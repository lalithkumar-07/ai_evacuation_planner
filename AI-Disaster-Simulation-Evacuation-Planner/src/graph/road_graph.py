"""Road network as a directed graph with dynamic edge state."""
from __future__ import annotations

import networkx as nx

from config.settings import RiskThresholds
from src.graph.graph_utils import RoadStatus

ARTERIAL_SPEED = 13.9   # m/s (50 km/h)
LOCAL_SPEED = 8.3       # m/s (30 km/h)
WALK_SPEED = 1.4        # m/s
PERSONS_PER_M = {True: 0.5, False: 0.2}   # road capacity: people on a segment per metre
SPEED_MULT = {"OPEN": 1.0, "CONGESTED": 1.0, "RESTRICTED": 0.6, "DANGEROUS": 0.4}
ACCESS = {"OPEN": 1.0, "CONGESTED": 0.7, "RESTRICTED": 0.5, "DANGEROUS": 0.25, "BLOCKED": 0.0}


def build_graph(dataset: dict) -> nx.DiGraph:
    meta = dataset["meta"]
    G = nx.DiGraph(extent=(meta["grid_size"] - 1) * meta["spacing_m"])
    for n in dataset["nodes"]:
        G.add_node(n["id"], x=n["x"], y=n["y"], hazard=0.0, risk=0.0)
    for e in dataset["edges"]:
        speed = ARTERIAL_SPEED if e["arterial"] else LOCAL_SPEED
        for a, b in ((e["u"], e["v"]), (e["v"], e["u"])):
            G.add_edge(a, b, distance=e["distance"], arterial=e["arterial"], free_speed=speed,
                       base_time=e["distance"] / speed, current_time=e["distance"] / speed,
                       speed_vehicle=speed, speed_walk=WALK_SPEED,
                       capacity=PERSONS_PER_M[e["arterial"]] * e["distance"],
                       hazard=0.0, risk=0.0, accessibility=1.0, congestion=0.0,
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
