"""Road classes: default speed, lanes and capacity per OpenStreetMap `highway` class, and parsers for the OSM
tags `maxspeed`, `lanes` and `oneway`.

The numbers below are generic ASSUMPTIONS, not measurements of any real road. Override or extend them in
config/simulation_config.yaml (`road_classes:`). A speed limit or lane count tagged on a road always wins over its class.

`lanes` in a class is lanes PER DIRECTION. The OSM `lanes` tag counts all lanes, so for a two-way road we halve it.
`capacity_per_lane_m` is the number of people that fit on one lane per metre of road (the queueing capacity).
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from config.settings import ROAD_CLASS_OVERRIDES


@dataclass(frozen=True)
class RoadClass:
    speed_mps: float
    lanes: int
    capacity_per_lane_m: float
    arterial: bool


def _kph(v: float) -> float:
    return v / 3.6


# "arterial" / "local" are the two classes of the synthetic grid; their values reproduce the pre-Phase-4 constants exactly.
DEFAULT_CLASSES: dict[str, RoadClass] = {
    "arterial": RoadClass(13.9, 2, 0.25, True),
    "local": RoadClass(8.3, 1, 0.2, False),
    "motorway": RoadClass(_kph(80), 2, 0.25, True), "motorway_link": RoadClass(_kph(50), 1, 0.25, True),
    "trunk": RoadClass(_kph(60), 2, 0.25, True), "trunk_link": RoadClass(_kph(40), 1, 0.25, True),
    "primary": RoadClass(_kph(50), 2, 0.25, True), "primary_link": RoadClass(_kph(40), 1, 0.25, True),
    "secondary": RoadClass(_kph(40), 2, 0.25, True), "secondary_link": RoadClass(_kph(30), 1, 0.25, True),
    "tertiary": RoadClass(_kph(35), 1, 0.2, False), "tertiary_link": RoadClass(_kph(25), 1, 0.2, False),
    "unclassified": RoadClass(_kph(30), 1, 0.2, False), "residential": RoadClass(_kph(25), 1, 0.2, False),
    "living_street": RoadClass(_kph(10), 1, 0.2, False), "service": RoadClass(_kph(15), 1, 0.2, False),
    "track": RoadClass(_kph(15), 1, 0.15, False),
}
# OSM `highway` values that cars cannot use. The importer skips them and says how many it skipped.
NON_DRIVABLE = {"footway", "path", "pedestrian", "steps", "cycleway", "bridleway", "corridor", "platform",
                "construction", "proposed", "elevator", "escape", "raceway", "bus_guideway"}


def build_classes(overrides: dict | None = None) -> dict[str, RoadClass]:
    """DEFAULT_CLASSES with the YAML overrides applied (partial overrides allowed for known classes)."""
    out = dict(DEFAULT_CLASSES)
    for name, o in (overrides or {}).items():
        base = out.get(name)
        speed = _kph(o["speed_kph"]) if "speed_kph" in o else o.get("speed_mps", base.speed_mps if base else None)
        lanes = o.get("lanes", base.lanes if base else None)
        cap = o.get("capacity_per_lane_m", base.capacity_per_lane_m if base else None)
        art = o.get("arterial", base.arterial if base else False)
        if None in (speed, lanes, cap):
            raise ValueError(f"road_classes.{name}: a new class needs speed_kph (or speed_mps), lanes and capacity_per_lane_m")
        if speed <= 0 or lanes < 1 or cap <= 0:
            raise ValueError(f"road_classes.{name}: speed, lanes and capacity must be positive")
        out[name] = RoadClass(float(speed), int(lanes), float(cap), bool(art))
    return out


CLASSES = build_classes(ROAD_CLASS_OVERRIDES)


def resolve_edge(e: dict, classes: dict[str, RoadClass] | None = None) -> dict:
    """Physical attributes of one dataset edge: class, speed (m/s), lanes per direction, capacity, arterial flag.

    Order of precedence: tagged value on the edge > road class > legacy `arterial` flag (files without classes).
    """
    classes = classes or CLASSES
    name = e.get("road_class")
    if name not in classes:
        name = "arterial" if e.get("arterial") else "local"
    c = classes[name]
    speed = e["maxspeed_kph"] / 3.6 if e.get("maxspeed_kph") else c.speed_mps
    tag = e.get("lanes")
    lanes = c.lanes if not tag else (int(tag) if e.get("oneway") else max(1, round(int(tag) / 2)))
    return {"class": name, "speed_mps": speed, "lanes": lanes, "capacity_per_m": lanes * c.capacity_per_lane_m,
            "arterial": c.arterial or bool(e.get("arterial"))}


# ---- OSM tag parsers (return None when the tag is missing or not a plain number) ------------------------------
def parse_maxspeed_kph(value) -> float | None:
    """'50' -> 50, '50 km/h' -> 50, '30 mph' -> 48.3, 'walk' -> 7, '50;60' -> 50, 'none' / 'IN:urban' -> None."""
    if value is None:
        return None
    s = str(value).strip().lower().split(";")[0].strip()
    if s == "walk":
        return 7.0
    try:
        mph = s.endswith("mph")
        num = float(s.replace("mph", "").replace("km/h", "").replace("kph", "").strip())
    except ValueError:
        return None
    kph = num * 1.609344 if mph else num
    return round(kph, 1) if 3 <= kph <= 200 else None


def parse_lanes(value) -> int | None:
    """'2' -> 2, '2;3' -> 2; anything outside 1..12 -> None."""
    if value is None:
        return None
    try:
        n = int(float(str(value).split(";")[0].strip()))
    except ValueError:
        return None
    return n if 1 <= n <= 12 else None


def parse_oneway(value, junction=None) -> int:
    """1 = one-way along the drawn direction, -1 = one-way against it, 0 = two-way. Roundabouts are one-way."""
    s = str(value).strip().lower() if value is not None else ""
    if s in ("yes", "true", "1"):
        return 1
    if s in ("-1", "reverse"):
        return -1
    if s in ("no", "false", "0") or not s:
        return 1 if str(junction).lower() in ("roundabout", "circular") else 0
    return 0