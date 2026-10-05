"""Phase 2: session isolation, expiry, eviction, validation and thread-safety."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import simulation_service as svc
from backend.services.session_store import (DEFAULT_SESSION_ID, STORE, InvalidSessionId, SessionStore,
                                            validate_session_id)
from config.settings import ScenarioConfig

A_ID, B_ID = "user-aaaaaaaa-0001", "user-bbbbbbbb-0002"


def client(sid=None) -> TestClient:
    return TestClient(app, headers={"X-Session-Id": sid} if sid else {})


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


# ---------------------------------------------------------------- SessionStore (unit) -------------
def test_same_id_same_session_different_ids_different_sessions():
    store = SessionStore(ttl_s=60, max_sessions=5, clock=Clock())
    with store.session("session-one") as a1:
        a1.strategy = "proposed"
    with store.session("session-one") as a2, store.session("session-two") as b:
        assert a2 is a1 and a2.strategy == "proposed"
        assert b is not a1 and b.strategy == ""


def test_idle_session_expires_but_activity_keeps_it_alive():
    clock = Clock()
    store = SessionStore(ttl_s=10, max_sessions=5, clock=clock)
    with store.session("session-one") as s1:
        s1.strategy = "x"
    clock.t = 8
    with store.session("session-one"):          # touched at t=8 -> idle timer restarts
        pass
    clock.t = 15                                # 7 s idle < ttl
    assert store.peek("session-one") is not None
    clock.t = 30                                # 22 s idle > ttl
    assert store.peek("session-one") is None
    with store.session("session-one") as s2:
        assert s2 is not s1 and s2.strategy == ""


def test_least_recently_used_session_is_evicted_when_full():
    clock = Clock()
    store = SessionStore(ttl_s=1000, max_sessions=2, clock=clock)
    for t, sid in enumerate(["session-aaa", "session-bbb"]):
        clock.t = t
        with store.session(sid):
            pass
    clock.t = 5
    with store.session("session-aaa"):          # A becomes most recent, so B is the LRU
        pass
    clock.t = 6
    with store.session("session-ccc"):
        pass
    assert len(store) == 2
    assert store.peek("session-bbb") is None
    assert store.peek("session-aaa") is not None and store.peek("session-ccc") is not None


def test_peek_does_not_create_or_refresh():
    clock = Clock()
    store = SessionStore(ttl_s=10, max_sessions=2, clock=clock)
    assert store.peek("session-none") is None and len(store) == 0
    with store.session("session-one"):
        pass
    clock.t = 9
    store.peek("session-one")                   # must not extend life
    clock.t = 11
    assert store.peek("session-one") is None


def test_delete():
    store = SessionStore(ttl_s=10, max_sessions=2)
    with store.session("session-one"):
        pass
    assert store.delete("session-one") is True and store.delete("session-one") is False


def test_session_id_validation():
    assert validate_session_id(None) == DEFAULT_SESSION_ID == validate_session_id("")
    assert validate_session_id("0f8fad5b-d9cb-469f-a165-70867728950e")
    for bad in ["short", "has space 12345", "semi;colon-12345", "x" * 65, "../../etc/passwd", "default"]:
        with pytest.raises(InvalidSessionId):
            validate_session_id(bad)


# ---------------------------------------------------------------- API isolation ------------------
def test_second_user_starting_a_scenario_does_not_replace_the_first_users_simulation():
    """The defect found in the Phase 1 audit."""
    A, B = client(A_ID), client(B_ID)
    A.post("/api/disaster/start", json={"disaster_type": "flood", "intensity": 0.9})
    assert A.post("/api/simulation/step", json={"steps": 10}).json()["time_s"] == 300

    B.post("/api/disaster/start", json={"disaster_type": "earthquake", "intensity": 0.5})
    a_status = A.get("/api/simulation/status").json()
    assert a_status["time_s"] == 300                                   # untouched by B
    assert A.post("/api/simulation/step", json={"steps": 1}).json()["disaster"]["kind"] == "flood"
    assert B.post("/api/simulation/step", json={"steps": 1}).json()["time_s"] == 30
    assert B.get("/api/simulation/status").json()["scenario_id"] == "live"


def test_new_session_has_no_simulation_even_when_another_user_has_one():
    A, B = client(A_ID), client(B_ID)
    A.post("/api/disaster/start", json={})
    assert B.post("/api/simulation/step", json={"steps": 1}).status_code == 409
    assert B.get("/api/metrics").status_code == 409
    assert B.get("/api/disaster/risk-map").status_code == 409
    assert B.post("/api/evacuation/plan", json={}).status_code == 409


def test_pause_is_per_session():
    A, B = client(A_ID), client(B_ID)
    for c in (A, B):
        c.post("/api/disaster/start", json={})
    A.post("/api/simulation/pause")
    assert A.post("/api/simulation/step", json={"steps": 1}).status_code == 409
    assert B.post("/api/simulation/step", json={"steps": 1}).status_code == 200


def test_reset_only_resets_own_simulation():
    A, B = client(A_ID), client(B_ID)
    for c in (A, B):
        c.post("/api/disaster/start", json={})
        c.post("/api/simulation/step", json={"steps": 4})
    assert A.post("/api/simulation/reset").json()["time_s"] == 0
    assert B.get("/api/simulation/status").json()["time_s"] == 120


def test_disaster_update_only_affects_own_session():
    A, B = client(A_ID), client(B_ID)
    for c in (A, B):
        c.post("/api/disaster/start", json={"intensity": 0.9})
    A.post("/api/disaster/update", json={"intensity": 0.4})
    assert A.post("/api/simulation/step", json={"steps": 1}).json()["disaster"]["intensity"] == 0.4
    assert B.post("/api/simulation/step", json={"steps": 1}).json()["disaster"]["intensity"] == 0.9


def test_custom_scenarios_are_private_to_a_session():
    A, B = client(A_ID), client(B_ID)
    created = A.post("/api/scenarios", json={"name": "mine", "total_population": 500}).json()
    cid = created["id"]
    assert cid in [s["id"] for s in A.get("/api/scenarios").json()]
    assert cid not in [s["id"] for s in B.get("/api/scenarios").json()]
    assert A.get(f"/api/scenarios/{cid}").status_code == 200
    assert B.get(f"/api/scenarios/{cid}").status_code == 404
    assert B.post("/api/simulation/start", json={"scenario_id": cid}).status_code == 404
    assert A.post("/api/simulation/start", json={"scenario_id": cid}).status_code == 200


def test_custom_scenario_limit_per_session(monkeypatch):
    from backend.services import scenario_service
    monkeypatch.setattr(scenario_service, "MAX_CUSTOM_SCENARIOS", 2)
    A, B = client(A_ID), client(B_ID)
    assert [A.post("/api/scenarios", json={}).status_code for _ in range(3)] == [201, 201, 422]
    assert B.post("/api/scenarios", json={}).status_code == 201             # B's quota is separate


def test_two_users_can_use_the_same_custom_id_without_clashing():
    A, B = client(A_ID), client(B_ID)
    ia = A.post("/api/scenarios", json={"name": "A's", "total_population": 500}).json()
    ib = B.post("/api/scenarios", json={"name": "B's", "total_population": 900}).json()
    assert ia["id"] == ib["id"] == "custom-1"
    assert A.get("/api/scenarios/custom-1").json()["name"] == "A's"
    assert B.get("/api/scenarios/custom-1").json()["name"] == "B's"


def test_live_scenario_is_per_session():
    A, B = client(A_ID), client(B_ID)
    assert A.get("/api/scenarios/live").status_code == 404                  # nothing generated yet
    A.post("/api/disaster/start", json={"disaster_type": "wildfire", "intensity": 0.6})
    assert A.get("/api/scenarios/live").json()["disaster_type"] == "wildfire"
    assert B.get("/api/scenarios/live").status_code == 404


def test_session_header_validation_and_default_session():
    assert client("bad id!").get("/api/session").status_code == 400
    assert client("short").post("/api/disaster/start", json={}).status_code == 400
    # no header -> shared default session: old clients and curl keep working
    d1, d2 = client(), client()
    d1.post("/api/disaster/start", json={})
    assert d2.post("/api/simulation/step", json={"steps": 2}).json()["time_s"] == 60


def test_session_info_and_delete():
    A = client(A_ID)
    assert A.get("/api/session").json()["exists"] is False                  # GET never creates a session
    A.post("/api/disaster/start", json={})
    info = A.get("/api/session").json()
    assert info["exists"] and info["has_simulation"] and info["session_id"] == A_ID and info["active_sessions"] == 1
    assert A.delete("/api/session").json() == {"deleted": True}
    assert A.post("/api/simulation/step", json={"steps": 1}).status_code == 409
    assert A.delete("/api/session").json() == {"deleted": False}


def test_expired_session_is_forgotten(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(STORE, "_clock", clock)
    monkeypatch.setattr(STORE, "ttl_s", 100)
    A = client(A_ID)
    A.post("/api/disaster/start", json={})
    clock.t = 50
    assert A.get("/api/simulation/status").status_code == 200
    clock.t = 400
    assert A.get("/api/simulation/status").status_code == 409               # session expired -> must start again


# ---------------------------------------------------------------- thread-safety ----------------------
def test_concurrent_steps_in_one_session_are_serialised():
    """8 threads x 10 single steps on ONE session: with the lock the clock must read exactly 80 * 30 s."""
    client(A_ID).post("/api/disaster/start", json={})

    def worker(_):
        c = client(A_ID)
        return [c.post("/api/simulation/step", json={"steps": 1}).status_code for _ in range(10)]

    with ThreadPoolExecutor(8) as ex:
        codes = [c for batch in ex.map(worker, range(8)) for c in batch]
    assert set(codes) == {200}
    assert client(A_ID).get("/api/simulation/status").json()["time_s"] == 80 * 30


def test_concurrent_users_progress_independently():
    kinds = ["flood", "wildfire", "earthquake", "flood"]
    ids = [f"user-concurrent-{i:04d}" for i in range(4)]
    for sid, kind in zip(ids, kinds):
        client(sid).post("/api/disaster/start", json={"disaster_type": kind})

    def worker(args):
        sid, n = args
        c = client(sid)
        for _ in range(n):
            assert c.post("/api/simulation/step", json={"steps": 1}).status_code == 200
        return sid, c.get("/api/simulation/status").json()["time_s"]

    with ThreadPoolExecutor(4) as ex:
        out = dict(ex.map(worker, [(sid, 3 * (i + 1)) for i, sid in enumerate(ids)]))
    assert out == {sid: 30.0 * 3 * (i + 1) for i, sid in enumerate(ids)}
    assert [client(s).post("/api/simulation/step", json={"steps": 1}).json()["disaster"]["kind"] for s in ids] == kinds


# ---------------------------------------------------------------- analytics cache --------------------
def _cheap(i=0, **kw):
    return replace(ScenarioConfig(), duration_s=300, intensity=0.5 + 0.05 * i, **kw)


def test_analytics_cache_is_bounded(monkeypatch):
    monkeypatch.setattr(svc, "ANALYTICS_CACHE_SIZE", 2)
    for i in range(4):
        svc.run_comparison(_cheap(i))
    assert len(svc._cache) == 2


def test_analytics_cache_ignores_scenario_name_and_id():
    svc.run_comparison(_cheap(1, id="a", name="first"))
    svc.run_comparison(_cheap(1, id="b", name="second"))
    assert len(svc._cache) == 1
    svc.run_comparison(_cheap(2))
    assert len(svc._cache) == 2


def test_analytics_endpoint_uses_callers_live_scenario():
    A, B = client(A_ID), client(B_ID)
    A.post("/api/disaster/start", json={"duration_s": 300, "intensity": 0.5})
    B.post("/api/disaster/start", json={"duration_s": 300, "intensity": 0.9})
    ra, rb = A.get("/api/analytics").json(), B.get("/api/analytics").json()
    assert ra["proposed"]["series"][-1]["t"] == 300 and rb["proposed"]["series"][-1]["t"] == 300
    assert len(svc._cache) == 2                                             # different configs -> separate entries


# ---------------------------------------------------------------- registry cannot be flooded ----------
def test_reads_and_failed_requests_do_not_create_sessions(monkeypatch):
    monkeypatch.setattr(STORE, "max_sessions", 2)
    real = client(A_ID)
    real.post("/api/disaster/start", json={})                  # the only legitimate session
    for i in range(30):                                        # 30 strangers with random ids, doing read/control calls
        c = client(f"stranger-{i:06d}")
        c.get("/api/scenarios")
        c.get("/api/session")
        assert c.post("/api/simulation/step", json={"steps": 1}).status_code == 409
        assert c.get("/api/metrics").status_code == 409
        c.delete("/api/session")
    assert len(STORE) == 1                                     # nobody was registered, nobody was evicted
    assert real.get("/api/simulation/status").status_code == 200


def test_only_generating_or_creating_registers_a_session():
    c = client(B_ID)
    assert len(STORE) == 0
    c.post("/api/scenarios", json={})
    assert len(STORE) == 1
    STORE.clear()
    client(B_ID).post("/api/simulation/start", json={"scenario_id": "static"})
    assert len(STORE) == 1