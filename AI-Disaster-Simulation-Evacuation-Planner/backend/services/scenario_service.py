"""Scenario catalogue: 7 read-only presets (shared) + custom scenarios (per session) + static map layers.

Nothing here is global-mutable any more: a user's custom scenarios and their "live" scenario live in their
SessionData, so one user's changes can never affect another's.
"""
from __future__ import annotations

from dataclasses import replace

from backend.schemas.disaster import DisasterStartIn
from backend.schemas.scenario import ScenarioIn
from backend.services.session_store import STORE, SessionData
from config.settings import MAX_CUSTOM_SCENARIOS, RISK_LEVELS, ScenarioConfig
from src.data.data_loader import load_dataset
from src.disaster.hazard_model import DISASTER_PRESETS
from src.graph.graph_utils import undirected_edges
from src.utils.helpers import from_latlon, node_latlon, to_latlon


class NotFound(LookupError):
    pass


_b = ScenarioConfig()
PRESETS: dict[str, ScenarioConfig] = {c.id: c for c in [
    replace(_b, id="normal", name="1. Normal conditions", disaster_enabled=False,
            description="No hazard. Precautionary drill: measures pure traffic behaviour."),
    replace(_b, id="static", name="2. Static disaster", initial_radius_m=1500, max_radius_m=1500,
            spread_speed_mps=0.0, description="Hazard fixed at 1.5 km radius."),
    replace(_b, id="expanding", name="3. Expanding disaster",
            description="Hazard spreads outward over time (preset values for the chosen disaster type)."),
    replace(_b, id="road_failure", name="4. Road failure", initial_radius_m=1500, max_radius_m=1500,
            spread_speed_mps=0.0, road_closure_count=14, description="Static hazard + 14 roads closed at t=5 min."),
    replace(_b, id="shelter_failure", name="5. Shelter failure", shelter_failures=[[0, 900], [1, 1500]],
            description="Expanding hazard; shelters 0 and 1 become unsafe at t=15 and t=25 min."),
    replace(_b, id="high_density", name="6. High population density", population_scale=20000 / 6000,
            shelter_capacity_scale=20000 / 6000, description="Expanding hazard, ~20,000 people."),
    replace(_b, id="combined", name="7. Combined failure", population_scale=2.0, shelter_capacity_scale=1.2,
            road_closure_count=10, shelter_failures=[[0, 1200]],
            description="Expanding hazard + 10 road closures + shelter failure + tight capacity."),
]}

BLURBS = {"flood": "Water spreads outward and closes roads from the centre.",
          "wildfire": "A fast front: smaller area, steeper edge, spreads quickly.",
          "earthquake": "Instant, fixed damage zone. Nothing spreads afterwards."}


# ---- pure helpers (take an already-locked SessionData, or None for presets only) -----------------
def get_scenario(scenario_id: str, session: SessionData | None = None) -> ScenarioConfig:
    if scenario_id == "live":
        if session is not None and session.cfg is not None:
            return session.cfg
        raise NotFound("No live scenario in this session yet. Generate one first.")
    if session is not None and scenario_id in session.custom_scenarios:
        return session.custom_scenarios[scenario_id]
    if scenario_id in PRESETS:
        return PRESETS[scenario_id]
    raise NotFound(f"Unknown scenario '{scenario_id}'")


def _extent() -> float:
    m = load_dataset()["meta"]
    return (m["grid_size"] - 1) * m["spacing_m"]


def resolved(cfg: ScenarioConfig) -> dict:
    """Config with preset defaults filled in and the epicentre expressed as lat/lon (for the UI form)."""
    d, p, ext = cfg.to_dict(), DISASTER_PRESETS[cfg.disaster_type], _extent()
    for k in ("initial_radius_m", "max_radius_m", "spread_speed_mps"):
        if d[k] is None:
            d[k] = p[k]
    d["center_lat"], d["center_lon"] = to_latlon(cfg.center_x_frac * ext, cfg.center_y_frac * ext, ext)
    return d


