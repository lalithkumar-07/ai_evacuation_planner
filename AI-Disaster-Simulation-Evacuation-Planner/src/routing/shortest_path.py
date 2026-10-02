"""BASELINE routing: distance only (Dijkstra / A*). Ignores hazard, traffic and road status."""
from __future__ import annotations

import math

import networkx as nx


def single_source_distance(G: nx.DiGraph, source: int) -> tuple[dict, dict]:
    return nx.single_source_dijkstra(G, source, weight="distance")


def shortest_path(G: nx.DiGraph, source: int, target: int) -> list[int] | None:
    try:
        return nx.dijkstra_path(G, source, target, weight="distance")
    except nx.NetworkXNoPath:
        return None


def astar_path(G: nx.DiGraph, source: int, target: int) -> list[int] | None:
    """A* with a Euclidean heuristic (admissible: road length >= straight line)."""
    def h(a: int, b: int) -> float:
        return math.hypot(G.nodes[a]["x"] - G.nodes[b]["x"], G.nodes[a]["y"] - G.nodes[b]["y"])
    try:
        return nx.astar_path(G, source, target, heuristic=h, weight="distance")
    except nx.NetworkXNoPath:
        return None
