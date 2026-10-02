"""Risk score = f(hazard, forecast hazard, population exposure). Functions are pluggable."""
from __future__ import annotations

from typing import Callable

from config.settings import RISK_LEVELS

RiskFn = Callable[[dict[str, float]], float]
RISK_FUNCTIONS: dict[str, RiskFn] = {}


def register_risk_function(name: str) -> Callable[[RiskFn], RiskFn]:
    def deco(fn: RiskFn) -> RiskFn:
        RISK_FUNCTIONS[name] = fn
        return fn
    return deco


def get_risk_function(name: str) -> RiskFn:
    if name not in RISK_FUNCTIONS:
        raise ValueError(f"Unknown risk function '{name}'. Available: {sorted(RISK_FUNCTIONS)}")
    return RISK_FUNCTIONS[name]


def _clip(v: float) -> float:
    return max(0.0, min(1.0, v))


@register_risk_function("weighted_sum")
def weighted_sum(f: dict[str, float]) -> float:
    """0.6*hazard + 0.4*forecast hazard, raised by up to 25% where many people live (exposure 0..1)."""
    return _clip((0.6 * f["hazard"] + 0.4 * f["predicted"]) * (1.0 + 0.25 * f.get("exposure", 0.0)))


@register_risk_function("max_hazard")
def max_hazard(f: dict[str, float]) -> float:
    return _clip(max(f["hazard"], f["predicted"]))


def risk_level(score: float) -> str:
    if score >= RISK_LEVELS.critical:
        return "CRITICAL"
    if score >= RISK_LEVELS.high:
        return "HIGH"
    if score >= RISK_LEVELS.medium:
        return "MEDIUM"
    return "LOW"
