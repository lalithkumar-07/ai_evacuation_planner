from fastapi import APIRouter

from backend.api.dependencies import SessionId
from backend.schemas.evacuation import StartIn, StepIn
from backend.services import simulation_service as svc

router = APIRouter(prefix="/api", tags=["simulation"])


@router.post("/simulation/start")
def start(body: StartIn, sid: SessionId):
    return svc.start_scenario(sid, body.scenario_id, body.strategy)


@router.post("/simulation/step")
def step(sid: SessionId, body: StepIn = StepIn()):
    return svc.step(sid, body.steps)


@router.post("/simulation/pause")
def pause(sid: SessionId):
    return svc.set_paused(sid, True)


@router.post("/simulation/resume")
def resume(sid: SessionId):
    return svc.set_paused(sid, False)


@router.post("/simulation/reset")
def reset(sid: SessionId):
    return svc.reset(sid)


@router.get("/simulation/status")
def status(sid: SessionId):
    return svc.status(sid)


@router.get("/metrics")
def metrics(sid: SessionId):
    return svc.metrics(sid)


@router.get("/analytics")
def analytics(sid: SessionId, scenario_id: str | None = None):
    """Baseline vs proposed on the same scenario (runs both; cached)."""
    return svc.analytics(sid, scenario_id)