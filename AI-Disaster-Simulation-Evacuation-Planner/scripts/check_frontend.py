"""Static frontend check:  python scripts/check_frontend.py

1. every id the JavaScript looks up exists in index.html (catches a controller written for a different HTML)
2. every script referenced by index.html exists
3. every JS file passes `node --check` (skipped with a note if Node is not installed)
Exit code 1 on any problem.
"""
import glob
import re
import shutil
import subprocess
import sys
from pathlib import Path

FRONT = Path(__file__).resolve().parents[1] / "frontend"
DYNAMIC = {"tab-live", "tab-routes", "tab-compare"}       # built as $('tab-' + name) in app.js


def main() -> int:
    problems = []
    html = (FRONT / "index.html").read_text(encoding="utf-8")
    ids = set(re.findall(r'\bid="([^"]+)"', html))
    used = {}
    for f in sorted(glob.glob(str(FRONT / "js" / "*.js"))):
        src = Path(f).read_text(encoding="utf-8")
        for m in re.findall(r"\$\('([A-Za-z0-9_-]+)'\)", src) + re.findall(r"getElementById\('([A-Za-z0-9_-]+)'\)", src):
            used.setdefault(m, Path(f).name)
    missing = sorted(i for i in used if i not in ids and i not in DYNAMIC)
    problems += [f"id '{i}' used in {used[i]} but missing from index.html" for i in missing]
    scripts = re.findall(r'<script src="(js/[^"]+)"', html)
    problems += [f"index.html loads {s} which does not exist" for s in scripts if not (FRONT / s).is_file()]
    unused = sorted(Path(f).name for f in glob.glob(str(FRONT / "js" / "*.js")) if f"js/{Path(f).name}" not in scripts)
    node = shutil.which("node")
    for f in sorted(glob.glob(str(FRONT / "js" / "*.js"))):
        if node:
            r = subprocess.run([node, "--check", f], capture_output=True, text=True)
            if r.returncode:
                problems.append(f"syntax error in {Path(f).name}: {r.stderr.strip().splitlines()[0]}")
    print(f"ids in index.html: {len(ids)} | ids used by JS: {len(used)} | scripts loaded: {len(scripts)}"
          f" | node syntax check: {'done' if node else 'SKIPPED (node not found)'}")
    if unused:
        print("note: JS files not loaded by index.html:", unused)
    for p in problems:
        print("PROBLEM:", p)
    print("frontend check:", "FAILED" if problems else "OK")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())