from fastapi import APIRouter

from backend.schemas.evacuation import RoutePlanIn
from backend.services import evacuation_service as svc
from backend.services import simulation_service as simsvc

router = APIRouter(prefix="/api/evacuation", tags=["evacuation"])


@router.post("/plan")
def plan(body: RoutePlanIn = RoutePlanIn()):
    """Baseline (shortest) vs proposed (risk-aware) route + shelter for one origin, under current conditions."""
    return svc.plan(simsvc.require(), body.lat, body.lon)


@router.post("/reroute")
def reroute():
    """Flag every active evacuee for re-planning at their next junction (proposed strategy only)."""
    return {"flagged": simsvc.require().ctrl.force_reroute_all()}


@router.get("/shelters")
def shelters():
    return simsvc.state(simsvc.require())["shelters"]
