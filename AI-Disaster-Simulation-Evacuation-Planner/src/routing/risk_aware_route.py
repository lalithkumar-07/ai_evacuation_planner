"""PROPOSED routing: dynamic multi-factor edge cost. Blocked roads are removed from the search."""
from __future__ import annotations

from typing import Callable

import networkx as nx

from config.settings import RoutingWeights


def dynamic_cost(w: RoutingWeights) -> Callable[[int, int, dict], float | None]:
    """cost = distance + travel time + risk + congestion + accessibility (weights in YAML)."""
    def cost(u: int, v: int, d: dict) -> float | None:
        if d["status"] == "BLOCKED":
            return None
        km = d["distance"] / 1000.0
        return (w.w_distance * km
                + w.w_time * d["current_time"] / 60.0
                + w.w_risk * d["risk"] * d["distance"] / 100.0
                + w.w_congestion * min(d["congestion"], 3.0) * km
                + w.w_accessibility * (1.0 - d["accessibility"]) * km)
    return cost


def single_source_risk_aware(G: nx.DiGraph, source: int, cost_fn) -> tuple[dict, dict]:
    return nx.single_source_dijkstra(G, source, weight=cost_fn)
