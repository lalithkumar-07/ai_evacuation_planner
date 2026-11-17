"""Facts about a road graph: what it is made of (static) and where the trouble is (during a run)."""
from __future__ import annotations

import networkx as nx

from src.graph.graph_utils import undirected_edges
from src.utils.helpers import node_latlon

HOTSPOT_KEYS = ("exposure", "congestion", "risk")


def summarize_network(G: nx.DiGraph) -> dict:
    """Counts, length, lanes, speeds, capacity and one-way share, overall and per road class."""
    pairs = undirected_edges(G)
    by_class: dict[str, dict] = {}
    total_m = 0.0
    oneway = 0
    for u, v in pairs:
        dirs = [G[a][b] for a, b in ((u, v), (v, u)) if G.has_edge(a, b)]
        e = dirs[0]
        c = by_class.setdefault(e["road_class"], {"roads": 0, "km": 0.0, "lanes_per_direction": e["lanes"],
                                                  "speed_kph": round(e["speed_limit_mps"] * 3.6, 1), "oneway_roads": 0})
        c["roads"] += 1
        c["km"] += e["distance"] / 1000
        total_m += e["distance"]
        if len(dirs) == 1:
            oneway += 1
            c["oneway_roads"] += 1
    speeds = [e["speed_limit_mps"] * 3.6 for _, _, e in G.edges(data=True)]
    return {"nodes": G.number_of_nodes(), "roads": len(pairs), "directed_edges": G.number_of_edges(),
            "oneway_roads": oneway, "two_way_roads": len(pairs) - oneway, "total_km": round(total_m / 1000, 2),
            "arterial_km": round(sum(e["distance"] for u, v, e in G.edges(data=True) if e["arterial"]) / 2000, 2),
            "speed_kph": {"min": round(min(speeds), 1), "max": round(max(speeds), 1)} if speeds else None,
            "lane_capacity_people": round(sum(e["capacity"] for _, _, e in G.edges(data=True))),
            "by_class": {k: {**v, "km": round(v["km"], 2)} for k, v in sorted(by_class.items())}}


def hotspots(G: nx.DiGraph, by: str = "exposure", limit: int = 10) -> list[dict]:
    """The roads (directed edges) with the highest cumulative exposure, current congestion or current risk."""
    if by not in HOTSPOT_KEYS:
        raise ValueError(f"by must be one of {HOTSPOT_KEYS}")
    key = {"exposure": "exposure", "congestion": "congestion", "risk": "risk"}[by]
    rows = [(e[key], u, v, e) for u, v, e in G.edges(data=True) if e[key] > 0]
    rows.sort(key=lambda r: -r[0])
    return [{"from": node_latlon(G, u), "to": node_latlon(G, v), "road_class": e["road_class"], "lanes": e["lanes"],
             "speed_kph": round(e["speed_limit_mps"] * 3.6), "oneway": e["oneway"], "status": e["status"],
             "length_m": round(e["distance"]), "value": round(val / 60, 1) if by == "exposure" else round(val, 3),
             "unit": "person-hazard-min" if by == "exposure" else "load/capacity" if by == "congestion" else "risk 0-1"}
            for val, u, v, e in rows[:limit]]