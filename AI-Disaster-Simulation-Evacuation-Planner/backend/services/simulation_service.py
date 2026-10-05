"""Session-bound simulation operations. Every public function takes the caller's session id, runs under that
session's lock, and returns a JSON-ready dict. Routes call these; they contain no logic of their own."""
from __future__ import annotations

import json
import logging
import threading
from collections import OrderedDict

from backend.schemas.disaster import DisasterStartIn
from backend.services import evacuation_service
from backend.services import scenario_service as scen
from backend.services.session_store import STORE, SessionData
from config.settings import ANALYTICS_CACHE_SIZE, ScenarioConfig
from src.disaster.risk_calculator import risk_level
from src.graph.graph_utils import SEVERITY, undirected_edges
from src.simulation.metrics import summarize
from src.simulation.simulation_engine import Simulation
from src.utils.helpers import node_latlon, to_latlon

log = logging.getLogger(__name__)


class Conflict(RuntimeError):
    pass


def _require(s: SessionData) -> Simulation:
    if s.sim is None:
        raise Conflict("No scenario loaded in this session. Generate one first (POST /api/disaster/start).")
    return s.sim


def _start(s: SessionData, cfg: ScenarioConfig, strategy: str) -> Simulation:
    s.sim, s.cfg, s.strategy, s.paused = Simulation(cfg, strategy), cfg, strategy, False
    return s.sim


# ---- serialisation -----------------------------------------------------------------------------------
def _xy(sim: Simulation, a) -> tuple[float, float]:
    n = sim.G.nodes[a.node]
    if a.next_node is None:
        return n["x"], n["y"]
    m, f = sim.G.nodes[a.next_node], a.progress / sim.G[a.node][a.next_node]["distance"]
    return n["x"] + (m["x"] - n["x"]) * f, n["y"] + (m["y"] - n["y"]) * f


def state(sim: Simulation, paused: bool = False) -> dict:
    G, ext, d = sim.G, sim.G.graph["extent"], sim.disaster
    roads = []
    for u, v in undirected_edges(G):
        worst = max((G[u][v], G[v][u]), key=lambda e: SEVERITY.index(e["status"]))
        roads.append([worst["status"], round(worst["risk"], 3)])
    return {
        "time_s": sim.t, "finished": sim.finished, "paused": paused, "strategy": sim.strategy.name,
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


# ---- starting / controlling ----------------------------------------------------------------------------
def start_scenario(sid: str, scenario_id: str, strategy: str) -> dict:
    with STORE.session(sid) as s:
        sim = _start(s, scen.get_scenario(scenario_id, s), strategy)
        return {"layers": scen.layers(sim), "state": state(sim, s.paused)}


def generate(sid: str, body: DisasterStartIn) -> dict:
    """Select disaster -> generate scenario: layers + initial state + first route plan."""
    with STORE.session(sid) as s:
        cfg = scen.live_from_request(body, s)
        sim = _start(s, cfg, body.strategy)
        return {"layers": scen.layers(sim), "state": state(sim, s.paused),
                "plan": evacuation_service.plan(sim, None, None)}


def step(sid: str, n: int) -> dict:
    with STORE.existing(sid) as s:
        sim = _require(s)
        if s.paused:
            raise Conflict("Simulation is paused")
        for _ in range(n):
            if sim.finished:
                break
            sim.step()
        return state(sim, s.paused)


def set_paused(sid: str, paused: bool) -> dict:
    with STORE.existing(sid) as s:
        _require(s)
        s.paused = paused
        return {"paused": paused}


def reset(sid: str) -> dict:
    with STORE.existing(sid) as s:
        _require(s)
        sim = _start(s, s.cfg, s.strategy)
        return state(sim, s.paused)


def update_disaster(sid: str, **params) -> dict:
    with STORE.existing(sid) as s:
        sim = _require(s)
        sim.update_disaster(**params)
        return state(sim, s.paused)


# ---- read-only views of the caller's simulation ------------------------------------------------------------
def status(sid: str) -> dict:
    with STORE.existing(sid) as s:
        sim = _require(s)
        return {"scenario_id": s.cfg.id, "strategy": s.strategy, "paused": s.paused, "time_s": sim.t,
                "finished": sim.finished, "latest": sim.history[-1]}


def metrics(sid: str) -> dict:
    with STORE.existing(sid) as s:
        return summarize(_require(s))


def risk_map(sid: str) -> dict:
    with STORE.existing(sid) as s:
        sim = _require(s)
        return {"time_s": sim.t, "nodes": [
            {"latlon": node_latlon(sim.G, n), "hazard": round(d["hazard"], 3), "risk": round(d["risk"], 3),
             "level": risk_level(d["risk"])} for n, d in sorted(sim.G.nodes(data=True))]}


def affected(sid: str) -> dict:
    with STORE.existing(sid) as s:
        m = _require(s).history[-1]
        return {"affected": m["affected"], "at_risk": m["at_risk"], "risk_level": m["risk_level"]}


def shelters(sid: str) -> list[dict]:
    with STORE.existing(sid) as s:
        return state(_require(s), s.paused)["shelters"]


def plan(sid: str, lat: float | None, lon: float | None) -> dict:
    with STORE.existing(sid) as s:
        return evacuation_service.plan(_require(s), lat, lon)


def reroute(sid: str) -> dict:
    with STORE.existing(sid) as s:
        return {"flagged": _require(s).ctrl.force_reroute_all()}


# ---- session endpoints -----------------------------------------------------------------------------------------
def session_info(sid: str) -> dict:
    s = STORE.peek(sid)
    out = {"session_id": sid, "exists": s is not None, **STORE.stats()}
    if s is not None:
        with s.lock:
            now = STORE.now()
            out.update({"age_s": round(now - s.created_at, 1), "idle_s": round(now - s.last_used, 1),
                        "has_simulation": s.sim is not None, "strategy": s.strategy or None,
                        "scenario_id": s.cfg.id if s.cfg else None, "paused": s.paused,
                        "time_s": s.sim.t if s.sim else None, "custom_scenarios": sorted(s.custom_scenarios)})
    return out


def end_session(sid: str) -> dict:
    return {"deleted": STORE.delete(sid)}


# ---- baseline-vs-proposed analytics (pure function of the config, so the cache is shared across sessions) ----
_cache: OrderedDict[str, dict] = OrderedDict()
_cache_lock = threading.Lock()


def _cache_key(cfg: ScenarioConfig) -> str:
    d = {k: v for k, v in cfg.to_dict().items() if k not in ("id", "name", "description")}
    return json.dumps(d, sort_keys=True)


def run_comparison(cfg: ScenarioConfig) -> dict:
    """Run both strategies on identical inputs. Bounded LRU cache; treat the returned dict as read-only."""
    key = _cache_key(cfg)
    with _cache_lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    out = {}
    for name in ("baseline", "proposed"):
        sim = Simulation(cfg, name)
        sim.run()
        out[name] = {"summary": summarize(sim), "series": sim.history}
    with _cache_lock:
        _cache[key] = out
        _cache.move_to_end(key)
        while len(_cache) > ANALYTICS_CACHE_SIZE:
            _cache.popitem(last=False)
    return out


def analytics(sid: str, scenario_id: str | None) -> dict:
    with STORE.existing(sid) as s:                       # resolve the config under the lock...
        cfg = scen.get_scenario(scenario_id, s) if scenario_id else (s.cfg or scen.PRESETS["expanding"])
    return run_comparison(cfg)                           # ...but run the (slow) comparison outside it