"""Phase 4: road classes, lanes, speed limits, one-way roads, per-road exposure, network analytics, and the guarantee
that the synthetic results did not change. Fixtures are TEST DATA in OSM-style tags, not real roads."""
import json
import math
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import scenario_service
from config.settings import ScenarioConfig
from src.data import data_loader
from src.data.importers import read_roads_geojson
from src.data.preprocessing import build_real_dataset, write_dataset
from src.data.schema import validate_dataset
from src.disaster.hazard_model import DISASTER_PRESETS, Disaster, area_scale, make_disaster
from src.graph.graph_utils import path_stats, road_edges, undirected_edges
from src.graph.network_stats import hotspots, summarize_network
from src.graph.road_classes import (DEFAULT_CLASSES, build_classes, parse_lanes, parse_maxspeed_kph, parse_oneway,
                                    resolve_edge)
from src.graph.road_graph import build_graph
from src.routing.shortest_path import shortest_path
from src.simulation.metrics import summarize
from src.simulation.simulation_engine import Simulation
from src.utils.helpers import nearest_node
from .data_pipeline import LAT0, LON0, N, STEP, make_fixture, tiny


def make_osm_like(tmp):
    """6x6 street grid with OSM-style tags. Rows (west-east): 0 primary 4 lanes 60 km/h | 1 plain | 2 ONE-WAY drawn
    west->east, 3 lanes | 3 ONE-WAY tagged -1 (so it runs east->west) | 4 unknown class 'weird', '30 mph' | 5 secondary.
    Columns are two-way. Extras: a footway (cars cannot use), a one-way spur that leads out and cannot return."""
    files = make_fixture(tmp)                                    # population + shelters on the same grid
    row = {0: {"highway": "primary", "maxspeed": "60", "lanes": "4"}, 1: {"highway": "residential"},
           2: {"highway": "residential", "oneway": "yes", "lanes": "3"}, 3: {"highway": "residential", "oneway": "-1"},
           4: {"highway": "weird", "maxspeed": "30 mph"}, 5: {"highway": "secondary"}}
    feats = [{"type": "Feature", "properties": row[i], "geometry": {"type": "LineString",
              "coordinates": [[LON0 + j * STEP, LAT0 + i * STEP] for j in range(N)]}} for i in range(N)]
    feats += [{"type": "Feature", "properties": {"highway": "residential"}, "geometry": {"type": "LineString",
               "coordinates": [[LON0 + j * STEP, LAT0 + i * STEP] for i in range(N)]}} for j in range(N)]
    feats.append({"type": "Feature", "properties": {"highway": "footway"}, "geometry": {"type": "LineString",
                  "coordinates": [[LON0, LAT0], [LON0 + 0.001, LAT0 + 0.001]]}})
    feats.append({"type": "Feature", "properties": {"highway": "residential", "oneway": "yes"}, "geometry": {
                  "type": "LineString", "coordinates": [[LON0 + 5 * STEP, LAT0 + 5 * STEP],
                                                         [LON0 + 5 * STEP + 0.003, LAT0 + 5 * STEP + 0.003]]}})
    files["roads"].write_text(json.dumps({"type": "FeatureCollection", "features": feats}), encoding="utf-8")
    return files


@pytest.fixture
def osm(tmp_path):
    f = make_osm_like(tmp_path)
    ds, manifest = build_real_dataset(f["roads"], f["population"], f["shelters"], name="osm_like")
    return ds, manifest, tmp_path


def node_at(G, i, j):
    return nearest_node(G, LAT0 + i * STEP, LON0 + j * STEP)


# ----------------------------------------------------------------------------------------------- tag parsers
@pytest.mark.parametrize("raw, kph", [("50", 50), ("50 km/h", 50), ("30 mph", 48.3), ("50;60", 50), ("walk", 7),
                                      ("none", None), ("IN:urban", None), ("1", None), ("999", None), (None, None)])
def test_parse_maxspeed(raw, kph):
    assert parse_maxspeed_kph(raw) == kph


def test_parse_lanes_and_oneway():
    assert [parse_lanes(v) for v in ("2", "2;3", "0", "13", "x", None)] == [2, 2, None, None, None, None]
    assert [parse_oneway(v) for v in ("yes", "true", "1", "-1", "reverse", "no", None, "weird")] == [1, 1, 1, -1, -1, 0, 0, 0]
    assert parse_oneway(None, "roundabout") == 1 and parse_oneway("no", "roundabout") == 1


