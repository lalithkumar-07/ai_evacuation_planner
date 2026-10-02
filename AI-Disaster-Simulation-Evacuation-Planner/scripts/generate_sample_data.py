"""Generate data/sample/demo_scenario.json (SYNTHETIC). Usage: python scripts/generate_sample_data.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config.settings import DEMO_SCENARIO_PATH  # noqa: E402
from src.data.preprocessing import generate_synthetic_dataset  # noqa: E402

if __name__ == "__main__":
    ds = generate_synthetic_dataset()
    DEMO_SCENARIO_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEMO_SCENARIO_PATH.write_text(json.dumps(ds, separators=(",", ":")))
    print(f"wrote {DEMO_SCENARIO_PATH}: {len(ds['nodes'])} nodes, {len(ds['edges'])} roads, "
          f"{len(ds['population'])} population groups, {len(ds['shelters'])} shelters")
