"""Evacuation logic: strategies (baseline vs proposed) and the controller that moves agents,
detects broken routes and reroutes. Lifecycle: AT_HOME -> TRAVELING -> (REROUTING) -> AT_SHELTER."""
from __future__ import annotations

from abc import ABC, abstractmethod

import networkx as nx

from config.settings import RoutingWeights
from src.routing.risk_aware_route import dynamic_cost, single_source_risk_aware
from src.routing.shelter_assignment import Shelter, ShelterStatus, assign_best, assign_nearest
from src.routing.shortest_path import single_source_distance
from src.simulation.agent import Agent
from src.simulation.agent import AgentStatus as S

MOVING = (S.TRAVELING, S.WAITING, S.TRAPPED, S.REROUTING)


class Strategy(ABC):
    name: str
    dynamic: bool

    @abstractmethod
    def assign(self, ctrl: "EvacuationController", agent: Agent) -> tuple[int, list[int]] | None: ...


class BaselineStrategy(Strategy):
    """Nearest shelter + shortest path by distance. Static: no rerouting."""
    name, dynamic = "baseline", False

    def assign(self, ctrl, agent):
        dist, paths = ctrl.static_paths(agent.node)
        return assign_nearest(ctrl.shelters, dist, paths)


class RiskAwareStrategy(Strategy):
    """Risk/traffic-aware route + capacity-aware shelter choice + dynamic rerouting."""
    name, dynamic = "proposed", True

    def __init__(self, weights: RoutingWeights) -> None:
        self.w = weights

    def assign(self, ctrl, agent):
        dist, paths = ctrl.dynamic_paths(agent.node)
        return assign_best(ctrl.shelters, dist, paths, agent.size, ctrl.reserved, agent.destination, self.w)


def make_strategy(name: str, weights: RoutingWeights) -> Strategy:
    if name == "baseline":
        return BaselineStrategy()
    if name == "proposed":
        return RiskAwareStrategy(weights)
    raise ValueError(f"Unknown strategy '{name}'")


class EvacuationController:
    def __init__(self, G: nx.DiGraph, shelters: list[Shelter], agents: list[Agent], strategy: Strategy,
                 weights: RoutingWeights, trap_timeout_s: float) -> None:
        self.G, self.shelters, self.agents, self.strategy = G, shelters, agents, strategy
        self.trap_timeout_s = trap_timeout_s
        self.reserved = {s.id: 0 for s in shelters}
        self.reroute_count = 0
        self.route_failures = 0
        self.t = 0.0
        self._static: dict[int, tuple] = {}
        self._dyn: dict[int, tuple] = {}
        self._cost = dynamic_cost(weights)

    # cached path trees: static never changes; dynamic is cleared whenever the environment updates
    def static_paths(self, node: int):
        if node not in self._static:
            self._static[node] = single_source_distance(self.G, node)
        return self._static[node]

    def dynamic_paths(self, node: int):
        if node not in self._dyn:
            self._dyn[node] = single_source_risk_aware(self.G, node, self._cost)
        return self._dyn[node]

    def invalidate_dynamic(self) -> None:
        self._dyn.clear()

    # ---- per-step operations -------------------------------------------------
    def flag_routes(self) -> None:
        """Mark routes whose road is blocked / shelter unusable (failure) or passes dangerous roads."""
        for a in self.agents:
            if a.status not in MOVING or a.destination is None:
                continue
            s = self.shelters[a.destination]
            broken = s.status == ShelterStatus.UNSAFE or s.occupancy + a.size > s.capacity
            danger = False
            for i in range(1 if a.next_node is not None else 0, len(a.route) - 1):
                st = self.G[a.route[i]][a.route[i + 1]]["status"]
                broken |= st == "BLOCKED"
                danger |= st == "DANGEROUS"
            if broken and not a.failure_counted:
                a.failure_counted = True
                self.route_failures += 1
            if self.strategy.dynamic and (broken or danger):
                a.needs_reroute = True

    def force_reroute_all(self) -> int:
        n = 0
        if self.strategy.dynamic:
            for a in self.agents:
                if a.status in MOVING and a.destination is not None:
                    a.needs_reroute, n = True, n + 1
        return n

    def start_due(self, t: float) -> None:
        for a in self.agents:
            if a.status == S.AT_HOME and t >= a.start_at:
                a.status = S.TRAVELING

    def advance(self, t: float, dt: float) -> None:
        self.t = t
        for a in self.agents:
            if a.status in MOVING:
                self._advance(a, dt)

    # ---- agent mechanics -----------------------------------------------------
    def _set_route(self, a: Agent, sid: int, route: list[int]) -> None:
        if a.destination is not None:
            self.reserved[a.destination] -= a.size
        self.reserved[sid] += a.size
        a.destination, a.route = sid, list(route)
        a.needs_reroute = a.failure_counted = False

    def _next_ok(self, a: Agent) -> bool:
        return (len(a.route) >= 2 and self.G.has_edge(a.node, a.route[1])
                and self.G[a.node][a.route[1]]["status"] != "BLOCKED")

    def _wait(self, a: Agent, seconds: float) -> None:
        a.wait_s += seconds
        a.status = S.TRAPPED if a.wait_s > self.trap_timeout_s else S.WAITING

    def _advance(self, a: Agent, dt: float) -> None:
        budget, guard = dt, 0
        while budget > 1e-9 and guard < 200:
            guard += 1
            if a.next_node is None:
                if a.destination is None:
                    res = self.strategy.assign(self, a)
                    if res is None:
                        self._wait(a, budget)
                        return
                    self._set_route(a, *res)
                outcome = self._at_node(a)
                if outcome == "done":
                    return
                if outcome == "wait":
                    self._wait(a, budget)
                    return
            e = self.G[a.node][a.next_node]
            speed = e["speed_walk"] if a.mobility == "walking" else e["speed_vehicle"]
            need = (e["distance"] - a.progress) / speed
            if need <= budget:
                budget -= need
                a.node, a.next_node, a.progress = a.next_node, None, 0.0
                a.route.pop(0)
            else:
                a.progress += speed * budget
                budget = 0.0

    def _at_node(self, a: Agent, depth: int = 0) -> str:
        """'done' (entered shelter) | 'go' (next_node set) | 'wait'."""
        s = self.shelters[a.destination]
        if a.node == s.node:
            if s.can_accept(a.size):
                s.occupancy += a.size
                self.reserved[s.id] -= a.size
                a.status, a.end_at = S.AT_SHELTER, self.t
                return "done"
            return self._handle_failure(a, depth)
        if self._next_ok(a) and not a.needs_reroute:
            a.next_node, a.status = a.route[1], S.TRAVELING
            return "go"
        return self._handle_failure(a, depth)

    def _handle_failure(self, a: Agent, depth: int) -> str:
        if not self.strategy.dynamic or depth >= 2:
            return "wait"
        old, a.status = tuple(a.route), S.REROUTING
        res = self.strategy.assign(self, a)
        if res is None:
            a.needs_reroute = False
            if a.node != self.shelters[a.destination].node and self._next_ok(a):
                a.next_node, a.status = a.route[1], S.TRAVELING   # nothing better: keep going
                return "go"
            return "wait"
        self._set_route(a, *res)
        if tuple(a.route) != old:
            a.reroutes += 1
            self.reroute_count += 1
        return self._at_node(a, depth + 1)
