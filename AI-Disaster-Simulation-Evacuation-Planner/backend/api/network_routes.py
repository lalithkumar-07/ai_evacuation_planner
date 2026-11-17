from typing import Literal

from fastapi import APIRouter, Query

from backend.api.dependencies import SessionId
from backend.services import scenario_service as scen
from backend.services import simulation_service as svc

router = APIRouter(prefix="/api/network", tags=["network"])


@router.get("/summary")
def summary():
    """The active dataset's road network: roads, km, lanes, speeds, one-way share, per road class."""
    return scen.network_summary()


@router.get("/hotspots")
def hotspots(sid: SessionId, by: Literal["exposure", "congestion", "risk"] = "exposure",
             limit: int = Query(10, ge=1, le=100)):
    """Where people were most exposed to hazard (cumulative), or where traffic / risk is worst right now."""
    return svc.hotspots(sid, by, limit)