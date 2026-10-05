from fastapi import APIRouter

from backend.api.dependencies import SessionId
from backend.schemas.disaster import DisasterStartIn, DisasterUpdateIn
from backend.services import simulation_service as svc

router = APIRouter(prefix="/api/disaster", tags=["disaster"])


@router.post("/start")
def start(body: DisasterStartIn, sid: SessionId):
    """Select disaster -> generate scenario. Returns static layers, initial state and a first route plan."""
    return svc.generate(sid, body)


@router.post("/update")
def update(body: DisasterUpdateIn, sid: SessionId):
    """Change the live disaster (intensity / spread / max radius) and refresh road + risk state."""
    return svc.update_disaster(sid, intensity=body.intensity, spread_speed=body.spread_speed, max_radius=body.max_radius)


@router.get("/risk-map")
def risk_map(sid: SessionId):
    return svc.risk_map(sid)


@router.get("/affected")
def affected(sid: SessionId):
    return svc.affected(sid)