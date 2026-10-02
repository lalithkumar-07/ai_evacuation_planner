"""Owns the disaster over time: writes hazard + risk onto the graph, applies closures/shelter failures."""
from __future__ import annotations

import networkx as nx

from src.ai.prediction import RiskPredictor
from src.disaster.hazard_model import Disaster
from src.disaster.risk_calculator import RiskFn


class DisasterManager:
    def __init__(self, disaster: Disaster | None, predictor: RiskPredictor, risk_fn: RiskFn,
                 closures: list[tuple[int, int, float]], shelter_failures: list[list[float]],
                 exposure: dict[int, float]) -> None:
        self.disaster, self.predictor, self.risk_fn = disaster, predictor, risk_fn
        self.closures, self.shelter_failures, self.exposure = closures, shelter_failures, exposure

    def _hz(self, x: float, y: float, t: float) -> tuple[float, float]:
        h = self.disaster.hazard_at(x, y, t) if self.disaster else 0.0
        return h, self.predictor.predict_hazard(self.disaster, x, y, t)

    def update(self, G: nx.DiGraph, t: float) -> None:
        """Set hazard/risk on every node and edge for time t, and apply scheduled road closures."""
        for u, v, tc in self.closures:
            if t >= tc:
                G[u][v]["forced_closed"] = G[v][u]["forced_closed"] = True
        for n, d in G.nodes(data=True):
            h, p = self._hz(d["x"], d["y"], t)
            d["hazard"] = h
            d["risk"] = self.risk_fn({"hazard": h, "predicted": p, "exposure": self.exposure.get(n, 0.0)})
        for u, v, e in G.edges(data=True):
            nu, nv = G.nodes[u], G.nodes[v]
            mh, mp = self._hz((nu["x"] + nv["x"]) / 2, (nu["y"] + nv["y"]) / 2, t)
            p = max(mp, self._hz(nu["x"], nu["y"], t)[1], self._hz(nv["x"], nv["y"], t)[1])
            e["hazard"] = max(nu["hazard"], nv["hazard"], mh)
            e["risk"] = self.risk_fn({"hazard": e["hazard"], "predicted": p, "exposure": 0.0})

    def shelter_failed(self, shelter_id: int, t: float) -> bool:
        return any(int(i) == shelter_id and t >= ft for i, ft in self.shelter_failures)

    def update_parameters(self, **kw) -> None:
        """Change the live disaster (e.g. intensity slider moved mid-run)."""
        from dataclasses import replace
        if self.disaster is None:
            raise ValueError("This scenario has no disaster")
        self.disaster = replace(self.disaster, **{k: v for k, v in kw.items() if v is not None})
