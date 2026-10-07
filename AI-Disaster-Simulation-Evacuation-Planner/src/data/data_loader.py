"""Loads the dataset JSON (synthetic today, real tomorrow) and turns it + a ScenarioConfig into a runnable Scenario."""
from __future__ import annotations

import json
import logging
import math
import random
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import networkx as nx

from config.settings import DEMO_SCENARIO_PATH, ScenarioConfig
from src.disaster.hazard_model import Disaster, make_disaster
from src.graph.graph_utils import undirected_edges
from src.graph.road_graph import build_graph
from src.routing.shelter_assignment import Shelter
from src.simulation.agent import Agent, AgentStatus

log = logging.getLogger(__name__)
REQUIRED = ("meta", "nodes", "edges", "population", "shelters")


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
    else:
        from src.data.preprocessing import generate_synthetic_dataset
        log.warning("%s not found - generating synthetic data in memory (run scripts/generate_sample_data.py)", p)
        data = generate_synthetic_dataset()
    missing = [k for k in REQUIRED if k not in data]
    if missing:
        raise ValueError(f"Dataset is missing keys: {missing}")
    return data


def load_dataset(path: str | Path | None = None) -> dict:
    """Cached, read-only dataset dict. Do not mutate."""
    return _load(str(path or DEMO_SCENARIO_PATH))


def build_scenario(cfg: ScenarioConfig, dataset: dict | None = None) -> Scenario:
    ds = dataset or load_dataset()
    G = build_graph(ds)
    extent = G.graph["extent"]
    center = (cfg.center_x_frac * extent, cfg.center_y_frac * extent)
    dist_c = lambda n: math.hypot(G.nodes[n]["x"] - center[0], G.nodes[n]["y"] - center[1])

    shelters = [Shelter(id=s["id"], node=s["node"], x=G.nodes[s["node"]]["x"], y=G.nodes[s["node"]]["y"],
                        capacity=int(round(s["capacity"] * cfg.shelter_capacity_scale)),
                        occupancy=s.get("occupancy", 0)) for s in ds["shelters"][:cfg.n_shelters]]
    agents = []
    for g in ds["population"]:
        ordered = dist_c(g["node"]) <= cfg.evacuation_radius_m
        agents.append(Agent(id=g["id"], origin=g["node"], node=g["node"],
                            size=max(1, int(round(g["size"] * cfg.population_scale))), mobility=g["mobility"],
                            vulnerability=g["vulnerability"], ordered=ordered, start_at=g["warning_delay_s"],
                            status=AgentStatus.AT_HOME if ordered else AgentStatus.SAFE))

    closures: list[tuple[int, int, float]] = []
    if cfg.road_closure_count > 0:
        near = [(u, v) for u, v in undirected_edges(G)
                if math.hypot((G.nodes[u]["x"] + G.nodes[v]["x"]) / 2 - center[0],
                              (G.nodes[u]["y"] + G.nodes[v]["y"]) / 2 - center[1]) <= cfg.evacuation_radius_m * 0.9]
        picks = random.Random(f"{cfg.seed}-closures").sample(near, min(cfg.road_closure_count, len(near)))
        closures = [(u, v, cfg.road_closure_time_s) for u, v in picks]

    return Scenario(G, shelters, agents, make_disaster(cfg, center), closures, center)