# ------------------------------------------------------------------------------------------------ road classes
def test_synthetic_classes_reproduce_the_old_constants_exactly():
    a, l = resolve_edge({"arterial": True}), resolve_edge({"arterial": False})
    assert (a["speed_mps"], a["capacity_per_m"], a["arterial"], a["class"]) == (13.9, 0.5, True, "arterial")
    assert (l["speed_mps"], l["capacity_per_m"], l["arterial"], l["class"]) == (8.3, 0.2, False, "local")


def test_tags_beat_class_defaults():
    r = resolve_edge({"road_class": "primary", "lanes": 4, "maxspeed_kph": 60})
    assert r["lanes"] == 2 and r["capacity_per_m"] == 0.5 and abs(r["speed_mps"] - 60 / 3.6) < 1e-9     # 4 lanes both ways = 2 each
    ow = resolve_edge({"road_class": "residential", "lanes": 3, "oneway": True})
    assert ow["lanes"] == 3 and abs(ow["capacity_per_m"] - 0.6) < 1e-9                                  # one-way: all 3 lanes count
    assert resolve_edge({"road_class": "no-such-class", "arterial": True})["class"] == "arterial"        # unknown -> legacy flag


def test_class_overrides_from_config():
    c = build_classes({"primary": {"speed_kph": 45}, "boulevard": {"speed_kph": 55, "lanes": 3, "capacity_per_lane_m": 0.3, "arterial": True}})
    assert abs(c["primary"].speed_mps - 12.5) < 1e-9 and c["primary"].lanes == DEFAULT_CLASSES["primary"].lanes
    assert c["boulevard"].lanes == 3 and c["boulevard"].arterial
    with pytest.raises(ValueError, match="needs speed"):
        build_classes({"newclass": {"speed_kph": 30}})
    with pytest.raises(ValueError, match="positive"):
        build_classes({"primary": {"lanes": 0}})


# ----------------------------------------------------------------------------------------------------- importer
def test_importer_reads_osm_tags(tmp_path):
    r = read_roads_geojson(make_osm_like(tmp_path)["roads"])
    s = r["stats"]
    assert s["non_drivable_skipped"] == {"footway": 1} and s["unknown_road_classes"] == {"weird": 1}
    assert s["nodes_dropped_disconnected"] == 1                                            # the one-way spur's far end
    assert s["oneway_roads"] == 2 * (N - 1) and s["roads_with_tagged_speed"] > 0 and s["roads_with_tagged_lanes"] > 0
    assert set(s["roads_by_class"]) == {"primary", "residential", "unclassified", "secondary"}
    assert len(r["nodes"]) == N * N and len(r["edges"]) == 2 * N * (N - 1)                  # spur edge dropped with its node


def test_oneway_direction_is_kept_and_minus_one_is_flipped(tmp_path):
    r = read_roads_geojson(make_osm_like(tmp_path)["roads"])
    xy = {n["id"]: (n["x"], n["y"]) for n in r["nodes"]}
    ow = [e for e in r["edges"] if e.get("oneway")]
    rows = {}
    for e in ow:
        (x1, y1), (x2, y2) = xy[e["u"]], xy[e["v"]]
        rows.setdefault(round(y1 / 100), []).append(x2 > x1)                               # True = runs west -> east
    flows = sorted(rows.items())
    assert len(flows) == 2 and all(flows[0][1]) and not any(flows[1][1])                    # row 2 eastbound, row 3 westbound


# ------------------------------------------------------------------------------------------------- graph + routing
def test_graph_has_one_directed_edge_for_one_way_roads(osm):
    G = build_graph(osm[0])
    pairs = undirected_edges(G)
    one = [(u, v) for u, v in pairs if len(road_edges(G, u, v)) == 1]
    assert len(one) == 2 * (N - 1) and G.number_of_edges() == 2 * len(pairs) - len(one)


def test_graph_attributes_come_from_tags(osm):
    G = build_graph(osm[0])
    primary = G[node_at(G, 0, 0)][node_at(G, 0, 1)]
    assert primary["road_class"] == "primary" and primary["lanes"] == 2 and primary["oneway"] is False
    assert abs(primary["speed_limit_mps"] - 60 / 3.6) < 1e-9 and abs(primary["capacity"] - 0.5 * primary["distance"]) < 1e-6
    east = G[node_at(G, 2, 0)][node_at(G, 2, 1)]
    assert east["oneway"] is True and east["lanes"] == 3 and abs(east["capacity"] - 0.6 * east["distance"]) < 1e-6
    assert not G.has_edge(node_at(G, 2, 1), node_at(G, 2, 0))
    mph = G[node_at(G, 4, 0)][node_at(G, 4, 1)]
    assert mph["road_class"] == "unclassified" and abs(mph["speed_limit_mps"] - 48.3 / 3.6) < 1e-6   # '30 mph', tagged speed wins


