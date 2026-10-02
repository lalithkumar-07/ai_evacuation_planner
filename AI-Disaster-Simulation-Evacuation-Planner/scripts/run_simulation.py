"""Headless run: python scripts/run_simulation.py [scenario_id]  -> baseline vs proposed table."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.services.scenario_service import get_scenario  # noqa: E402
from backend.services.simulation_service import run_comparison  # noqa: E402

KEYS = ["evacuation_time_s", "time_to_90pct_s", "avg_trip_time_s", "max_trip_time_s", "person_minutes_in_hazard",
        "success_rate", "shelter_utilization", "congestion_peak", "route_failures", "rerouting_count",
        "unserved_population"]

if __name__ == "__main__":
    r = run_comparison(get_scenario(sys.argv[1] if len(sys.argv) > 1 else "expanding"))
    f = lambda v: "-" if v is None else (f"{v:,.2f}" if isinstance(v, float) else str(v))
    print(f"{'metric':32s}{'baseline':>14s}{'proposed':>14s}")
    for k in KEYS:
        print(f"{k:32s}{f(r['baseline']['summary'][k]):>14s}{f(r['proposed']['summary'][k]):>14s}")
