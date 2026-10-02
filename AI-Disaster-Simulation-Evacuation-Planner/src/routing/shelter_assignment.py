"""Shelters and the rules that pick one for a group of evacuees."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from config.settings import RoutingWeights


class ShelterStatus(str, Enum):
    ACTIVE = "ACTIVE"
    FULL = "FULL"
    UNSAFE = "UNSAFE"


@dataclass
class Shelter:
    id: int
    node: int
    x: float
    y: float
    capacity: int
    occupancy: int = 0
    risk: float = 0.0
    status: ShelterStatus = ShelterStatus.ACTIVE
    forced_unsafe: bool = False

    @property
    def remaining_capacity(self) -> int:
        return max(0, self.capacity - self.occupancy)

    def can_accept(self, size: int) -> bool:
        return self.status != ShelterStatus.UNSAFE and self.occupancy + size <= self.capacity


def assign_nearest(shelters: list[Shelter], dist: dict, paths: dict):
    """Baseline: nearest by distance; ignores capacity, status and risk."""
    reachable = [s for s in shelters if s.node in dist]
    if not reachable:
        return None
    best = min(reachable, key=lambda s: dist[s.node])
    return best.id, list(paths[best.node])


def assign_best(shelters: list[Shelter], dist: dict, paths: dict, size: int, reserved: dict[int, int],
                own_dest: int | None, w: RoutingWeights):
    """Proposed: cheapest reachable shelter that is safe and still has room (counting reservations)."""
    best, best_score = None, float("inf")
    for s in shelters:
        if s.node not in dist or s.status == ShelterStatus.UNSAFE:
            continue
        res = reserved[s.id] - (size if own_dest == s.id else 0)
        if s.capacity - s.occupancy - res < size:
            continue
        score = dist[s.node] + w.w_shelter_risk * s.risk + w.w_shelter_fill * (s.occupancy + res) / s.capacity
        if score < best_score:
            best, best_score = s, score
    return None if best is None else (best.id, list(paths[best.node]))
