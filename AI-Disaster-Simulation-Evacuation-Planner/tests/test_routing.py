import math
from dataclasses import replace

from config.settings import ROUTING_WEIGHTS, ScenarioConfig
from src.graph.graph_utils import path_stats
from src.routing.risk_aware_route import dynamic_cost
from src.routing.shortest_path import astar_path, shortest_path
from src.simulation.agent import Agent
from src.simulation.evacuation import BaselineStrategy, RiskAwareStrategy
from src.simulation.simulation_engine import Simulation


def _len(G, p):
    return sum(G[a][b]["distance"] for a, b in zip(p, p[1:]))


def test_astar_equals_dijkstra():
    G = Simulation(ScenarioConfig(), "baseline").G
    assert math.isclose(_len(G, shortest_path(G, 0, 255)), _len(G, astar_path(G, 0, 255)))


def test_dynamic_cost_penalises_risk_and_hides_blocked():
    G = Simulation(ScenarioConfig(disaster_enabled=False), "baseline").G
    u, v = next(iter(G.edges))
    e, f = G[u][v], dynamic_cost(ROUTING_WEIGHTS)
    base = f(u, v, e)
    e["risk"] = 0.5
    assert f(u, v, e) > base
    e["status"] = "BLOCKED"
    assert f(u, v, e) is None


def test_proposed_route_is_safer_than_baseline_for_exposed_origin():
    from backend.services.evacuation_service import plan
    sim = Simulation(ScenarioConfig(), "proposed")
    p = plan(sim, None, None)
    assert p["proposed"]["stats"]["avg_risk"] <= p["baseline"]["stats"]["avg_risk"]
    assert p["proposed"]["stats"]["blocked_roads"] == 0


def test_proposed_never_routes_over_blocked_roads():
    sim = Simulation(ScenarioConfig(), "proposed")
    probe = Agent(-1, 0, 25, "vehicle", 0, True, 0, node=0)
    for origin in range(0, 256, 17):
        probe.node = origin
        res = RiskAwareStrategy(ROUTING_WEIGHTS).assign(sim.ctrl, probe)
        if res:
            assert path_stats(sim.G, res[1])["blocked_roads"] == 0


def test_baseline_ignores_hazard():
    sim = Simulation(ScenarioConfig(), "baseline")
    probe = Agent(-1, 0, 25, "vehicle", 0, True, 0, node=136)
    sid, route = BaselineStrategy().assign(sim.ctrl, probe)
    assert route[0] == 136 and route[-1] == sim.shelters[sid].node
