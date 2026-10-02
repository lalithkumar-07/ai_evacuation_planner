from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from src.disaster.hazard_model import DISASTER_PRESETS


class DisasterStartIn(BaseModel):
    """Step 1 of the demo: pick a disaster and generate the scenario."""
    disaster_type: str = "flood"
    intensity: float = Field(0.9, gt=0, le=1)
    scenario_id: str = "expanding"          # preset to build on
    strategy: str = Field("proposed", pattern="^(baseline|proposed)$")

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
