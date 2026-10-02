from fastapi import APIRouter

from backend.schemas.disaster import DisasterStartIn, DisasterUpdateIn
from backend.services import scenario_service as scen
from backend.services import simulation_service as simsvc
from backend.services.evacuation_service import plan

router = APIRouter(prefix="/api/disaster", tags=["disaster"])


@router.post("/start")
def start(body: DisasterStartIn):
    """Select disaster -> generate scenario. Returns static layers, initial state and a first route plan."""
    cfg = scen.live_from_disaster(body.disaster_type, body.intensity, body.scenario_id)
    sim = simsvc.start(cfg, body.strategy)
    return {"layers": scen.layers(sim), "state": simsvc.state(sim), "plan": plan(sim, None, None)}


@router.post("/update")
def update(body: DisasterUpdateIn):
    """Change the live disaster (intensity / spread / max radius) and refresh road + risk state."""
    sim = simsvc.require()
    sim.update_disaster(intensity=body.intensity, spread_speed=body.spread_speed, max_radius=body.max_radius)
    return simsvc.state(sim)


@router.get("/risk-map")
def risk_map():
    sim = simsvc.require()
    from src.disaster.risk_calculator import risk_level
    from src.utils.helpers import node_latlon
    return {"time_s": sim.t, "nodes": [{"latlon": node_latlon(sim.G, n), "hazard": round(d["hazard"], 3),
                                        "risk": round(d["risk"], 3), "level": risk_level(d["risk"])}
                                       for n, d in sorted(sim.G.nodes(data=True))]}


@router.get("/affected")
def affected():
    m = simsvc.require().history[-1]
    return {"affected": m["affected"], "at_risk": m["at_risk"], "risk_level": m["risk_level"]}
