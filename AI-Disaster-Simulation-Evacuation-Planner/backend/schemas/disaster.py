from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from src.disaster.hazard_model import DISASTER_PRESETS


class DisasterStartIn(BaseModel):
    """Generate a scenario. Every field except type/intensity is optional and overrides the base preset."""
    disaster_type: str = "flood"
    intensity: float = Field(0.9, gt=0, le=1)
    scenario_id: str = "expanding"                 # base preset (or a custom scenario of this session)
    strategy: str = Field("proposed", pattern="^(baseline|proposed)$")
    disaster_enabled: bool | None = None
    center_lat: float | None = Field(None, ge=-90, le=90)      # epicentre picked on the map
    center_lon: float | None = Field(None, ge=-180, le=180)
    initial_radius_m: float | None = Field(None, gt=0, le=10000)
    max_radius_m: float | None = Field(None, gt=0, le=10000)
    spread_speed_mps: float | None = Field(None, ge=0, le=20)
    evacuation_radius_m: float | None = Field(None, gt=0, le=10000)
    population_scale: float | None = Field(None, gt=0, le=10)
    shelter_capacity_scale: float | None = Field(None, gt=0, le=10)
    n_shelters: int | None = Field(None, ge=1, le=12)
    road_closure_count: int | None = Field(None, ge=0, le=100)
    road_closure_time_s: float | None = Field(None, ge=0, le=43200)
    shelter_failures: list[tuple[int, float]] | None = None    # [(shelter_id, time_s)]
    duration_s: float | None = Field(None, ge=300, le=43200)

    @field_validator("disaster_type")
    @classmethod
    def _known(cls, v: str) -> str:
        if v not in DISASTER_PRESETS:
            raise ValueError(f"disaster_type must be one of {sorted(DISASTER_PRESETS)}")
        return v


class DisasterUpdateIn(BaseModel):
    intensity: float | None = Field(None, gt=0, le=1)
    spread_speed: float | None = Field(None, ge=0, le=20)
    max_radius: float | None = Field(None, gt=0, le=10000)