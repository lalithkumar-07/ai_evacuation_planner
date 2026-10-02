from fastapi import APIRouter

from backend.schemas.evacuation import StartIn, StepIn
from backend.services import scenario_service as scen
from backend.services import simulation_service as svc
from src.simulation.metrics import summarize

router = APIRouter(prefix="/api", tags=["simulation"])


@router.post("/simulation/start")
def start(body: StartIn):
    sim = svc.start(scen.get_scenario(body.scenario_id), body.strategy)
    return {"layers": scen.layers(sim), "state": svc.state(sim)}


@router.post("/simulation/step")
def step(body: StepIn = StepIn()):
    return svc.step(body.steps)


@router.post("/simulation/pause")
def pause():
    svc.require()
    svc.S.paused = True
    return {"paused": True}


@router.post("/simulation/resume")
def resume():
    svc.require()
    svc.S.paused = False
    return {"paused": False}


@router.post("/simulation/reset")
def reset():
    return svc.state(svc.reset())


@router.get("/simulation/status")
def status():
    sim = svc.require()
    return {"scenario_id": svc.S.scenario_id, "strategy": svc.S.strategy, "paused": svc.S.paused,
            "time_s": sim.t, "finished": sim.finished, "latest": sim.history[-1]}


@router.get("/metrics")
def metrics():
    return summarize(svc.require())


@router.get("/analytics")
def analytics(scenario_id: str | None = None):
    """Baseline vs proposed on the same scenario (runs both; cached)."""
    cfg = scen.get_scenario(scenario_id or svc.S.scenario_id or "expanding")
    return svc.run_comparison(cfg)