def test_routing_respects_one_way_direction(osm):
    G = build_graph(osm[0])
    west2, east2, west3, east3 = node_at(G, 2, 0), node_at(G, 2, 5), node_at(G, 3, 0), node_at(G, 3, 5)
    straight = lambda path, i: all(abs(G.nodes[n]["y"] - G.nodes[path[0]]["y"]) < 1 for n in path)
    we, ew = shortest_path(G, west2, east2), shortest_path(G, east2, west2)
    assert straight(we, 2) and not straight(ew, 2)                                         # row 2: only eastbound is direct
    ew3, we3 = shortest_path(G, east3, west3), shortest_path(G, west3, east3)
    assert straight(ew3, 3) and not straight(we3, 3)                                       # row 3 (-1): only westbound is direct
    assert path_stats(G, ew)["distance_m"] > path_stats(G, we)["distance_m"]


def test_simulation_runs_with_one_way_roads_and_closures(osm):
    ds, _, _ = osm
    cfg = replace(ScenarioConfig(), evacuation_radius_m=5000, initial_radius_m=150, max_radius_m=500, spread_speed_mps=0.2,
                  duration_s=3000, n_shelters=3, road_closure_count=100, road_closure_time_s=60)
    sim = Simulation(cfg, "proposed", dataset=ds)
    sim.run()
    G = sim.G
    pairs_blocked = {(min(u, v), max(u, v)) for u, v, e in G.edges(data=True) if e["status"] == "BLOCKED"}
    assert sim.history[-1]["blocked_roads"] == len(pairs_blocked) > 0                       # one-way edges are counted too
    from backend.services.simulation_service import state
    assert len(state(sim)["roads"]) == len(undirected_edges(G))                             # serialising never hits a missing direction


def test_layers_describe_each_road(osm, monkeypatch):
    ds, manifest, tmp = osm
    path, _ = write_dataset(ds, manifest, tmp / "out")
    monkeypatch.setattr(data_loader, "DATASET_PATH", path)
    c = TestClient(app, headers={"X-Session-Id": "road-test-00001"})
    roads = c.post("/api/disaster/start", json={"duration_s": 600}).json()["layers"]["roads"]
    assert {r["cls"] for r in roads} == {"primary", "residential", "unclassified", "secondary"}
    assert sum(r["oneway"] for r in roads) == 2 * (N - 1) and all(isinstance(r["rev"], bool) for r in roads)
    assert {r["kph"] for r in roads if r["cls"] == "primary"} == {60}
    assert {r["lanes"] for r in roads if r["cls"] == "primary"} == {2}


# ------------------------------------------------------------------------------------------------------ validation
@pytest.mark.parametrize("patch, expect", [
    ({"lanes": 0}, "lanes must be an integer"), ({"lanes": "2"}, "lanes must be an integer"), ({"lanes": 13}, "lanes must be"),
    ({"maxspeed_kph": -5}, "maxspeed_kph"), ({"maxspeed_kph": 500}, "maxspeed_kph"), ({"oneway": "yes"}, "oneway must be"),
])
def test_validation_of_road_fields(patch, expect):
    d = tiny()
    d["edges"][0].update(patch)
    r = validate_dataset(d)
    assert not r.ok and any(expect in e for e in r.errors), r.errors


def test_validation_warns_about_unknown_road_classes():
    d = tiny()
    d["edges"][0]["road_class"] = "hyperloop"
    r = validate_dataset(d)
    assert r.ok and any("hyperloop" in w for w in r.warnings)


def one_way_chain(shelter_node, group_nodes):
    d = tiny()
    d["edges"] = [{"u": i, "v": i + 1, "distance": 10.0, "oneway": True} for i in range(3)]       # 0 -> 1 -> 2 -> 3 only
    d["shelters"] = [{"id": 0, "node": shelter_node, "capacity": 50, "occupancy": 0}]
    d["population"] = [{"id": i, "node": n, "size": 10, "mobility": "vehicle"} for i, n in enumerate(group_nodes)]
    return d


def test_reachability_follows_one_way_directions():
    ok = validate_dataset(one_way_chain(3, [0, 1]))                                         # everyone can drive towards node 3
    assert ok.ok and not any("cannot reach" in w for w in ok.warnings)
    partial = validate_dataset(one_way_chain(0, [0, 1]))                                    # node 1 cannot get back to node 0
    assert partial.ok and any("1 of 2 population groups" in w for w in partial.warnings)
    none = validate_dataset(one_way_chain(0, [1, 2]))
    assert not none.ok and any("no population group can reach any shelter" in e for e in none.errors)


