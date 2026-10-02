"""Scenario catalogue (7 predefined + custom/live) and the static map layers for a running sim."""
from __future__ import annotations

from dataclasses import replace

from backend.schemas.scenario import ScenarioIn
from config.settings import RISK_LEVELS, ScenarioConfig
from src.graph.graph_utils import undirected_edges
from src.utils.helpers import node_latlon


class NotFound(LookupError):
    pass


_b = ScenarioConfig()
SCENARIOS: dict[str, ScenarioConfig] = {c.id: c for c in [
    replace(_b, id="normal", name="1. Normal conditions", disaster_enabled=False,
            description="No hazard. Precautionary drill: measures pure traffic behaviour."),
    replace(_b, id="static", name="2. Static disaster", initial_radius_m=1500, max_radius_m=1500,
            spread_speed_mps=0.0, description="Hazard fixed at 1.5 km radius."),
    replace(_b, id="expanding", name="3. Expanding disaster",
            description="Hazard spreads outward over time (preset values for the chosen disaster type)."),
    replace(_b, id="road_failure", name="4. Road failure", initial_radius_m=1500, max_radius_m=1500,
            spread_speed_mps=0.0, road_closure_count=14, description="Static hazard + 14 roads closed at t=5 min."),
    replace(_b, id="shelter_failure", name="5. Shelter failure", shelter_failures=[[0, 900], [1, 1500]],
            description="Expanding hazard; shelters 0 and 1 become unsafe at t=15 and t=25 min."),
    replace(_b, id="high_density", name="6. High population density", population_scale=20000 / 6000,
            shelter_capacity_scale=20000 / 6000, description="Expanding hazard, ~20,000 people."),
    replace(_b, id="combined", name="7. Combined failure", population_scale=2.0, shelter_capacity_scale=1.2,
            road_closure_count=10, shelter_failures=[[0, 1200]],
            description="Expanding hazard + 10 road closures + shelter failure + tight capacity."),
]}


def list_scenarios() -> list[dict]:
    return [{"id": c.id, "name": c.name, "description": c.description} for c in SCENARIOS.values()]


def get_scenario(sid: str) -> ScenarioConfig:
    if sid not in SCENARIOS:
        raise NotFound(f"Unknown scenario '{sid}'")
    return SCENARIOS[sid]


def create_custom(body: ScenarioIn) -> ScenarioConfig:
    sid = f"custom-{len(SCENARIOS) + 1}"
    data = body.model_dump()
    data["shelter_failures"] = [list(x) for x in body.shelter_failures]
    SCENARIOS[sid] = ScenarioConfig(id=sid, **data)
    return SCENARIOS[sid]


def live_from_disaster(disaster_type: str, intensity: float, base_id: str) -> ScenarioConfig:
    """Preset + the user's disaster choice, stored as scenario 'live'."""
    base = get_scenario(base_id)
    SCENARIOS["live"] = replace(base, id="live", name=f"Live: {disaster_type} ({base.name})",
                                disaster_type=disaster_type, intensity=intensity)
    return SCENARIOS["live"]


def layers(sim) -> dict:
    """Static layers drawn once: roads, nodes (risk map points), population, shelters."""
    G = sim.G
    pop: dict[int, int] = {}
    for a in sim.agents:
        pop[a.origin] = pop.get(a.origin, 0) + a.size
    return {
        "synthetic": True,
        "scenario": sim.cfg.to_dict(),
        "risk_levels": {"medium": RISK_LEVELS.medium, "high": RISK_LEVELS.high, "critical": RISK_LEVELS.critical},
        "roads": [{"a": node_latlon(G, u), "b": node_latlon(G, v), "arterial": G[u][v]["arterial"]}
                  for u, v in undirected_edges(G)],
        "nodes": [node_latlon(G, n) for n in sorted(G.nodes)],
        "population": [{"latlon": node_latlon(G, n), "people": p, "ordered": any(
            a.ordered for a in sim.agents if a.origin == n)} for n, p in pop.items()],
    }