def live_from_request(body: DisasterStartIn, session: SessionData) -> ScenarioConfig:
    """Base scenario + every option the user set. Returned, not stored: the caller attaches it to the session."""
    base = get_scenario(body.scenario_id, session)
    f = body.model_dump(exclude_none=True, exclude={"scenario_id", "strategy", "center_lat", "center_lon"})
    if "shelter_failures" in f:
        f["shelter_failures"] = [list(x) for x in f["shelter_failures"]]
    if body.center_lat is not None and body.center_lon is not None:
        ext = _extent()
        x, y = from_latlon(body.center_lat, body.center_lon, ext)
        f["center_x_frac"], f["center_y_frac"] = (min(1.0, max(0.0, v / ext)) for v in (x, y))
    cfg = replace(base, id="live", name=f"Live: {body.disaster_type}", **f)
    r = resolved(cfg)
    if r["max_radius_m"] < r["initial_radius_m"]:
        raise ValueError("max_radius_m must be >= initial_radius_m")
    return cfg


def meta() -> dict:
    """Everything the UI needs to build its option controls (same for every user)."""
    ds, ext = load_dataset(), _extent()
    return {
        "synthetic": True, "extent_m": ext,
        "bounds": [to_latlon(0, 0, ext), to_latlon(ext, ext, ext)],
        "base_population": sum(g["size"] for g in ds["population"]),
        "n_shelters_max": len(ds["shelters"]), "base_shelter_capacity": ds["shelters"][0]["capacity"],
        "disaster_types": {k: {"label": k.title(), "blurb": BLURBS.get(k, ""), **v} for k, v in DISASTER_PRESETS.items()},
        "defaults": resolved(PRESETS["expanding"]),
    }


def layers(sim) -> dict:
    """Static layers drawn once: roads, nodes (risk-map points), population."""
    G = sim.G
    pop: dict[int, int] = {}
    ordered_nodes = set()
    for a in sim.agents:
        pop[a.origin] = pop.get(a.origin, 0) + a.size
        if a.ordered:
            ordered_nodes.add(a.origin)
    ext = G.graph["extent"]
    return {
        "synthetic": True,
        "scenario": sim.cfg.to_dict(),
        "risk_levels": {"medium": RISK_LEVELS.medium, "high": RISK_LEVELS.high, "critical": RISK_LEVELS.critical},
        "bounds": [to_latlon(0, 0, ext), to_latlon(ext, ext, ext)],
        "roads": [{"a": node_latlon(G, u), "b": node_latlon(G, v), "arterial": G[u][v]["arterial"]}
                  for u, v in undirected_edges(G)],
        "nodes": [node_latlon(G, n) for n in sorted(G.nodes)],
        "population": [{"latlon": node_latlon(G, n), "people": p, "ordered": n in ordered_nodes} for n, p in pop.items()],
    }


# ---- session-level operations (open the caller's session themselves) -----------------------------
def list_for_session(sid: str) -> list[dict]:
    with STORE.existing(sid) as s:
        cfgs = [*PRESETS.values(), *s.custom_scenarios.values()]
        return [{"id": c.id, "name": c.name, "description": c.description, "config": resolved(c)} for c in cfgs]


def describe_for_session(sid: str, scenario_id: str) -> dict:
    with STORE.existing(sid) as s:
        return resolved(get_scenario(scenario_id, s))


def create_for_session(sid: str, body: ScenarioIn) -> dict:
    with STORE.session(sid) as s:
        if len(s.custom_scenarios) >= MAX_CUSTOM_SCENARIOS:
            raise ValueError(f"At most {MAX_CUSTOM_SCENARIOS} custom scenarios per session")
        cid = f"custom-{len(s.custom_scenarios) + 1}"
        data = body.model_dump()
        data["shelter_failures"] = [list(x) for x in body.shelter_failures]
        s.custom_scenarios[cid] = ScenarioConfig(id=cid, **data)
        return s.custom_scenarios[cid].to_dict()