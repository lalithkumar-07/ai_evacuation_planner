"""Graph helpers: road status enum, undirected edge listing, path statistics."""
from __future__ import annotations

from enum import Enum

import networkx as nx


class RoadStatus(str, Enum):
    OPEN = "OPEN"
    CONGESTED = "CONGESTED"
    RESTRICTED = "RESTRICTED"
    BLOCKED = "BLOCKED"
    DANGEROUS = "DANGEROUS"


SEVERITY = ["OPEN", "CONGESTED", "RESTRICTED", "DANGEROUS", "BLOCKED"]


def undirected_edges(G: nx.DiGraph) -> list[tuple[int, int]]:
    return sorted({(min(u, v), max(u, v)) for u, v in G.edges})


def path_stats(G: nx.DiGraph, path: list[int]) -> dict:
    """Facts about a route under the *current* graph state."""
    edges = [G[a][b] for a, b in zip(path, path[1:])]
    if not edges:
        return {"distance_m": 0.0, "time_s": 0.0, "avg_risk": 0.0, "max_risk": 0.0, "hazardous_roads": 0,
                "blocked_roads": 0}
    dist = sum(e["distance"] for e in edges)
    return {
        "distance_m": round(dist, 1),
        "time_s": round(sum(e["current_time"] for e in edges), 1),
        "avg_risk": round(sum(e["risk"] * e["distance"] for e in edges) / dist, 3),
        "max_risk": round(max(e["risk"] for e in edges), 3),
        "hazardous_roads": sum(e["status"] in ("RESTRICTED", "DANGEROUS", "BLOCKED") for e in edges),
        "blocked_roads": sum(e["status"] == "BLOCKED" for e in edges),
    }
