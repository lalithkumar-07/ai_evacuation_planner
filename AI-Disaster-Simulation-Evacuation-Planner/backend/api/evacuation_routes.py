from fastapi import APIRouter

from backend.api.dependencies import SessionId
from backend.schemas.evacuation import RoutePlanIn
from backend.services import simulation_service as svc

router = APIRouter(prefix="/api/evacuation", tags=["evacuation"])


@router.post("/plan")
def plan(sid: SessionId, body: RoutePlanIn = RoutePlanIn()):
    """Baseline (shortest) vs proposed (risk-aware) route + shelter for one origin, under current conditions."""
    return svc.plan(sid, body.lat, body.lon)


@router.post("/reroute")
def reroute(sid: SessionId):
    """Flag every active evacuee for re-planning at their next junction (proposed strategy only)."""
    return svc.reroute(sid)


@router.get("/shelters")
def shelters(sid: SessionId):
    return svc.shelters(sid)