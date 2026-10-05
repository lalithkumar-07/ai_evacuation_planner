from dataclasses import replace

from fastapi.testclient import TestClient

from backend.main import app
from config.settings import ScenarioConfig
from src.simulation.metrics import summarize
from src.simulation.simulation_engine import Simulation


def _run(strategy, **kw):
    sim = Simulation(replace(ScenarioConfig(), **{"duration_s": 5400, **kw}), strategy)
    sim.run()
    return sim


def test_people_and_capacity_conserved():
    for strat in ("baseline", "proposed"):
        sim = _run(strat)
        inside = sum(a.size for a in sim.agents if a.status.value == "AT_SHELTER")
        assert inside == sum(s.occupancy for s in sim.shelters)
        assert all(s.occupancy <= s.capacity for s in sim.shelters)


def test_deterministic():
    assert summarize(_run("proposed")) == summarize(_run("proposed"))


def test_no_hazard_everyone_served_with_proposed():
    m = summarize(_run("proposed", disaster_enabled=False, duration_s=10800))
    assert m["success_rate"] == 1.0 and m["risk_exposure_person_hazard_s"] == 0


def test_proposed_reroutes_when_shelter_fails():
    sim = _run("proposed", shelter_failures=[[0, 900], [1, 1500]])
    assert sim.reroute_count > 0
    assert sim.shelters[0].status.value == "UNSAFE"


def test_metrics_are_computed_not_constant():
    a, b = summarize(_run("baseline")), summarize(_run("proposed"))
    assert a["person_minutes_in_hazard"] != b["person_minutes_in_hazard"]


def test_api_end_to_end():
    c = TestClient(app)
    assert c.post("/api/simulation/step", json={"steps": 1}).status_code == 409      # nothing started yet
    r = c.post("/api/disaster/start", json={"disaster_type": "flood", "intensity": 0.8, "scenario_id": "expanding"})
    assert r.status_code == 200
    body = r.json()
    assert body["layers"]["synthetic"] is True and body["plan"]["proposed"] and body["plan"]["baseline"]
    assert c.post("/api/simulation/step", json={"steps": 4}).json()["time_s"] == 120
    walled = c.post("/api/evacuation/plan", json={"lat": 17.385, "lon": 78.4867}).json()
    assert walled["proposed"] is None            # disaster centre: every road around it is blocked
    p = c.post("/api/evacuation/plan", json={"lat": 17.40, "lon": 78.50}).json()
    assert p["proposed"]["path"]
    c.post("/api/simulation/pause")
    assert c.post("/api/simulation/step", json={"steps": 1}).status_code == 409
    c.post("/api/simulation/resume")
    assert c.post("/api/disaster/update", json={"intensity": 0.5}).status_code == 200
    assert c.get("/api/disaster/risk-map").json()["nodes"][0]["level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert c.post("/api/simulation/reset").json()["time_s"] == 0
    assert c.post("/api/disaster/start", json={"disaster_type": "meteor"}).status_code == 422
    assert c.get("/api/scenarios/nope").status_code == 404
    assert len(c.get("/api/scenarios").json()) >= 7
    assert c.get("/").status_code == 200


def test_meta_and_scenario_options():
    c = TestClient(app)
    m = c.get("/api/meta").json()
    assert set(m["disaster_types"]) >= {"flood", "wildfire", "earthquake"} and m["n_shelters_max"] >= 8
    sc = c.get("/api/scenarios").json()
    assert len(sc) == 7 and sc[0]["config"]["initial_radius_m"] is not None
    body = {"disaster_type": "wildfire", "intensity": 0.7, "center_lat": m["bounds"][0][0] + 0.01,
            "center_lon": m["bounds"][0][1] + 0.01, "initial_radius_m": 500, "max_radius_m": 1200,
            "spread_speed_mps": 0.5, "population_scale": 2.0, "n_shelters": 3, "shelter_capacity_scale": 0.5,
            "road_closure_count": 4, "road_closure_time_s": 120, "shelter_failures": [[0, 600]], "duration_s": 3600}
    r = c.post("/api/disaster/start", json=body).json()
    cfg = r["layers"]["scenario"]
    assert cfg["n_shelters"] == 3 and len(r["state"]["shelters"]) == 3 and cfg["population_scale"] == 2.0
    assert r["state"]["metrics"]["total_population"] == 12000 and r["state"]["disaster"]["radius_m"] == 500
    assert c.post("/api/disaster/start", json={**body, "max_radius_m": 100}).status_code == 422
    assert c.post("/api/disaster/start", json={"disaster_enabled": False}).json()["state"]["disaster"] is None