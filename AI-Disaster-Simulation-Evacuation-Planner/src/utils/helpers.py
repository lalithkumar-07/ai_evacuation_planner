"""Local metric (x, y) <-> lat/lon.

A ``Frame`` ties a dataset's local metre coordinates (x east, y north, from the south-west corner) to the
globe using a simple equirectangular projection. It works for any place, which real road data needs.

Backward compatible: every function still accepts the old ``extent`` number. A number means "the synthetic
square grid centred on PLANNER_ORIGIN_LAT/LON", exactly as before Phase 3.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import networkx as nx

from config.settings import ORIGIN_LAT, ORIGIN_LON

M_PER_DEG_LAT = 111_320.0


@dataclass(frozen=True)
class Frame:
    lat0: float        # latitude of the south-west corner (x = 0, y = 0)
    lon0: float        # longitude of the south-west corner
    cos_lat: float     # cos(latitude) used to turn metres east into degrees of longitude
    width_m: float     # extent east-west
    height_m: float    # extent north-south

    def to_latlon(self, x: float, y: float) -> list[float]:
        lat = self.lat0 + y / M_PER_DEG_LAT
        lon = self.lon0 + x / (M_PER_DEG_LAT * self.cos_lat)
        return [round(lat, 6), round(lon, 6)]

    def from_latlon(self, lat: float, lon: float) -> tuple[float, float]:
        return (lon - self.lon0) * M_PER_DEG_LAT * self.cos_lat, (lat - self.lat0) * M_PER_DEG_LAT

    def bounds(self) -> list[list[float]]:
        """[[south, west], [north, east]]"""
        return [self.to_latlon(0, 0), self.to_latlon(self.width_m, self.height_m)]

    def to_dict(self) -> dict:
        return asdict(self)


def legacy_frame(extent: float) -> Frame:
    """The synthetic grid: a square of side ``extent`` centred on the configured origin."""
    cos_lat = math.cos(math.radians(ORIGIN_LAT))
    return Frame(lat0=ORIGIN_LAT - extent / 2 / M_PER_DEG_LAT,
                 lon0=ORIGIN_LON - extent / 2 / (M_PER_DEG_LAT * cos_lat),
                 cos_lat=cos_lat, width_m=float(extent), height_m=float(extent))


def as_frame(frame_or_extent) -> Frame:
    return frame_or_extent if isinstance(frame_or_extent, Frame) else legacy_frame(float(frame_or_extent))


def to_latlon(x: float, y: float, frame_or_extent) -> list[float]:
    return as_frame(frame_or_extent).to_latlon(x, y)


def from_latlon(lat: float, lon: float, frame_or_extent) -> tuple[float, float]:
    """Inverse of to_latlon: map click -> local metres."""
    return as_frame(frame_or_extent).from_latlon(lat, lon)


def graph_frame(G: nx.DiGraph) -> Frame:
    return G.graph.get("frame") or legacy_frame(G.graph["extent"])


def node_latlon(G: nx.DiGraph, n: int) -> list[float]:
    return graph_frame(G).to_latlon(G.nodes[n]["x"], G.nodes[n]["y"])


def nearest_node(G: nx.DiGraph, lat: float, lon: float) -> int:
    """Node closest (in metres) to a lat/lon point."""
    x, y = graph_frame(G).from_latlon(lat, lon)
    return min(G.nodes, key=lambda n: (G.nodes[n]["x"] - x) ** 2 + (G.nodes[n]["y"] - y) ** 2)
