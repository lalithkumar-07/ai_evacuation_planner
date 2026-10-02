"""Holds the live simulation session and serialises its state for the UI."""
from __future__ import annotations

import json
import logging

from backend.services.scenario_service import get_scenario
from config.settings import ScenarioConfig
from src.disaster.risk_calculator import risk_level
from src.graph.graph_utils import SEVERITY, undirected_edges
from src.simulation.metrics import summarize
from src.simulation.simulation_engine import Simulation
from src.utils.helpers import to_latlon

log = logging.getLogger(__name__)


class Conflict(RuntimeError):
    pass


class Session:
    sim: Simulation | None = None
    scenario_id = ""
    strategy = ""
    paused = False


S = Session()
_cache: dict[str, dict] = {}


def require() -> Simulation:
    if S.sim is None:
        raise Conflict("No scenario loaded. Generate one first (POST /api/disaster/start).")
    return S.sim


def start(cfg: ScenarioConfig, strategy: str) -> Simulation:
    S.sim, S.scenario_id, S.strategy, S.paused = Simulation(cfg, strategy), cfg.id, strategy, False
    return S.sim


def reset() -> Simulation:
    require()
    return start(get_scenario(S.scenario_id), S.strategy)


def step(n: int) -> dict:
    sim = require()
    if S.paused:
        raise Conflict("Simulation is paused")
    for _ in range(n):
        if sim.finished:
            break
        sim.step()
    return state(sim)


def _xy(sim, a) -> tuple[float, float]:
    n = sim.G.nodes[a.node]
    if a.next_node is None:
        return n["x"], n["y"]
    m, f = sim.G.nodes[a.next_node], a.progress / sim.G[a.node][a.next_node]["distance"]
    return n["x"] + (m["x"] - n["x"]) * f, n["y"] + (m["y"] - n["y"]) * f


def state(sim: Simulation) -> dict:
    G, ext, d = sim.G, sim.G.graph["extent"], sim.disaster
    roads = []
    for u, v in undirected_edges(G):
        worst = max((G[u][v], G[v][u]), key=lambda e: SEVERITY.index(e["status"]))
        roads.append([worst["status"], round(worst["risk"], 3)])
    return {
        "time_s": sim.t, "finished": sim.finished, "paused": S.paused, "strategy": sim.strategy.name,
        "metrics": sim.history[-1],
        "disaster": None if d is None else {"kind": d.kind, "center": to_latlon(d.cx, d.cy, ext),
                                           "radius_m": d.radius(sim.t), "intensity": d.intensity},
        "roads": roads,
        "node_risk": [round(G.nodes[n]["risk"], 3) for n in sorted(G.nodes)],
        "shelters": [{"id": s.id, "latlon": to_latlon(s.x, s.y, ext), "capacity": s.capacity,
                      "occupancy": s.occupancy, "available": s.remaining_capacity,
                      "status": s.status.value, "risk": round(s.risk, 3), "risk_level": risk_level(s.risk)}
                     for s in sim.shelters],
        "agents": [[*to_latlon(*_xy(sim, a), ext), a.status.value, a.size] for a in sim.agents],
    }


def run_comparison(cfg: ScenarioConfig) -> dict:
    """Run baseline and proposed on identical inputs; cached per config."""
    key = json.dumps(cfg.to_dict(), sort_keys=True)
    if key not in _cache:
        out = {}
        for name in ("baseline", "proposed"):
            sim = Simulation(cfg, name)
            sim.run()
            out[name] = {"summary": summarize(sim), "series": sim.history}
        _cache[key] = out
    return _cache[key]
