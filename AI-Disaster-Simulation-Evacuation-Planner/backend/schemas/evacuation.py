from __future__ import annotations

from pydantic import BaseModel, Field


class RoutePlanIn(BaseModel):
    """Origin as lat/lon (e.g. a map click). Omit both to use the most exposed populated node."""
    lat: float | None = Field(None, ge=-90, le=90)
    lon: float | None = Field(None, ge=-180, le=180)


class StartIn(BaseModel):
    scenario_id: str = "expanding"
    strategy: str = Field("proposed", pattern="^(baseline|proposed)$")


class StepIn(BaseModel):
    steps: int = Field(1, ge=1, le=200)
