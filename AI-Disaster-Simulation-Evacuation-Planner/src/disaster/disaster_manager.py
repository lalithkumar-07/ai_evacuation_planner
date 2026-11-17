"""Owns the disaster over time: writes hazard + risk onto the graph, applies closures/shelter failures."""
from __future__ import annotations

import networkx as nx

from src.ai.prediction import RiskPredictor
from src.disaster.hazard_model import Disaster
from src.disaster.risk_calculator import RiskFn
from src.graph.graph_utils import road_edges


class DisasterManager:
    def __init__(self, disaster: Disaster | None, predictor: RiskPredictor, risk_fn: RiskFn,
                 closures: list[tuple[int, int, float]], shelter_failures: list[list[float]],
                 exposure: dict[int, float]) -> None:
        self.disaster, self.predictor, self.risk_fn = disaster, predictor, risk_fn
        self.closures, self.shelter_failures, self.exposure = closures, shelter_failures, exposure
        self._last_key, self._last_graph = None, None

    def _hz(self, x: float, y: float, t: float) -> tuple[float, float]:
        h = self.disaster.hazard_at(x, y, t) if self.disaster else 0.0
        return h, self.predictor.predict_hazard(self.disaster, x, y, t)

    def _field_key(self, t: float):
        """Identifies the hazard field at time t; None means 'cannot tell, always recompute'."""
        if self.disaster is None:
            return ("no disaster",)
        sig = getattr(self.predictor, "signature", None)
        if sig is None:
            return None
        return (self.disaster, self.disaster.state_key(t), sig(self.disaster, t))

    def update(self, G: nx.DiGraph, t: float) -> None:
        """Set hazard/risk on every node and edge for time t, and apply scheduled road closures."""
        for u, v, tc in self.closures:
            if t >= tc:
                for e in road_edges(G, u, v):                       # one edge for a one-way road, two otherwise
                    e["forced_closed"] = True
        key = self._field_key(t)
        if key is not None and key == self._last_key and G is self._last_graph:
            return                                                  # hazard field unchanged: nothing to recompute
        self._last_key, self._last_graph = key, G

        for n, d in G.nodes(data=True):
            h, p = self._hz(d["x"], d["y"], t)
            d["hazard"], d["pred"] = h, p
            d["risk"] = self.risk_fn({"hazard": h, "predicted": p, "exposure": self.exposure.get(n, 0.0)})
        memo: dict[tuple[int, int], tuple[float, float]] = {}       # both directions of a road share hazard and risk
        for u, v, e in G.edges(data=True):
            k = (u, v) if u < v else (v, u)
            if k not in memo:
                nu, nv = G.nodes[u], G.nodes[v]
                mh, mp = self._hz((nu["x"] + nv["x"]) / 2, (nu["y"] + nv["y"]) / 2, t)
                h = max(nu["hazard"], nv["hazard"], mh)
                memo[k] = (h, self.risk_fn({"hazard": h, "predicted": max(mp, nu["pred"], nv["pred"]), "exposure": 0.0}))
            e["hazard"], e["risk"] = memo[k]

    def shelter_failed(self, shelter_id: int, t: float) -> bool:
        return any(int(i) == shelter_id and t >= ft for i, ft in self.shelter_failures)

    def update_parameters(self, **kw) -> None:
        """Change the live disaster (e.g. intensity slider moved mid-run)."""
        from dataclasses import replace
        if self.disaster is None:
            raise ValueError("This scenario has no disaster")
        self.disaster = replace(self.disaster, **{k: v for k, v in kw.items() if v is not None})
        self._last_key = None