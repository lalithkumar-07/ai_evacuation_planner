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
    assert c.post("/api/simulation/step", json={"steps": 1}).status_code in (200, 409)
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
