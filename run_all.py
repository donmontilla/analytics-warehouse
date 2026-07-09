"""
One-command rebuild of the entire project:
    python run_all.py

Runs, in order:
  1. scripts/generate_data.py   -> data/raw_*.csv
  2. scripts/build_warehouse.py -> warehouse.duckdb (clean + star schema)
  3. scripts/make_charts.py     -> assets/*.png
  4. scripts/run_queries.py     -> prints every business-question result

Everything is deterministic (fixed seed), so results reproduce exactly.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

STEPS = [
    ("Generating synthetic data",      "scripts/generate_data.py"),
    ("Building warehouse (clean + star schema)", "scripts/build_warehouse.py"),
    ("Rendering charts",               "scripts/make_charts.py"),
]

def main():
    for label, script in STEPS:
        print(f"\n{'='*70}\n{label}\n{'='*70}")
        r = subprocess.run([PY, os.path.join(ROOT, script)], cwd=ROOT)
        if r.returncode != 0:
            sys.exit(f"Step failed: {script}")
    print(f"\n{'='*70}\nRunning all business-question queries\n{'='*70}")
    subprocess.run([PY, os.path.join(ROOT, "scripts/run_queries.py")], cwd=ROOT)
    print("\nDone. Open the SQL files in sql/ and the charts in assets/.")

if __name__ == "__main__":
    main()
