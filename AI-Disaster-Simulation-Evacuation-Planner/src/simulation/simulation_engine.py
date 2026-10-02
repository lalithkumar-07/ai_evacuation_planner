"""Discrete-time simulation loop with the dynamic feedback cycle:
hazard -> risk -> road state -> route check -> agent movement -> traffic load -> metrics."""
from __future__ import annotations

import logging

from config.settings import (RISK_FUNCTION, RISK_THRESHOLDS, ROUTING_WEIGHTS, SIM, RoutingWeights,
                             ScenarioConfig)
from src.ai.prediction import DeterministicForecastPredictor, RiskPredictor
from src.data.data_loader import build_scenario
from src.disaster.disaster_manager import DisasterManager
from src.disaster.risk_calculator import get_risk_function, risk_level
from src.graph.road_graph import refresh_edge_states
from src.routing.shelter_assignment import ShelterStatus
from src.simulation.agent import AgentStatus as S
from src.simulation.evacuation import EvacuationController, Strategy, make_strategy

log = logging.getLogger(__name__)


class Simulation:
    def __init__(self, cfg: ScenarioConfig, strategy: str | Strategy = "proposed", dataset: dict | None = None,
                 weights: RoutingWeights | None = None, predictor: RiskPredictor | None = None) -> None:
        self.cfg = cfg
        weights = weights or ROUTING_WEIGHTS
        sc = build_scenario(cfg, dataset)
        self.G, self.shelters, self.agents, self.center = sc.G, sc.shelters, sc.agents, sc.center
        strat = make_strategy(strategy, weights) if isinstance(strategy, str) else strategy
        self.ctrl = EvacuationController(self.G, self.shelters, self.agents, strat, weights, cfg.trap_timeout_s)
        people: dict[int, int] = {}
        for a in self.agents:
            people[a.origin] = people.get(a.origin, 0) + a.size
        peak = max(people.values())
        self.manager = DisasterManager(sc.disaster, predictor or DeterministicForecastPredictor(SIM.forecast_horizon_s),
                                       get_risk_function(RISK_FUNCTION), sc.closures, cfg.shelter_failures,
                                       {n: p / peak for n, p in people.items()})
        self.t = 0.0
        self.loads: dict[tuple[int, int], int] = {}
        self.history: list[dict] = []
        self.exposure_person_s = 0.0      # sum(hazard * seconds * people)
        self.person_s_in_hazard = 0.0     # person-seconds spent where hazard >= "restricted"
        self._update_environment()
        self._record()

    # convenience accessors
    @property
    def strategy(self) -> Strategy:
        return self.ctrl.strategy

    @property
    def disaster(self):
        return self.manager.disaster

    @property
    def reserved(self):
        return self.ctrl.reserved

    @property
    def reroute_count(self) -> int:
        return self.ctrl.reroute_count

    @property
    def route_failures(self) -> int:
        return self.ctrl.route_failures

    @property
    def ordered_people(self) -> int:
        return sum(a.size for a in self.agents if a.ordered)

    @property
    def finished(self) -> bool:
        return self.t >= self.cfg.duration_s or all(a.status == S.AT_SHELTER for a in self.agents if a.ordered)

    # ---- main loop -------------------------------------------------------------
    def step(self) -> dict:
        self.t += self.cfg.dt_s
        self._update_environment()
        self.ctrl.flag_routes()
        self.ctrl.start_due(self.t)
        self.ctrl.advance(self.t, self.cfg.dt_s)
        self._accumulate_exposure()
        self._recompute_loads()
        return self._record()

    def run(self) -> None:
        while not self.finished:
            self.step()
        log.info("finished strategy=%s t=%.0fs", self.strategy.name, self.t)

    def update_disaster(self, **params) -> None:
        self.manager.update_parameters(**params)
        self._update_environment()

    # ---- internals -------------------------------------------------------------
    def _update_environment(self) -> None:
        self.manager.update(self.G, self.t)
        refresh_edge_states(self.G, RISK_THRESHOLDS, self.loads)
        for s in self.shelters:
            s.forced_unsafe = s.forced_unsafe or self.manager.shelter_failed(s.id, self.t)
            s.risk = self.G.nodes[s.node]["risk"]
            if s.forced_unsafe or self.G.nodes[s.node]["hazard"] >= RISK_THRESHOLDS.blocked:
                s.status = ShelterStatus.UNSAFE
            elif s.occupancy >= s.capacity:
                s.status = ShelterStatus.FULL
            else:
                s.status = ShelterStatus.ACTIVE
        self.ctrl.invalidate_dynamic()

    def _local(self, a) -> dict:
        return self.G[a.node][a.next_node] if a.next_node is not None else self.G.nodes[a.node]

    def _accumulate_exposure(self) -> None:
        dt = self.cfg.dt_s
        for a in self.agents:
            h = self._local(a)["hazard"]
            a.risk_exposure += h * dt
            self.exposure_person_s += h * dt * a.size
            if h >= RISK_THRESHOLDS.restricted:
                self.person_s_in_hazard += dt * a.size

    def _recompute_loads(self) -> None:
        self.loads = {}
        for a in self.agents:
            if a.next_node is not None and a.status in (S.TRAVELING, S.REROUTING, S.WAITING, S.TRAPPED):
                k = (a.node, a.next_node)
                self.loads[k] = self.loads.get(k, 0) + a.size

    def _record(self) -> dict:
        people = {st: 0 for st in S}
        at_risk, peak_risk = 0, 0.0
        for a in self.agents:
            people[a.status] += a.size
            if a.ordered and a.status != S.AT_SHELTER:
                loc = self._local(a)
                peak_risk = max(peak_risk, loc["risk"])
                if loc["hazard"] >= RISK_THRESHOLDS.restricted:
                    at_risk += a.size
        ratios = [ld / self.G[u][v]["capacity"] for (u, v), ld in self.loads.items()]
        rec = {
            "t": self.t,
            "total_population": sum(a.size for a in self.agents),
            "ordered": self.ordered_people,
            "evacuated": people[S.AT_SHELTER],
            "remaining": self.ordered_people - people[S.AT_SHELTER],
            "traveling": people[S.TRAVELING] + people[S.REROUTING],
            "waiting": people[S.WAITING], "trapped": people[S.TRAPPED], "at_home": people[S.AT_HOME],
            "affected": sum(a.size for a in self.agents
                            if self.G.nodes[a.origin]["hazard"] >= RISK_THRESHOLDS.restricted),
            "at_risk": at_risk,
            "peak_risk": round(peak_risk, 3), "risk_level": risk_level(peak_risk),
            "exposure": self.exposure_person_s,
            "blocked_roads": sum(1 for u, v, e in self.G.edges(data=True) if u < v and e["status"] == "BLOCKED"),
            "congestion_mean": sum(ratios) / len(ratios) if ratios else 0.0,
            "congestion_peak": max(ratios) if ratios else 0.0,
            "shelters_active": sum(1 for s in self.shelters if s.status == ShelterStatus.ACTIVE),
            "shelter_capacity_left": sum(s.remaining_capacity for s in self.shelters
                                         if s.status != ShelterStatus.UNSAFE),
            "reroutes": self.reroute_count, "route_failures": self.route_failures,
        }
        self.history.append(rec)
        return rec
