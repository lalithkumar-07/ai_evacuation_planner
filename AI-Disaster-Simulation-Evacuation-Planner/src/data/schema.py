"""The dataset contract and its validator.

A dataset is one JSON object (see docs/data_pipeline.md):

    meta        name, optional frame, optional per-layer provenance, assumptions
    nodes       [{id, x, y}]                    metres from the south-west corner of the frame
    edges       [{u, v, distance, arterial, road_class?}]   undirected roads
    population  [{id, node, size, mobility, vulnerability, warning_delay_s}]   groups of evacuees
    shelters    [{id, node, capacity, occupancy, name?}]    ids MUST be 0..n-1 in order (the engine indexes by id)

Synthetic and real data share this format. ``meta.provenance`` records, for each layer (roads, population,
shelters), whether it is ``synthetic``, ``real`` or ``derived`` and where it came from, so the two are never confused.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import networkx as nx

from src.utils.helpers import Frame, legacy_frame

REQUIRED_KEYS = ("meta", "nodes", "edges", "population", "shelters")
LAYERS = ("roads", "population", "shelters")
SOURCES = ("synthetic", "real", "derived")
MOBILITY = ("walking", "vehicle")
SLOW_NODE_COUNT = 5000          # above this the per-step routing becomes slow (see docs)


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {"ok": self.ok, "errors": self.errors, "warnings": self.warnings, "stats": self.stats}


# ---- frame / provenance helpers -------------------------------------------------------------------------
def frame_of(ds: dict) -> Frame:
    """The dataset's frame. Files without one (the original synthetic grid) get the legacy centred frame."""
    meta = ds["meta"]
    if meta.get("frame"):
        return Frame(**meta["frame"])
    return legacy_frame((meta["grid_size"] - 1) * meta["spacing_m"])


def layer_sources(ds: dict) -> dict[str, str]:
    prov = (ds.get("meta") or {}).get("provenance") or {}
    default = "synthetic" if (ds.get("meta") or {}).get("synthetic", True) else "real"
    return {layer: (prov.get(layer) or {}).get("source", default) for layer in LAYERS}


def dataset_kind(ds: dict) -> str:
    """'synthetic' (all layers synthetic), 'real' (none synthetic) or 'mixed'."""
    s = set(layer_sources(ds).values())
    return "synthetic" if s == {"synthetic"} else "real" if "synthetic" not in s else "mixed"


