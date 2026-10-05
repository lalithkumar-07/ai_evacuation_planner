"""Local metric (x, y) <-> lat/lon for display."""
from __future__ import annotations

import math

import networkx as nx

from config.settings import ORIGIN_LAT, ORIGIN_LON

M_PER_DEG_LAT = 111_320.0


def to_latlon(x: float, y: float, extent: float) -> list[float]:
    lat = ORIGIN_LAT + (y - extent / 2) / M_PER_DEG_LAT
    lon = ORIGIN_LON + (x - extent / 2) / (M_PER_DEG_LAT * math.cos(math.radians(ORIGIN_LAT)))
    return [round(lat, 6), round(lon, 6)]


def node_latlon(G: nx.DiGraph, n: int) -> list[float]:
    return to_latlon(G.nodes[n]["x"], G.nodes[n]["y"], G.graph["extent"])


def nearest_node(G: nx.DiGraph, lat: float, lon: float) -> int:
    return min(G.nodes, key=lambda n: (lambda p: (p[0] - lat) ** 2 + (p[1] - lon) ** 2)(node_latlon(G, n)))


def from_latlon(lat: float, lon: float, extent: float) -> tuple[float, float]:
    """Inverse of to_latlon: map click -> local metres."""
    y = (lat - ORIGIN_LAT) * M_PER_DEG_LAT + extent / 2
    x = (lon - ORIGIN_LON) * M_PER_DEG_LAT * math.cos(math.radians(ORIGIN_LAT)) + extent / 2
    return x, y