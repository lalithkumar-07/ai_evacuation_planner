"""Hazard generation: a radial, time-varying field. Add new disaster types with register_disaster_type."""
from __future__ import annotations

import math
from dataclasses import dataclass

from config.settings import ScenarioConfig

DISASTER_PRESETS: dict[str, dict] = {
    "flood": dict(falloff=0.5, initial_radius_m=600.0, max_radius_m=2500.0, spread_speed_mps=1.5),
    "wildfire": dict(falloff=1.0, initial_radius_m=400.0, max_radius_m=2200.0, spread_speed_mps=2.0),
    "earthquake": dict(falloff=1.5, initial_radius_m=2000.0, max_radius_m=2000.0, spread_speed_mps=0.0),
}


def register_disaster_type(name: str, **preset) -> None:
    DISASTER_PRESETS[name] = preset


@dataclass(frozen=True)
class Disaster:
    kind: str
    cx: float
    cy: float
    intensity: float
    initial_radius: float
    max_radius: float
    spread_speed: float
    falloff: float
    start_time: float = 0.0

    def radius(self, t: float) -> float:
        if t < self.start_time:
            return 0.0
        return min(self.max_radius, self.initial_radius + self.spread_speed * (t - self.start_time))

    def hazard_at(self, x: float, y: float, t: float) -> float:
        r = self.radius(t)
        d = math.hypot(x - self.cx, y - self.cy)
        if r <= 0 or d >= r:
            return 0.0
        return self.intensity * (1.0 - d / r) ** self.falloff


def make_disaster(cfg: ScenarioConfig, center: tuple[float, float]) -> Disaster | None:
    if not cfg.disaster_enabled:
        return None
    p = DISASTER_PRESETS[cfg.disaster_type]
    pick = lambda v, k: p[k] if v is None else v
    return Disaster(cfg.disaster_type, center[0], center[1], cfg.intensity,
                    pick(cfg.initial_radius_m, "initial_radius_m"), pick(cfg.max_radius_m, "max_radius_m"),
                    pick(cfg.spread_speed_mps, "spread_speed_mps"), p["falloff"])
