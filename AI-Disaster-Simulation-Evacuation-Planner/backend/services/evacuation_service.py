"""Route planning for the demo: baseline route vs proposed route for one origin."""
from __future__ import annotations

from config.settings import ROUTING_WEIGHTS
from src.graph.graph_utils import path_stats
from src.simulation.agent import Agent
from src.simulation.evacuation import BaselineStrategy, RiskAwareStrategy
from src.utils.helpers import nearest_node, node_latlon


def _most_exposed_origin(sim) -> int:
    """Populated, ordered node whose *baseline* route carries the most distance-weighted risk."""
    base, best, best_score = BaselineStrategy(), None, -1.0
    seen = set()
    for a in sim.agents:
        if not a.ordered or a.origin in seen:
            continue
        seen.add(a.origin)
        res = base.assign(sim.ctrl, Agent(-1, a.origin, 1, "vehicle", 0, True, 0, node=a.origin))
        if res:
            st = path_stats(sim.G, res[1])
            score = st["avg_risk"] * st["distance_m"]
            if score > best_score:
                best, best_score = a.origin, score
    return best if best is not None else sim.agents[0].origin


def plan(sim, lat: float | None, lon: float | None) -> dict:
    G = sim.G
    origin = nearest_node(G, lat, lon) if lat is not None and lon is not None else _most_exposed_origin(sim)
    probe = Agent(-1, origin, 25, "vehicle", 0.0, True, 0.0, node=origin)
    out = {"origin": {"node": origin, "latlon": node_latlon(G, origin)}, "time_s": sim.t}
    for label, strat in (("baseline", BaselineStrategy()), ("proposed", RiskAwareStrategy(ROUTING_WEIGHTS))):
        res = strat.assign(sim.ctrl, probe)
        if res is None:
            out[label] = None
            continue
        sid, path = res
        out[label] = {"shelter_id": sid, "path": [node_latlon(G, n) for n in path], "stats": path_stats(G, path)}
    return out