# ---------------------------------------------------------------------------------------- exposure + analytics
def test_per_road_exposure_adds_up():
    cfg = replace(ScenarioConfig(), duration_s=2400)
    sim = Simulation(cfg, "baseline")
    sim.run()
    per_road = sum(e["exposure"] for _, _, e in sim.G.edges(data=True))
    assert 0 < per_road <= sim.exposure_person_s + 1e-6                                     # roads are a part of the total
    top = hotspots(sim.G, "exposure", 5)
    assert len(top) == 5 and [t["value"] for t in top] == sorted((t["value"] for t in top), reverse=True)
    assert top[0]["unit"] == "person-hazard-min" and top[0]["road_class"] in ("arterial", "local")
    with pytest.raises(ValueError):
        hotspots(sim.G, "luck")


def test_network_summary_of_the_demo():
    G = build_graph(data_loader.load_dataset())
    s = summarize_network(G)
    assert s["nodes"] == 256 and s["roads"] == 456 and s["oneway_roads"] == 0 and s["two_way_roads"] == 456
    assert set(s["by_class"]) == {"arterial", "local"} and s["by_class"]["arterial"]["lanes_per_direction"] == 2
    assert sum(c["roads"] for c in s["by_class"].values()) == 456
    assert abs(s["total_km"] - sum(e["distance"] for _, _, e in G.edges(data=True)) / 2000) < 0.01


def test_network_api(osm, monkeypatch):
    c = TestClient(app, headers={"X-Session-Id": "network-test-001"})
    demo = c.get("/api/network/summary").json()
    assert demo["dataset"] == "demo_scenario" and demo["roads"] == 456 and demo["oneway_roads"] == 0
    assert c.get("/api/network/hotspots").status_code == 409                                # no simulation yet
    c.post("/api/disaster/start", json={})
    c.post("/api/simulation/step", json={"steps": 40})
    rows = c.get("/api/network/hotspots", params={"by": "exposure", "limit": 3}).json()
    assert 1 <= len(rows) <= 3 and rows[0]["value"] >= rows[-1]["value"] > 0
    assert c.get("/api/network/hotspots", params={"by": "congestion"}).status_code == 200
    assert c.get("/api/network/hotspots", params={"by": "luck"}).status_code == 422
    assert c.get("/api/network/hotspots", params={"limit": 0}).status_code == 422
    ds, manifest, tmp = osm
    path, _ = write_dataset(ds, manifest, tmp / "out")
    monkeypatch.setattr(data_loader, "DATASET_PATH", path)
    real = c.get("/api/network/summary").json()
    assert real["dataset"] == "osm_like" and real["oneway_roads"] == 2 * (N - 1) and "primary" in real["by_class"]


# --------------------------------------------------------------------------- performance work changed nothing
GOLDEN = {   # measured on the Phase 3 code (duration 5400 s) BEFORE the Phase 4 changes
    ("expanding", "baseline"): {"avg_trip_time_s": 393.114286, "blocked_roads_end": 72, "congestion_peak": 1.723623, "evacuated_population": 1400, "person_minutes_in_hazard": 263712.5, "rerouting_count": 0, "route_failures": 103, "shelter_utilization": 0.186667, "success_rate": 0.352201, "unserved_population": 2575},
    ("expanding", "proposed"): {"avg_trip_time_s": 690.9512, "blocked_roads_end": 72, "congestion_peak": 1.326936, "evacuated_population": 3125, "person_minutes_in_hazard": 107437.5, "rerouting_count": 9, "route_failures": 3, "shelter_utilization": 0.416667, "success_rate": 0.786164, "unserved_population": 850},
    ("combined", "baseline"): {"avg_trip_time_s": 413.629167, "blocked_roads_end": 81, "congestion_peak": 4.596328, "evacuated_population": 2400, "person_minutes_in_hazard": 530575.0, "rerouting_count": 0, "route_failures": 111, "shelter_utilization": 0.266667, "success_rate": 0.301887, "unserved_population": 5550},
    ("combined", "proposed"): {"avg_trip_time_s": 603.536134, "blocked_roads_end": 81, "congestion_peak": 3.686953, "evacuated_population": 5950, "person_minutes_in_hazard": 215900.0, "rerouting_count": 14, "route_failures": 12, "shelter_utilization": 0.661111, "success_rate": 0.748428, "unserved_population": 2000},
}
COMBINED = dict(population_scale=2.0, shelter_capacity_scale=1.2, road_closure_count=10, shelter_failures=[[0, 1200]])


