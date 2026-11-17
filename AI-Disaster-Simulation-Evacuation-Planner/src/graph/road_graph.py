"""Road network as a directed graph with dynamic edge state."""
from __future__ import annotations

import networkx as nx

from config.settings import RiskThresholds
from src.data.schema import dataset_kind, frame_of, layer_sources
from src.graph.graph_utils import RoadStatus
from src.graph.road_classes import resolve_edge

WALK_SPEED = 1.4        # m/s
SPEED_MULT = {"OPEN": 1.0, "CONGESTED": 1.0, "RESTRICTED": 0.6, "DANGEROUS": 0.4}
ACCESS = {"OPEN": 1.0, "CONGESTED": 0.7, "RESTRICTED": 0.5, "DANGEROUS": 0.25, "BLOCKED": 0.0}


def build_graph(dataset: dict) -> nx.DiGraph:
    """Directed road graph. A two-way road becomes two directed edges, a one-way road (`oneway: true`, direction
    u -> v) just one. Speed, lanes and capacity come from the tags on the edge or its road class (road_classes.py)."""
    meta = dataset["meta"]
    frame = frame_of(dataset)
    G = nx.DiGraph(extent=max(frame.width_m, frame.height_m), frame=frame, width=frame.width_m, height=frame.height_m,
                   dataset_name=meta.get("name", "unnamed"), dataset_kind=dataset_kind(dataset),
                   provenance=layer_sources(dataset))
    for n in dataset["nodes"]:
        G.add_node(n["id"], x=n["x"], y=n["y"], hazard=0.0, risk=0.0)
    for e in dataset["edges"]:
        r = resolve_edge(e)
        oneway = bool(e.get("oneway", False))
        for a, b in (((e["u"], e["v"]),) if oneway else ((e["u"], e["v"]), (e["v"], e["u"]))):
            G.add_edge(a, b, distance=e["distance"], arterial=r["arterial"], road_class=r["class"], lanes=r["lanes"],
                       oneway=oneway, free_speed=r["speed_mps"], speed_limit_mps=r["speed_mps"],
                       base_time=e["distance"] / r["speed_mps"], current_time=e["distance"] / r["speed_mps"],
                       speed_vehicle=r["speed_mps"], speed_walk=WALK_SPEED,
                       capacity=r["capacity_per_m"] * e["distance"],
                       hazard=0.0, risk=0.0, exposure=0.0, accessibility=1.0, congestion=0.0,
                       status=RoadStatus.OPEN.value, forced_closed=False)
    return G


def refresh_edge_states(G: nx.DiGraph, th: RiskThresholds, loads: dict[tuple[int, int], int]) -> None:
    """Derive status, accessibility, congestion and travel time from hazard + traffic load."""
    for u, v, e in G.edges(data=True):
        h = e["hazard"]
        e["congestion"] = loads.get((u, v), 0) / e["capacity"]
        if e["forced_closed"] or h >= th.blocked:
            s = "BLOCKED"
        elif h >= th.dangerous:
            s = "DANGEROUS"
        elif h >= th.restricted:
            s = "RESTRICTED"
        elif e["congestion"] > 1.0:
            s = "CONGESTED"
        else:
            s = "OPEN"
        e["status"], e["accessibility"] = s, ACCESS[s]
        mult = SPEED_MULT.get(s, 1.0)
        bpr = 1.0 / (1.0 + 0.15 * e["congestion"] ** 4)   # BPR-style congestion slowdown
        e["speed_vehicle"] = max(0.1 * e["free_speed"], e["free_speed"] * mult * bpr)
        e["speed_walk"] = WALK_SPEED * mult
        e["current_time"] = e["distance"] / e["speed_vehicle"]