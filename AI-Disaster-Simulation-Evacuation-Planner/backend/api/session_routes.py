from fastapi import APIRouter

from backend.api.dependencies import SessionId
from backend.services import simulation_service as svc

router = APIRouter(prefix="/api/session", tags=["session"])


@router.get("")
def info(sid: SessionId):
    """Who am I, and what is stored for me? (Does not create a session.)"""
    return svc.session_info(sid)


@router.delete("")
def end(sid: SessionId):
    """Discard my simulation and custom scenarios now instead of waiting for the idle timeout."""
    return svc.end_session(sid)