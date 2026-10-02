"""Evaluation metrics computed from an executed simulation. Nothing is estimated or hard-coded."""
from __future__ import annotations

from src.simulation.agent import AgentStatus as S


def summarize(sim) -> dict:
    ordered = [a for a in sim.agents if a.ordered]
    total = sum(a.size for a in ordered)
    arrived = [a for a in ordered if a.status == S.AT_SHELTER]
    arrived_people = sum(a.size for a in arrived)
    trips = [(a.end_at - a.start_at, a.size) for a in arrived]
    complete = bool(ordered) and arrived_people == total
    cap = sum(s.capacity for s in sim.shelters)
    cong = [r["congestion_mean"] for r in sim.history if r["congestion_mean"] > 0]
    return {
        "strategy": sim.strategy.name,
        "ordered_population": total,
        "evacuated_population": arrived_people,
        "evacuation_complete": complete,
        "evacuation_time_s": max(a.end_at for a in arrived) if complete else None,
        "time_to_90pct_s": next((r["t"] for r in sim.history if total and r["evacuated"] >= 0.9 * total), None),
        "avg_trip_time_s": sum(d * n for d, n in trips) / arrived_people if arrived_people else None,  # arrived only
        "max_trip_time_s": max((d for d, _ in trips), default=None),                                     # arrived only
        "risk_exposure_person_hazard_s": sim.exposure_person_s,
        "person_minutes_in_hazard": sim.person_s_in_hazard / 60.0,
        "success_rate": arrived_people / total if total else None,
        "shelter_utilization": sum(s.occupancy for s in sim.shelters) / cap if cap else None,
        "congestion_mean": sum(cong) / len(cong) if cong else 0.0,
        "congestion_peak": max((r["congestion_peak"] for r in sim.history), default=0.0),
        "route_failures": sim.route_failures,
        "route_failure_rate": sim.route_failures / len(ordered) if ordered else None,
        "rerouting_count": sim.reroute_count,
        "unserved_population": total - arrived_people,
        "trapped_population": sum(a.size for a in ordered if a.status == S.TRAPPED),
        "sim_end_time_s": sim.t,
    }
