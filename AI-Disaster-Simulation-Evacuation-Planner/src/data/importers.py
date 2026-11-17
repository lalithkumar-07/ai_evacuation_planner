"""Parsers for raw, real-world files. Pure functions: file in, plain data out, no global state.

  roads        GeoJSON (LineString / MultiLineString), e.g. an OpenStreetMap export with a `highway` property
  population   CSV with columns lat, lon, population
  shelters     CSV with columns lat, lon, capacity  (+ optional name, occupancy)

CSV files are read as UTF-8 (a BOM from Excel on Windows is handled). Column names are case-insensitive and a few
common aliases are accepted. Bad rows are dropped and reported, never silently guessed.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import networkx as nx
import numpy as np

from src.graph.road_classes import CLASSES, NON_DRIVABLE, parse_lanes, parse_maxspeed_kph, parse_oneway
from src.utils.helpers import M_PER_DEG_LAT, Frame

POPULATION_COLUMNS = {"lat": ("lat", "latitude", "y"), "lon": ("lon", "lng", "long", "longitude", "x"),
                      "population": ("population", "pop", "people", "count")}
SHELTER_COLUMNS = {"lat": ("lat", "latitude", "y"), "lon": ("lon", "lng", "long", "longitude", "x"),
                   "capacity": ("capacity", "cap", "beds", "places"), "name": ("name", "shelter", "title"),
                   "occupancy": ("occupancy", "occupied", "current")}


# ---- roads ---------------------------------------------------------------------------------------------------
def read_roads_geojson(path, snap_m: float = 1.0) -> dict:
    """GeoJSON roads -> {nodes, edges, frame, stats}.

    * Vertices closer than ``snap_m`` become one node, so roads that share a coordinate (an intersection) connect.
    * Reads the OSM tags `highway` (road class), `maxspeed`, `lanes`, `oneway` and `junction`.
    * Roads cars cannot use (footway, path, steps, ...) are skipped and counted. Unknown classes become `unclassified`.
    * Only the largest STRONGLY connected network is kept, so every kept node can reach every other one
      following one-way directions. The frame is computed from the part that is kept.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    feats = data.get("features", []) if data.get("type") == "FeatureCollection" else [data]
    lines, skipped, bad, non_drivable, unknown = [], {}, 0, {}, {}
    for f in feats:
        geom, props = f.get("geometry") or {}, f.get("properties") or {}
        kind, coords = geom.get("type"), geom.get("coordinates")
        parts = [coords] if kind == "LineString" else coords if kind == "MultiLineString" else None
        if parts is None:
            skipped[str(kind)] = skipped.get(str(kind), 0) + 1
            continue
        hw = props.get("highway")
        if hw in NON_DRIVABLE:
            non_drivable[hw] = non_drivable.get(hw, 0) + 1
            continue
        if hw is not None and hw not in CLASSES:
            unknown[str(hw)] = unknown.get(str(hw), 0) + 1
            hw = "unclassified"
        attrs = {"road_class": hw, "arterial": CLASSES[hw].arterial if hw else False,
                 "maxspeed_kph": parse_maxspeed_kph(props.get("maxspeed")), "lanes": parse_lanes(props.get("lanes")),
                 "oneway": parse_oneway(props.get("oneway"), props.get("junction"))}
        for part in parts:
            pts = [(float(c[0]), float(c[1])) for c in part
                   if isinstance(c, (list, tuple)) and len(c) >= 2 and all(math.isfinite(float(v)) for v in c[:2])]
            if len(pts) >= 2:
                lines.append((pts, attrs))
            else:
                bad += 1
    if not lines:
        raise ValueError("No usable drivable LineString features found in the roads file")

    lons = [p[0] for pts, _ in lines for p in pts]
    lats = [p[1] for pts, _ in lines for p in pts]
    lat0, lon0 = min(lats), min(lons)
    cos_lat = math.cos(math.radians((min(lats) + max(lats)) / 2))
    frame = Frame(lat0=lat0, lon0=lon0, cos_lat=cos_lat,
                  width_m=(max(lons) - lon0) * M_PER_DEG_LAT * cos_lat, height_m=(max(lats) - lat0) * M_PER_DEG_LAT)
    if frame.width_m <= 0 or frame.height_m <= 0:
        raise ValueError("Road coordinates cover no area (all on one line or point)")

    key_to_id, xy, ll, edges = {}, [], [], {}
    for pts, a in lines:
        prev = None
        for lon, lat in pts:
            x, y = frame.from_latlon(lat, lon)
            key = (round(x / snap_m), round(y / snap_m))
            if key not in key_to_id:
                key_to_id[key] = len(xy)
                xy.append((x, y))
                ll.append((lon, lat))
            nid = key_to_id[key]
            if prev is not None and prev != nid:
                if a["oneway"] == 0:
                    ek = (min(prev, nid), max(prev, nid), False)
                else:                                              # one-way: store as u -> v (flip if tagged -1)
                    ek = (prev, nid, True) if a["oneway"] == 1 else (nid, prev, True)
                rec = edges.setdefault(ek, {"arterial": False, "road_class": None, "maxspeed_kph": None, "lanes": None})
                rec["arterial"] = rec["arterial"] or a["arterial"]
                for k in ("road_class", "maxspeed_kph", "lanes"):
                    rec[k] = rec[k] if rec[k] is not None else a[k]
            prev = nid

    dg = nx.DiGraph()
    dg.add_nodes_from(range(len(xy)))
    for (a, b, ow) in edges:
        dg.add_edge(a, b)
        if not ow:
            dg.add_edge(b, a)
    main = max(nx.strongly_connected_components(dg), key=len)
    order = sorted(main)
    new_id = {old: i for i, old in enumerate(order)}

    # The frame must describe the network we keep, not stray pieces we drop (they could be far away).
    lons = [ll[o][0] for o in order]
    lats = [ll[o][1] for o in order]
    lat0, lon0 = min(lats), min(lons)
    cos_lat = math.cos(math.radians((min(lats) + max(lats)) / 2))
    frame = Frame(lat0=lat0, lon0=lon0, cos_lat=cos_lat,
                  width_m=(max(lons) - lon0) * M_PER_DEG_LAT * cos_lat, height_m=(max(lats) - lat0) * M_PER_DEG_LAT)
    if frame.width_m <= 0 or frame.height_m <= 0:
        raise ValueError("The connected road network covers no area")
    pos = {o: frame.from_latlon(ll[o][1], ll[o][0]) for o in order}
    nodes = [{"id": new_id[o], "x": round(pos[o][0], 2), "y": round(pos[o][1], 2)} for o in order]
    out_edges, by_class, tagged_speed, tagged_lanes = [], {}, 0, 0
    for (a, b, ow), rec in sorted(edges.items()):
        if a not in main or b not in main:
            continue
        e = {"u": new_id[a], "v": new_id[b],
             "distance": round(max(math.hypot(pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]), 0.01), 2),
             "arterial": rec["arterial"], "road_class": rec["road_class"]}
        if rec["maxspeed_kph"] is not None:
            e["maxspeed_kph"] = rec["maxspeed_kph"]; tagged_speed += 1
        if rec["lanes"] is not None:
            e["lanes"] = rec["lanes"]; tagged_lanes += 1
        if ow:
            e["oneway"] = True
        out_edges.append(e)
        cls = rec["road_class"] or ("arterial" if rec["arterial"] else "local")
        by_class[cls] = by_class.get(cls, 0) + 1
    return {"nodes": nodes, "edges": out_edges, "frame": frame,
            "stats": {"features": len(feats), "lines": len(lines), "nodes_before_cleanup": len(xy),
                      "edges_before_cleanup": len(edges), "nodes_dropped_disconnected": len(xy) - len(main),
                      "skipped_geometries": skipped, "unusable_lines": bad,
                      "non_drivable_skipped": non_drivable, "unknown_road_classes": unknown,
                      "roads_by_class": dict(sorted(by_class.items())), "oneway_roads": sum(1 for e in out_edges if e.get("oneway")),
                      "roads_with_tagged_speed": tagged_speed, "roads_with_tagged_lanes": tagged_lanes}}

