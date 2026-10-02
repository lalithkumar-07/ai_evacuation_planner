from dataclasses import replace

from config.settings import RISK_THRESHOLDS, ScenarioConfig
from src.data.data_loader import build_scenario
from src.disaster.hazard_model import DISASTER_PRESETS, make_disaster
from src.disaster.risk_calculator import get_risk_function, risk_level
from src.graph.road_graph import refresh_edge_states
from src.simulation.simulation_engine import Simulation


def test_all_presets_produce_hazard():
    for kind in DISASTER_PRESETS:
        d = make_disaster(replace(ScenarioConfig(), disaster_type=kind), (100, 100))
        assert d.hazard_at(100, 100, 0) > 0


def test_flood_spreads_and_decays_with_distance():
    d = make_disaster(ScenarioConfig(), (0, 0))
    assert d.radius(0) < d.radius(600) <= d.max_radius
    assert d.hazard_at(0, 0, 0) > d.hazard_at(300, 0, 0) > 0
    assert d.hazard_at(d.max_radius + 1, 0, 1e6) == 0


def test_earthquake_is_static():
    d = make_disaster(replace(ScenarioConfig(), disaster_type="earthquake"), (0, 0))
    assert d.radius(0) == d.radius(5000)


def test_risk_levels_and_function():
    assert [risk_level(x) for x in (0.1, 0.3, 0.6, 0.9)] == ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    f = get_risk_function("weighted_sum")
    assert f({"hazard": 0.5, "predicted": 0.5, "exposure": 1.0}) > f({"hazard": 0.5, "predicted": 0.5, "exposure": 0.0})
    assert 0 <= f({"hazard": 1, "predicted": 1, "exposure": 1}) <= 1


def test_blocked_roads_appear_and_grow_with_time():
    sim = Simulation(ScenarioConfig(), "proposed")
    b0 = sim.history[0]["blocked_roads"]
    for _ in range(40):
        sim.step()
    assert sim.history[-1]["blocked_roads"] >= b0 > 0


def test_no_disaster_means_no_hazard():
    sim = Simulation(replace(ScenarioConfig(), disaster_enabled=False), "proposed")
    assert max(d["hazard"] for _, d in sim.G.nodes(data=True)) == 0
    assert sim.history[0]["blocked_roads"] == 0


def test_closures_block_roads():
    sim = Simulation(replace(ScenarioConfig(), disaster_enabled=False, road_closure_count=5, road_closure_time_s=60), "proposed")
    sim.step(); sim.step(); sim.step()
    assert sim.history[-1]["blocked_roads"] == 5
