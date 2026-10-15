"""Check a dataset file against the contract.   python scripts/validate_dataset.py [path]

Default path = the active dataset (PLANNER_DATASET or the synthetic demo). Exit code 1 if there are errors.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config.settings import DATASET_PATH  # noqa: E402
from src.data.schema import dataset_kind, validate_dataset  # noqa: E402


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    path = Path(argv[0]) if argv else DATASET_PATH
    if not path.is_file():
        print(f"error: not found: {path}", file=sys.stderr)
        return 2
    try:
        ds = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"error: {path.name} is not valid JSON: {exc}", file=sys.stderr)
        return 1
    report = validate_dataset(ds)
    kind = dataset_kind(ds) if report.ok else "unknown"
    print(f"{path.name}: {'OK' if report.ok else 'INVALID'}  (data kind: {kind})")
    print("stats:", report.stats)
    for e in report.errors:
        print("ERROR  ", e)
    for w in report.warnings:
        print("warning", w)
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())