# ---- CSV -------------------------------------------------------------------------------------------------------
def read_csv_rows(path, columns: dict, required: tuple) -> tuple[list[dict], dict]:
    """Rows as dicts with canonical keys. Returns (rows, {'dropped': n, 'examples': [...]})."""
    rows, dropped, examples = [], 0, []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        header = {(h or "").strip().lower(): h for h in (reader.fieldnames or [])}
        pick = {}
        for canon, aliases in columns.items():
            hit = next((a for a in aliases if a in header), None)
            if hit:
                pick[canon] = header[hit]
        absent = [c for c in required if c not in pick]
        if absent:
            raise ValueError(f"{Path(path).name}: missing column(s) {absent}. Found: {list(header)}. "
                             f"Accepted names: { {c: columns[c] for c in absent} }")
        for line_no, raw in enumerate(reader, start=2):
            try:
                row = {c: raw[col].strip() for c, col in pick.items() if raw.get(col) is not None}
                for c in ("lat", "lon", "population", "capacity", "occupancy"):
                    if c in row:
                        row[c] = float(row[c]) if row[c] != "" else None
                if any(row.get(c) is None or not math.isfinite(row[c]) for c in required):
                    raise ValueError("empty or non-finite value")
                if not (-90 <= row["lat"] <= 90 and -180 <= row["lon"] <= 180):
                    raise ValueError("coordinates out of range")
                rows.append(row)
            except (ValueError, TypeError, KeyError) as exc:
                dropped += 1
                if len(examples) < 5:
                    examples.append(f"line {line_no}: {exc}")
    return rows, {"dropped": dropped, "examples": examples}


def read_population_csv(path):
    return read_csv_rows(path, POPULATION_COLUMNS, ("lat", "lon", "population"))


def read_shelters_csv(path):
    return read_csv_rows(path, SHELTER_COLUMNS, ("lat", "lon", "capacity"))


# ---- snapping -------------------------------------------------------------------------------------------------------
def nearest_nodes(points_xy: np.ndarray, nodes_xy: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Index of the closest node (and the distance in metres) for each point."""
    if len(points_xy) == 0:
        return np.zeros(0, dtype=int), np.zeros(0)
    chunk = max(1, 4_000_000 // max(1, len(nodes_xy)))
    idx, dist = [], []
    for i in range(0, len(points_xy), chunk):
        p = points_xy[i:i + chunk]
        d2 = ((p[:, None, :] - nodes_xy[None, :, :]) ** 2).sum(axis=2)
        j = d2.argmin(axis=1)
        idx.append(j)
        dist.append(np.sqrt(d2[np.arange(len(p)), j]))
    return np.concatenate(idx), np.concatenate(dist)