"""Build a processed dataset from raw real-world files.

  python scripts/build_dataset.py --name my_city ^
      --roads data/raw/roads/roads.geojson --population data/raw/population/population.csv ^
      --shelters data/raw/shelters/shelters.csv --roads-license "ODbL" --population-license "CC BY 4.0"

Writes data/processed/<name>.json and <name>.manifest.json (input checksums, parameters, what was dropped,
assumptions, validation). Then activate it with  PLANNER_DATASET=data/processed/<name>.json  in .env.
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config.settings import DATA_DIR  # noqa: E402
from src.data.preprocessing import build_real_dataset, write_dataset  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True, help="dataset name (letters, digits, _ and -)")
    ap.add_argument("--roads", default=str(DATA_DIR / "raw" / "roads" / "roads.geojson"))
    ap.add_argument("--population", default=str(DATA_DIR / "raw" / "population" / "population.csv"))
    ap.add_argument("--shelters", default=str(DATA_DIR / "raw" / "shelters" / "shelters.csv"))
    ap.add_argument("--out-dir", default=str(DATA_DIR / "processed"))
    ap.add_argument("--group-size", type=int, default=25, help="people per evacuee group")
    ap.add_argument("--walking-fraction", type=float, default=0.15, help="ASSUMED share of groups on foot")
    ap.add_argument("--max-warning-delay", type=float, default=900.0, help="ASSUMED max warning delay, seconds")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--snap-m", type=float, default=1.0, help="road vertices closer than this become one node")
    ap.add_argument("--max-snap-distance", type=float, default=500.0, help="drop points farther than this from any road")
    for layer in ("roads", "population", "shelters"):
        ap.add_argument(f"--{layer}-license", default="not recorded", help=f"licence of the {layer} source")
    ap.add_argument("--notes", default="", help="free-text description stored in the dataset")
    a = ap.parse_args(argv)

    if not re.fullmatch(r"[A-Za-z0-9_-]+", a.name):
        print("error: --name may only contain letters, digits, '_' and '-'", file=sys.stderr)
        return 2
    for label, p in (("roads", a.roads), ("population", a.population), ("shelters", a.shelters)):
        if not Path(p).is_file():
            print(f"error: {label} file not found: {p}\n       see data/README.md for the expected format and location",
                  file=sys.stderr)
            return 2
    try:
        ds, manifest = build_real_dataset(
            a.roads, a.population, a.shelters, name=a.name, group_size=a.group_size,
            walking_fraction=a.walking_fraction, max_warning_delay_s=a.max_warning_delay, seed=a.seed,
            snap_m=a.snap_m, max_snap_distance_m=a.max_snap_distance, notes=a.notes,
            licenses={"roads": a.roads_license, "population": a.population_license, "shelters": a.shelters_license})
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    data_path, man_path = write_dataset(ds, manifest, a.out_dir)
    s = manifest["validation"]["stats"]
    print(f"Built '{a.name}': {s['nodes']:,} nodes, {s['edges']:,} roads, {s['population_groups']:,} groups "
          f"({s['population']:,.0f} people), {s['shelters']} shelters (capacity {s['shelter_capacity']:,.0f})")
    print("Dropped:", {k: {kk: vv for kk, vv in v.items() if kk != 'examples' and vv} for k, v in manifest["dropped"].items()})
    for w in manifest["validation"]["warnings"]:
        print("warning:", w)
    print(f"\nWrote {data_path}\nWrote {man_path}\n\nTo use it, add this line to .env and restart:\n  PLANNER_DATASET={Path(a.out_dir) / (a.name + '.json')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())