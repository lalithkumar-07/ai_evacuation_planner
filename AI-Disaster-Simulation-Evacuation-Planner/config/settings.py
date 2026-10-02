"""Settings: environment variables + simulation_config.yaml + scenario dataclass."""
from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv is optional
    pass

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("PLANNER_DATA_DIR", ROOT / "data"))
DEMO_SCENARIO_PATH = DATA_DIR / "sample" / "demo_scenario.json"
FRONTEND_DIR = ROOT / "frontend"
HOST = os.getenv("PLANNER_HOST", "127.0.0.1")
PORT = int(os.getenv("PLANNER_PORT", "8000"))
ORIGIN_LAT = float(os.getenv("PLANNER_ORIGIN_LAT", "17.3850"))
ORIGIN_LON = float(os.getenv("PLANNER_ORIGIN_LON", "78.4867"))
LOG_LEVEL = os.getenv("PLANNER_LOG_LEVEL", "INFO")

_Y = yaml.safe_load((ROOT / "config" / "simulation_config.yaml").read_text()) or {}


@dataclass(frozen=True)
class RoutingWeights:
    w_distance: float = 1.0
    w_time: float = 1.0
    w_risk: float = 2.0
    w_congestion: float = 1.0
    w_accessibility: float = 2.0
    w_shelter_risk: float = 10.0
    w_shelter_fill: float = 2.0


@dataclass(frozen=True)
class RiskThresholds:
    blocked: float = 0.6
    dangerous: float = 0.4
    restricted: float = 0.2


@dataclass(frozen=True)
class RiskLevels:
    medium: float = 0.25
    high: float = 0.5
    critical: float = 0.75


@dataclass(frozen=True)
class SimParams:
    dt_s: float = 30
    duration_s: float = 10800
    trap_timeout_s: float = 1800
    forecast_horizon_s: float = 1800


ROUTING_WEIGHTS = RoutingWeights(**_Y.get("routing_weights", {}))
RISK_THRESHOLDS = RiskThresholds(**_Y.get("risk_thresholds", {}))
RISK_LEVELS = RiskLevels(**_Y.get("risk_levels", {}))
SIM = SimParams(**_Y.get("simulation", {}))
RISK_FUNCTION = _Y.get("risk_function", "weighted_sum")


@dataclass
class ScenarioConfig:
    """What varies between experiments. Geography/population come from the dataset file."""
    id: str = "custom"
    name: str = "Custom scenario"
    description: str = ""
    disaster_type: str = "flood"
    disaster_enabled: bool = True
    intensity: float = 0.9
    center_x_frac: float = 0.5
    center_y_frac: float = 0.5
    initial_radius_m: float | None = None     # None -> disaster-type preset
    max_radius_m: float | None = None
    spread_speed_mps: float | None = None     # 0 = static hazard
    evacuation_radius_m: float = 2500.0       # people inside are ordered to evacuate
    population_scale: float = 1.0
    shelter_capacity_scale: float = 1.0
    shelter_failures: list[list[float]] = field(default_factory=list)  # [[shelter_id, time_s], ...]
    road_closure_count: int = 0
    road_closure_time_s: float = 300.0
    duration_s: float = SIM.duration_s
    dt_s: float = SIM.dt_s
    trap_timeout_s: float = SIM.trap_timeout_s
    seed: int = 42

    def to_dict(self) -> dict:
        return asdict(self)


def configure_logging() -> None:
    logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