# ---- validation ---------------------------------------------------------------------------------------------
def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def validate_dataset(ds) -> ValidationReport:
    r = ValidationReport()
    if not isinstance(ds, dict):
        r.errors.append("Dataset must be a JSON object")
        return r
    missing = [k for k in REQUIRED_KEYS if k not in ds]
    if missing:
        r.errors.append(f"Missing top-level keys: {missing}")
        return r
    meta = ds["meta"]
    if not isinstance(meta, dict):
        r.errors.append("meta must be an object")
        return r

    # frame
    try:
        frame = frame_of(ds)
        if not (frame.width_m > 0 and frame.height_m > 0):
            r.errors.append("frame width_m and height_m must be > 0")
        if not (0 < frame.cos_lat <= 1):
            r.errors.append("frame cos_lat must be in (0, 1]")
        if not (-90 <= frame.lat0 <= 90 and -180 <= frame.lon0 <= 180):
            r.errors.append("frame lat0/lon0 are not valid coordinates")
    except Exception as exc:                                    # missing grid_size/spacing_m, bad frame keys, ...
        r.errors.append(f"Cannot determine the coordinate frame: {exc!r}")
        frame = None

    # provenance
    prov = meta.get("provenance")
    if prov is not None:
        if not isinstance(prov, dict):
            r.errors.append("meta.provenance must be an object")
        else:
            for layer, info in prov.items():
                if layer not in LAYERS:
                    r.warnings.append(f"provenance has unknown layer '{layer}'")
                src = (info or {}).get("source")
                if src not in SOURCES:
                    r.errors.append(f"provenance.{layer}.source must be one of {SOURCES}, got {src!r}")
                elif src == "real" and not (info or {}).get("origin"):
                    r.warnings.append(f"provenance.{layer} is 'real' but has no 'origin' (file or URL)")

    # nodes
    nodes = ds["nodes"] if isinstance(ds["nodes"], list) else []
    if not nodes:
        r.errors.append("nodes must be a non-empty list")
    node_ids, seen = set(), set()
    for i, n in enumerate(nodes):
        if not (isinstance(n, dict) and "id" in n and _num(n.get("x")) and _num(n.get("y"))):
            r.errors.append(f"nodes[{i}] needs numeric x and y and an id")
            continue
        if n["id"] in seen:
            r.errors.append(f"duplicate node id {n['id']}")
        seen.add(n["id"]); node_ids.add(n["id"])
        if frame and not (-1 <= n["x"] <= frame.width_m + 1 and -1 <= n["y"] <= frame.height_m + 1):
            r.warnings.append(f"node {n['id']} lies outside the frame (x={n['x']:.0f}, y={n['y']:.0f})")
            break                                               # one example is enough

    # edges
    g = nx.Graph()
    g.add_nodes_from(node_ids)
    bad_edges = 0
    for i, e in enumerate(ds["edges"] if isinstance(ds["edges"], list) else []):
        ok = isinstance(e, dict) and e.get("u") in node_ids and e.get("v") in node_ids and e.get("u") != e.get("v")
        if not ok:
            bad_edges += 1
            if bad_edges <= 3:
                r.errors.append(f"edges[{i}] must connect two different existing nodes")
            continue
        if not (_num(e.get("distance")) and e["distance"] > 0):
            r.errors.append(f"edges[{i}] distance must be a positive number")
            continue
        if e["distance"] > 5000:
            r.warnings.append(f"edges[{i}] is {e['distance']:.0f} m long (check the road geometry)")
        g.add_edge(e["u"], e["v"])
    if bad_edges > 3:
        r.errors.append(f"... {bad_edges} invalid edges in total")
    if not ds["edges"]:
        r.errors.append("edges must be a non-empty list")

    # connectivity
    comps = sorted(nx.connected_components(g), key=len, reverse=True) if node_ids else []
    main = comps[0] if comps else set()
    if len(comps) > 1:
        r.warnings.append(f"road network has {len(comps)} disconnected parts; the largest has {len(main)} of "
                          f"{len(node_ids)} nodes. People or shelters outside it cannot reach each other.")

    # population
    pop_total, outside = 0, 0
    groups = ds["population"] if isinstance(ds["population"], list) else []
    if not groups:
        r.errors.append("population must contain at least one group")
    gids = set()
    for i, p in enumerate(groups):
        if not (isinstance(p, dict) and p.get("node") in node_ids):
            r.errors.append(f"population[{i}] must reference an existing node")
            continue
        if not (_num(p.get("size")) and p["size"] > 0):
            r.errors.append(f"population[{i}] size must be > 0")
            continue
        if p.get("mobility") not in MOBILITY:
            r.errors.append(f"population[{i}] mobility must be one of {MOBILITY}")
        if p.get("id") in gids:
            r.errors.append(f"duplicate population id {p.get('id')}")
        gids.add(p.get("id"))
        pop_total += p["size"]
        outside += p["node"] not in main
    if outside and len(comps) > 1:
        r.warnings.append(f"{outside} population groups sit outside the main road network")

    # shelters (the engine indexes shelters by id, so ids must be 0..n-1 in order)
    shelters = ds["shelters"] if isinstance(ds["shelters"], list) else []
    if not shelters:
        r.errors.append("shelters must contain at least one shelter")
    if [s.get("id") for s in shelters if isinstance(s, dict)] != list(range(len(shelters))):
        r.errors.append("shelter ids must be 0, 1, 2, ... in order")
    cap_total = 0
    for i, s in enumerate(shelters):
        if not (isinstance(s, dict) and s.get("node") in node_ids):
            r.errors.append(f"shelters[{i}] must reference an existing node")
            continue
        if not (_num(s.get("capacity")) and s["capacity"] > 0):
            r.errors.append(f"shelters[{i}] capacity must be > 0")
            continue
        if _num(s.get("occupancy")) and s["occupancy"] > s["capacity"]:
            r.errors.append(f"shelters[{i}] occupancy exceeds capacity")
        cap_total += s["capacity"]
    if shelters and len(comps) > 1 and any(isinstance(s, dict) and s.get("node") not in main for s in shelters):
        r.warnings.append("some shelters sit outside the main road network")

    # soft checks
    if len(node_ids) > SLOW_NODE_COUNT:
        r.warnings.append(f"{len(node_ids)} nodes: simulation steps will be slow (routing is recomputed each step)")
    if pop_total and cap_total and cap_total < pop_total:
        r.warnings.append(f"total shelter capacity ({cap_total:,.0f}) covers only {100 * cap_total / pop_total:.0f}% "
                          f"of the population ({pop_total:,.0f})")
    if "provenance" not in meta and meta.get("synthetic") is None:
        r.warnings.append("no provenance recorded: treated as synthetic")

    r.stats = {"nodes": len(node_ids), "edges": len(ds["edges"]) if isinstance(ds["edges"], list) else 0,
               "components": len(comps), "population_groups": len(groups), "population": pop_total,
               "shelters": len(shelters), "shelter_capacity": cap_total}
    return r


def describe_dataset(ds: dict, report: ValidationReport | None = None) -> dict:
    """What the API tells the UI about the active dataset."""
    meta = ds["meta"]
    prov = meta.get("provenance") or {}
    src = layer_sources(ds)
    report = report or validate_dataset(ds)
    return {
        "name": meta.get("name", "unnamed"), "kind": dataset_kind(ds), "description": meta.get("description", ""),
        "layers": {l: {"source": src[l], **{k: v for k, v in (prov.get(l) or {}).items() if k != "source"}} for l in LAYERS},
        "assumptions": meta.get("assumptions", []), "stats": report.stats, "warnings": report.warnings,
        "frame": frame_of(ds).to_dict() if not report.errors else None,
    }