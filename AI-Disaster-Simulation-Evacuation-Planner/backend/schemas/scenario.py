from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from src.disaster.hazard_model import DISASTER_PRESETS


class ScenarioIn(BaseModel):
    name: str = Field("Custom scenario", max_length=80)
    description: str = Field("", max_length=300)
    disaster_type: str = "flood"
    disaster_enabled: bool = True
    intensity: float = Field(0.9, gt=0, le=1)
    initial_radius_m: float | None = Field(None, gt=0, le=10000)
    max_radius_m: float | None = Field(None, gt=0, le=10000)
    spread_speed_mps: float | None = Field(None, ge=0, le=20)
    population_scale: float = Field(1.0, gt=0, le=10)
    shelter_capacity_scale: float = Field(1.0, gt=0, le=10)
    shelter_failures: list[tuple[int, float]] = []
    road_closure_count: int = Field(0, ge=0, le=100)
    duration_s: float = Field(10800, ge=300, le=43200)

    @field_validator("disaster_type")
    @classmethod
    def _known(cls, v: str) -> str:
        if v not in DISASTER_PRESETS:
            raise ValueError(f"disaster_type must be one of {sorted(DISASTER_PRESETS)}")
        return v
