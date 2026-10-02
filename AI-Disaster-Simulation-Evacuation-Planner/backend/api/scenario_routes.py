from fastapi import APIRouter

from backend.schemas.scenario import ScenarioIn
from backend.services import scenario_service as svc

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


@router.get("")
def list_all():
    return svc.list_scenarios()


@router.get("/{scenario_id}")
def get_one(scenario_id: str):
    return svc.get_scenario(scenario_id).to_dict()


@router.post("", status_code=201)
def create(body: ScenarioIn):
    return svc.create_custom(body).to_dict()
