from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AgentStatus(str, Enum):
    AT_HOME = "AT_HOME"
    TRAVELING = "TRAVELING"
    WAITING = "WAITING"
    REROUTING = "REROUTING"
    AT_SHELTER = "AT_SHELTER"
    TRAPPED = "TRAPPED"
    SAFE = "SAFE"        # not ordered to evacuate


@dataclass
class Agent:
    """A group of evacuees moving together (`size` people)."""
    id: int
    origin: int
    size: int
    mobility: str                 # "walking" | "vehicle"
    vulnerability: float
    ordered: bool
    start_at: float
    node: int = 0                 # current node (departure node while on an edge)
    next_node: int | None = None
    progress: float = 0.0         # metres along current edge
    destination: int | None = None
    route: list[int] = field(default_factory=list)
    status: AgentStatus = AgentStatus.AT_HOME
    risk_exposure: float = 0.0    # sum(hazard * seconds)
    end_at: float | None = None
    reroutes: int = 0
    wait_s: float = 0.0
    needs_reroute: bool = False
    failure_counted: bool = False