@pytest.mark.parametrize("name, strategy", list(GOLDEN))
def test_synthetic_results_are_unchanged_since_phase_3(name, strategy):
    kw = COMBINED if name == "combined" else {}
    sim = Simulation(replace(ScenarioConfig(), duration_s=5400, **kw), strategy)
    sim.run()
    m = summarize(sim)
    got = {k: (round(m[k], 6) if isinstance(m[k], float) else m[k]) for k in GOLDEN[(name, strategy)] if k != "blocked_roads_end"}
    got["blocked_roads_end"] = sim.history[-1]["blocked_roads"]
    assert got == GOLDEN[(name, strategy)]


class NoSignaturePredictor:
    """Same forecast as the default, but without `signature`, so the manager can never skip an update."""
    def __init__(self, horizon_s=1800.0):
        self.horizon_s = horizon_s

    def predict_hazard(self, disaster, x, y, t):
        return 0.0 if disaster is None else disaster.hazard_at(x, y, t + self.horizon_s)


@pytest.mark.parametrize("kw", [dict(), dict(initial_radius_m=1500, max_radius_m=1500, spread_speed_mps=0.0),
                                dict(disaster_type="wildfire", road_closure_count=5), dict(disaster_enabled=False)])
def test_skipping_unchanged_hazard_gives_identical_runs(kw):
    cfg = replace(ScenarioConfig(), duration_s=2400, **kw)
    fast, slow = Simulation(cfg, "proposed"), Simulation(cfg, "proposed", predictor=NoSignaturePredictor())
    fast.run(); slow.run()
    assert fast.history == slow.history


def test_static_hazard_is_computed_once_and_live_changes_recompute(monkeypatch):
    calls = {"n": 0}
    real = Disaster.hazard_at

    def counting(self, x, y, t):
        calls["n"] += 1
        return real(self, x, y, t)
    monkeypatch.setattr(Disaster, "hazard_at", counting)
    sim = Simulation(replace(ScenarioConfig(), initial_radius_m=1500, max_radius_m=1500, spread_speed_mps=0.0, duration_s=3000), "proposed")
    start = calls["n"]
    assert start > 0
    for _ in range(20):
        sim.step()
    assert calls["n"] == start                                                              # nothing recomputed for a static field
    before = max(e["hazard"] for _, _, e in sim.G.edges(data=True))
    sim.update_disaster(intensity=0.5)
    assert calls["n"] > start and max(e["hazard"] for _, _, e in sim.G.edges(data=True)) < before


# ------------------------------------------------------------------------------------------ area-scaled defaults
def test_area_scale():
    assert area_scale(6000, 6000) == 1.0 and area_scale(20000, 9000) == 1.0                 # never enlarged
    assert abs(area_scale(1590, 1590) - 0.265) < 1e-3 and area_scale(100, 100) == 0.15      # clamped


def test_preset_radii_shrink_on_small_areas_but_explicit_values_do_not():
    cfg = ScenarioConfig()
    big, small = make_disaster(cfg, (0, 0), 1.0), make_disaster(cfg, (0, 0), 0.25)
    p = DISASTER_PRESETS["flood"]
    assert (big.initial_radius, big.max_radius, big.spread_speed) == (p["initial_radius_m"], p["max_radius_m"], p["spread_speed_mps"])
    assert small.max_radius == p["max_radius_m"] * 0.25 and small.spread_speed == p["spread_speed_mps"] * 0.25
    explicit = make_disaster(replace(cfg, initial_radius_m=500, max_radius_m=900, spread_speed_mps=1.0), (0, 0), 0.25)
    assert (explicit.initial_radius, explicit.max_radius, explicit.spread_speed) == (500, 900, 1.0)


def test_meta_defaults_follow_the_dataset_size(osm, monkeypatch):
    demo = scenario_service.meta()["defaults"]
    assert (demo["initial_radius_m"], demo["max_radius_m"], demo["spread_speed_mps"]) == (600.0, 2500.0, 1.5)   # demo unchanged
    ds, manifest, tmp = osm
    path, _ = write_dataset(ds, manifest, tmp / "out")
    monkeypatch.setattr(data_loader, "DATASET_PATH", path)
    m = scenario_service.meta()
    assert m["defaults"]["max_radius_m"] < 1000 and m["disaster_types"]["flood"]["max_radius_m"] == m["defaults"]["max_radius_m"]
    assert m["disaster_types"]["flood"]["falloff"] == DISASTER_PRESETS["flood"]["falloff"]                # only lengths are scaled