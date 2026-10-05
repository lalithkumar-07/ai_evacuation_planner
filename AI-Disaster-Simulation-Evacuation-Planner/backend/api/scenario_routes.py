from fastapi import APIRouter

from backend.api.dependencies import SessionId
from backend.schemas.scenario import ScenarioIn
from backend.services import scenario_service as svc

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])
meta_router = APIRouter(prefix="/api", tags=["scenarios"])


@meta_router.get("/meta")
def meta():
    """Option ranges, disaster presets, map bounds - used by the UI to build its controls."""
    return svc.meta()


@router.get("")
def list_all(sid: SessionId):
    return svc.list_for_session(sid)


@router.get("/{scenario_id}")
def get_one(scenario_id: str, sid: SessionId):
    return svc.describe_for_session(sid, scenario_id)


@router.post("", status_code=201)
def create(body: ScenarioIn, sid: SessionId):
    return svc.create_for_session(sid, body)