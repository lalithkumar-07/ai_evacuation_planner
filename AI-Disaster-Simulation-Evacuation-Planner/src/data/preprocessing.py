"""SYNTHETIC dataset generator (road grid, population groups, shelters). Not a real city.
Output format is the same one a real-data converter (OSM / WorldPop / shelter registry) must produce."""
from __future__ import annotations

import math
import random

import networkx as nx


def generate_synthetic_dataset(grid_size=16, spacing_m=400.0, total_population=6000, group_size=25,
                               walking_fraction=0.15, max_warning_delay_s=900.0, n_shelters=8,
                               shelter_capacity=1500, seed=42, center_frac=(0.5, 0.5),
                               core_radius_m=600.0, focus_radius_m=2500.0) -> dict:
    rng = lambda tag: random.Random(f"{seed}-{tag}")
    n, s = grid_size, spacing_m
    extent = (n - 1) * s
    cx, cy = center_frac[0] * extent, center_frac[1] * extent

    # roads: grid, every 4th row/column is an arterial; ~8% of local roads removed (connectivity kept)
    r = rng("network")
    und = nx.Graph()
    nodes = [{"id": i * n + j, "x": i * s, "y": j * s} for i in range(n) for j in range(n)]
    und.add_nodes_from(d["id"] for d in nodes)
    cand = []
    for i in range(n):
        for j in range(n):
            if i + 1 < n:
                cand.append((i * n + j, (i + 1) * n + j, j % 4 == 0))
            if j + 1 < n:
                cand.append((i * n + j, i * n + j + 1, i % 4 == 0))
    for u, v, art in cand:
        und.add_edge(u, v, arterial=art, distance=round(s * r.uniform(1.0, 1.2), 2))
    loc = [(u, v) for u, v, art in cand if not art]
    r.shuffle(loc)
    for u, v in loc:
        if r.random() < 0.08:
            data = und[u][v]
            und.remove_edge(u, v)
            if not nx.is_connected(und):
                und.add_edge(u, v, **data)
    edges = [{"u": u, "v": v, "distance": d["distance"], "arterial": d["arterial"]} for u, v, d in und.edges(data=True)]

    # shelters: farthest-point sampling among nodes outside the initial hazard core
    r = rng("shelters")
    pos = {d["id"]: (d["x"], d["y"]) for d in nodes}
    cands = [k for k, (x, y) in pos.items() if math.hypot(x - cx, y - cy) > core_radius_m * 1.3]
    chosen = [r.choice(cands)]
    while len(chosen) < min(n_shelters, len(cands)):
        chosen.append(max((k for k in cands if k not in chosen),
                          key=lambda k: min(math.hypot(pos[k][0] - pos[c][0], pos[k][1] - pos[c][1]) for c in chosen)))
    shelters = [{"id": i, "node": k, "capacity": shelter_capacity, "occupancy": 0} for i, k in enumerate(chosen)]

    # population groups, concentrated near the centre
    r = rng("population")
    ids = [d["id"] for d in nodes]
    w = [1.0 + 3.0 * math.exp(-(math.hypot(pos[k][0] - cx, pos[k][1] - cy) / (0.5 * focus_radius_m)) ** 2) for k in ids]
    population = [{"id": g, "node": r.choices(ids, w)[0], "size": group_size,
                   "mobility": "walking" if r.random() < walking_fraction else "vehicle",
                   "vulnerability": round(r.random(), 3), "warning_delay_s": round(r.uniform(0, max_warning_delay_s), 1)}
                  for g in range(round(total_population / group_size))]

    return {"meta": {"synthetic": True, "description": "SYNTHETIC prototype data - not a real place or population.",
                     "seed": seed, "grid_size": n, "spacing_m": s, "center": [cx, cy]},
            "nodes": nodes, "edges": edges, "population": population, "shelters": shelters}
