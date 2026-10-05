"""Per-user, in-memory simulation sessions.

* A session = one user's simulation + its scenario + any custom scenarios they created.
* Thread-safe: a short store-level lock guards the registry; each session has its own RLock so two requests
  for the same session run one after the other, while different sessions run in parallel.
* Bounded: idle sessions expire after `ttl_s`; beyond `max_sessions` the least-recently-used one is evicted.
* Deliberately free of FastAPI and simulation imports so it can be unit-tested on its own.
"""
from __future__ import annotations

import re
import threading
import time
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

from config.settings import MAX_SESSIONS, SESSION_TTL_S

DEFAULT_SESSION_ID = "default"          # used when a client sends no X-Session-Id (curl, scripts, old frontend)
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


class InvalidSessionId(ValueError):
    pass


def validate_session_id(raw: str | None) -> str:
    """No header -> the shared 'default' session (backward compatible). Otherwise it must look like an id."""
    if raw is None or raw == "":
        return DEFAULT_SESSION_ID
    if not SESSION_ID_RE.fullmatch(raw):
        raise InvalidSessionId("X-Session-Id must be 8-64 characters: letters, digits, '_' or '-'")
    return raw


@dataclass
class SessionData:
    id: str
    created_at: float
    last_used: float
    sim: Any = None                       # Simulation (typed loosely to keep this module dependency-free)
    cfg: Any = None                       # ScenarioConfig the running simulation was built from ("live" scenario)
    strategy: str = ""
    paused: bool = False
    custom_scenarios: dict[str, Any] = field(default_factory=dict)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)


class SessionStore:
    def __init__(self, ttl_s: float, max_sessions: int, clock: Callable[[], float] = time.monotonic) -> None:
        self.ttl_s, self.max_sessions, self._clock = ttl_s, max_sessions, clock
        self._sessions: OrderedDict[str, SessionData] = OrderedDict()   # oldest-used first
        self._lock = threading.Lock()

    def now(self) -> float:
        return self._clock()

    def _purge_expired(self, now: float) -> None:
        for sid in [k for k, s in self._sessions.items() if now - s.last_used > self.ttl_s]:
            del self._sessions[sid]

    def _acquire(self, sid: str) -> SessionData:
        with self._lock:
            now = self._clock()
            self._purge_expired(now)
            s = self._sessions.get(sid)
            if s is None:
                while len(self._sessions) >= self.max_sessions:
                    self._sessions.popitem(last=False)          # evict least recently used
                s = SessionData(id=sid, created_at=now, last_used=now)
                self._sessions[sid] = s
            s.last_used = now
            self._sessions.move_to_end(sid)
            return s

    @contextmanager
    def session(self, sid: str) -> Iterator[SessionData]:
        """Get-or-create the session and hold its lock for the duration of the block."""
        s = self._acquire(sid)
        with s.lock:
            yield s

    @contextmanager
    def existing(self, sid: str) -> Iterator[SessionData]:
        """Like session(), but NEVER registers a new session: for reads and controls. If the caller has no session
        they get an empty throw-away one (so 'no simulation yet' -> 409), and the registry is left untouched.
        This stops stray or malicious ids from filling the store and evicting real users' sessions."""
        with self._lock:
            now = self._clock()
            self._purge_expired(now)
            s = self._sessions.get(sid)
            if s is None:
                s = SessionData(id=sid, created_at=now, last_used=now)      # transient, not stored
            else:
                s.last_used = now
                self._sessions.move_to_end(sid)
        with s.lock:
            yield s

    def peek(self, sid: str) -> SessionData | None:
        """Look up without creating or refreshing the idle timer."""
        with self._lock:
            self._purge_expired(self._clock())
            return self._sessions.get(sid)

    def delete(self, sid: str) -> bool:
        with self._lock:
            return self._sessions.pop(sid, None) is not None

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)

    def stats(self) -> dict:
        return {"active_sessions": len(self), "max_sessions": self.max_sessions, "ttl_s": self.ttl_s}


STORE = SessionStore(SESSION_TTL_S, MAX_SESSIONS)       # the process-wide registry