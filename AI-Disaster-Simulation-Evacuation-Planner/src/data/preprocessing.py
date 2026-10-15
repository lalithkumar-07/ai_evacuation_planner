"""SYNTHETIC dataset generator (road grid, population groups, shelters). Not a real city.
Output format is the same one a real-data converter (OSM / WorldPop / shelter registry) must produce."""
from __future__ import annotations

import math
import random

import networkx as nx
from src.data.schema import LAYERS

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

    prov = {layer: {"source": "synthetic", "origin": "src/data/preprocessing.py:generate_synthetic_dataset",
                    "notes": "generated for the prototype; not a real place or population"} for layer in LAYERS}
    return {"meta": {"name": "demo_scenario", "synthetic": True,
                     "description": "SYNTHETIC prototype data - not a real place or population.",
                     "provenance": prov, "seed": seed, "grid_size": n, "spacing_m": s, "center": [cx, cy]},
            "nodes": nodes, "edges": edges, "population": population, "shelters": shelters}


# =====================================================================================================
# REAL DATA: raw files (data/raw/...) -> processed dataset (data/processed/...) + manifest
# =====================================================================================================
import hashlib      # noqa: E402
import json         # noqa: E402
from datetime import datetime, timezone      # noqa: E402
from pathlib import Path                      # noqa: E402

import numpy as np                            # noqa: E402

from src.data.importers import nearest_nodes, read_population_csv, read_roads_geojson, read_shelters_csv  # noqa: E402
from src.data.schema import validate_dataset  # noqa: E402


def _sha256(path) -> dict:
    data = Path(path).read_bytes()
    return {"file": Path(path).name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def canonical_json(ds: dict) -> str:
    """The exact text written to disk: sorted keys, no spaces. Same inputs -> same bytes -> same checksum."""
    return json.dumps(ds, separators=(",", ":"), sort_keys=True)


def make_groups(per_node: dict[int, float], group_size: int, walking_fraction: float,
                max_warning_delay_s: float, seed: int) -> list[dict]:
    """Split each node's population into evacuee groups of about ``group_size``. Totals are preserved exactly.
    Mobility and warning delay are ASSUMPTIONS (no such data in the inputs), drawn from a seeded generator."""
    rng = random.Random(f"{seed}-population")
    groups = []
    for node in sorted(per_node):
        total = int(round(per_node[node]))
        if total <= 0:
            continue
        k = max(1, round(total / group_size))
        base, extra = divmod(total, k)
        for i in range(k):
            groups.append({"id": len(groups), "node": int(node), "size": base + (1 if i < extra else 0),
                           "mobility": "walking" if rng.random() < walking_fraction else "vehicle",
                           "vulnerability": round(rng.random(), 3),
                           "warning_delay_s": round(rng.uniform(0, max_warning_delay_s), 1)})
    return groups


def build_real_dataset(roads_path, population_path, shelters_path, *, name: str, group_size: int = 25,
                       walking_fraction: float = 0.15, max_warning_delay_s: float = 900.0, seed: int = 42,
                       snap_m: float = 1.0, max_snap_distance_m: float = 500.0,
                       licenses: dict | None = None, notes: str = "") -> tuple[dict, dict]:
    """Build a dataset from raw files. Returns (dataset, manifest). Raises ValueError if the result is invalid."""
    licenses = licenses or {}
    roads = read_roads_geojson(roads_path, snap_m=snap_m)
    frame = roads["frame"]
    nodes_xy = np.array([[n["x"], n["y"]] for n in roads["nodes"]])

    pop_rows, pop_bad = read_population_csv(population_path)
    pts = np.array([frame.from_latlon(r["lat"], r["lon"]) for r in pop_rows]).reshape(-1, 2)
    idx, dist = nearest_nodes(pts, nodes_xy)
    per_node: dict[int, float] = {}
    far = zero = 0
    for r, j, d in zip(pop_rows, idx, dist):
        if r["population"] <= 0:
            zero += 1
        elif d > max_snap_distance_m:
            far += 1
        else:
            per_node[int(j)] = per_node.get(int(j), 0) + r["population"]
    groups = make_groups(per_node, group_size, walking_fraction, max_warning_delay_s, seed)

    sh_rows, sh_bad = read_shelters_csv(shelters_path)
    spts = np.array([frame.from_latlon(r["lat"], r["lon"]) for r in sh_rows]).reshape(-1, 2)
    sidx, sdist = nearest_nodes(spts, nodes_xy)
    shelters, sh_far, sh_nonpos = [], 0, 0
    for r, j, d in zip(sh_rows, sidx, sdist):
        if r["capacity"] <= 0:
            sh_nonpos += 1
        elif d > max_snap_distance_m:
            sh_far += 1
        else:
            occ = int(min(r.get("occupancy") or 0, r["capacity"]))
            shelters.append({"id": len(shelters), "node": int(j), "capacity": int(r["capacity"]), "occupancy": occ,
                             "name": r.get("name") or f"shelter {len(shelters)}"})

    inputs = {"roads": _sha256(roads_path), "population": _sha256(population_path), "shelters": _sha256(shelters_path)}
    prov = {layer: {"source": "real", "origin": inputs[layer]["file"], "sha256": inputs[layer]["sha256"],
                    "license": licenses.get(layer, "not recorded")} for layer in LAYERS}
    assumptions = [
        f"Population points are snapped to the nearest road node within {max_snap_distance_m:g} m; others are dropped.",
        f"Evacuees are grouped into groups of about {group_size} people.",
        f"{walking_fraction:.0%} of groups are assumed to be on foot, the rest in vehicles (inputs have no mobility data).",
        f"Warning delays are drawn uniformly from 0-{max_warning_delay_s:g} s (assumed).",
        "Road capacity and speed come from the road class only (arterial vs local) with default values.",
    ]
    ds = {"meta": {"name": name, "synthetic": False, "description": notes or f"Dataset '{name}' built from raw files.",
                   "frame": frame.to_dict(), "provenance": prov, "assumptions": assumptions, "seed": seed},
          "nodes": roads["nodes"], "edges": roads["edges"], "population": groups, "shelters": shelters}

    report = validate_dataset(ds)
    if not report.ok:
        raise ValueError("Built dataset is invalid:\n  " + "\n  ".join(report.errors))
    dropped = {"roads": {**roads["stats"]},
               "population": {"unreadable_rows": pop_bad["dropped"], "examples": pop_bad["examples"],
                              "zero_population_rows": zero, "too_far_from_any_road": far},
               "shelters": {"unreadable_rows": sh_bad["dropped"], "examples": sh_bad["examples"],
                            "non_positive_capacity": sh_nonpos, "too_far_from_any_road": sh_far}}
    manifest = {"name": name, "tool": "src.data.preprocessing.build_real_dataset",
                "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "parameters": {"group_size": group_size, "walking_fraction": walking_fraction,
                               "max_warning_delay_s": max_warning_delay_s, "seed": seed, "snap_m": snap_m,
                               "max_snap_distance_m": max_snap_distance_m},
                "inputs": inputs, "dropped": dropped, "assumptions": assumptions, "validation": report.to_dict(),
                "output_sha256": hashlib.sha256(canonical_json(ds).encode("utf-8")).hexdigest()}
    return ds, manifest


def write_dataset(ds: dict, manifest: dict, out_dir) -> tuple[Path, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    name = ds["meta"]["name"]
    data_path, man_path = out / f"{name}.json", out / f"{name}.manifest.json"
    data_path.write_text(canonical_json(ds), encoding="utf-8")
    man_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return data_path, man_path