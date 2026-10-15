"""Loads the active dataset (JSON), validates it, and turns it + a ScenarioConfig into a runnable Scenario.

Which dataset: PLANNER_DATASET in .env (default: the synthetic demo in data/sample/). Datasets are validated on
load: errors stop the app with a clear message, warnings are logged and exposed at GET /api/dataset.
"""
from __future__ import annotations

import json
import logging
import math
import random
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import networkx as nx

from config.settings import DATASET_PATH, DEMO_SCENARIO_PATH, ScenarioConfig
from src.data.schema import ValidationReport, describe_dataset, validate_dataset
from src.disaster.hazard_model import Disaster, make_disaster
from src.graph.graph_utils import undirected_edges
from src.graph.road_graph import build_graph
from src.routing.shelter_assignment import Shelter
from src.simulation.agent import Agent, AgentStatus

log = logging.getLogger(__name__)
_REPORTS: dict[str, ValidationReport] = {}


@dataclass
class Scenario:
    G: nx.DiGraph
    shelters: list[Shelter]
    agents: list[Agent]
    disaster: Disaster | None
    closures: list[tuple[int, int, float]]
    center: tuple[float, float]


@lru_cache(maxsize=4)
def _load(path: str) -> dict:
    p = Path(path)
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8"))
    elif p == Path(DEMO_SCENARIO_PATH):
        from src.data.preprocessing import generate_synthetic_dataset
        log.warning("%s not found - generating the synthetic demo in memory (run scripts/generate_sample_data.py)", p)
        data = generate_synthetic_dataset()
    else:
        raise FileNotFoundError(f"Dataset not found: {p}. Check PLANNER_DATASET in .env "
                                f"(build one with scripts/build_dataset.py).")
    report = validate_dataset(data)
    _REPORTS[path] = report
    for w in report.warnings:
        log.warning("dataset %s: %s", p.name, w)
    if not report.ok:
        raise ValueError(f"Dataset {p.name} is invalid:\n  " + "\n  ".join(report.errors))
    return data


def load_dataset(path: str | Path | None = None) -> dict:
    """Cached, validated, read-only dataset dict. Do not mutate."""
    return _load(str(path or DATASET_PATH))


def dataset_report(path: str | Path | None = None) -> ValidationReport:
    load_dataset(path)
    return _REPORTS[str(path or DATASET_PATH)]


def dataset_info(path: str | Path | None = None) -> dict:
    """Name, kind (synthetic/real/mixed), per-layer provenance, stats and warnings of the active dataset."""
    return describe_dataset(load_dataset(path), dataset_report(path))


def build_scenario(cfg: ScenarioConfig, dataset: dict | None = None) -> Scenario:
    ds = dataset or load_dataset()
    G = build_graph(ds)
    center = (cfg.center_x_frac * G.graph["width"], cfg.center_y_frac * G.graph["height"])
    dist_c = lambda n: math.hypot(G.nodes[n]["x"] - center[0], G.nodes[n]["y"] - center[1])

    shelters = [Shelter(id=s["id"], node=s["node"], x=G.nodes[s["node"]]["x"], y=G.nodes[s["node"]]["y"],
                        capacity=int(round(s["capacity"] * cfg.shelter_capacity_scale)),
                        occupancy=s.get("occupancy", 0)) for s in ds["shelters"][: cfg.n_shelters]]
    agents = []
    for g in ds["population"]:
        ordered = dist_c(g["node"]) <= cfg.evacuation_radius_m
        agents.append(Agent(id=g["id"], origin=g["node"], node=g["node"],
                            size=max(1, int(round(g["size"] * cfg.population_scale))), mobility=g["mobility"],
                            vulnerability=g.get("vulnerability", 0.0), ordered=ordered,
                            start_at=g.get("warning_delay_s", 0.0),
                            status=AgentStatus.AT_HOME if ordered else AgentStatus.SAFE))

    closures: list[tuple[int, int, float]] = []
    if cfg.road_closure_count > 0:
        near = [(u, v) for u, v in undirected_edges(G)
                if math.hypot((G.nodes[u]["x"] + G.nodes[v]["x"]) / 2 - center[0],
                              (G.nodes[u]["y"] + G.nodes[v]["y"]) / 2 - center[1]) <= cfg.evacuation_radius_m * 0.9]
        picks = random.Random(f"{cfg.seed}-closures").sample(near, min(cfg.road_closure_count, len(near)))
        closures = [(u, v, cfg.road_closure_time_s) for u, v in picks]

    return Scenario(G, shelters, agents, make_disaster(cfg, center), closures, center)