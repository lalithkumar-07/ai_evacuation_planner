"""Prediction interface.

DeterministicForecastPredictor is NOT a trained model: it extrapolates the simulated disaster's own
spread `horizon_s` ahead (an "oracle" with perfect knowledge of the simulator). Results using it show an
upper bound on what a good forecast could deliver. Model training not yet performed.
Demand / traffic / population predictors should implement the same pattern later.
"""
from __future__ import annotations

from typing import Protocol

from src.disaster.hazard_model import Disaster


class RiskPredictor(Protocol):
    def predict_hazard(self, disaster: Disaster | None, x: float, y: float, t: float) -> float: ...


class DeterministicForecastPredictor:
    def __init__(self, horizon_s: float = 1800.0) -> None:
        self.horizon_s = horizon_s

    def predict_hazard(self, disaster, x, y, t):
        return 0.0 if disaster is None else disaster.hazard_at(x, y, t + self.horizon_s)
