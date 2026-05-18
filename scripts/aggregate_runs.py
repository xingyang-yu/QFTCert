#!/usr/bin/env python3
"""Aggregate metrics.json files across all runs/ subdirectories.

Usage:
    python scripts/aggregate_runs.py [--runs-dir runs]

Prints a summary table to stdout.  Exits 0 always (this is a reporting tool).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-dir", default="runs")
    parser.add_argument("--json", action="store_true", help="Emit raw JSON instead of table.")
    args = parser.parse_args(argv)

    runs_dir = Path(args.runs_dir)
    if not runs_dir.is_dir():
        print(f"No runs directory found at: {runs_dir}")
        return 0

    records = []
    for metrics_path in sorted(runs_dir.glob("*/metrics.json")):
        records.append(json.loads(metrics_path.read_text(encoding="utf-8")))

    if not records:
        print("No metrics.json files found.")
        return 0

    if args.json:
        print(json.dumps(records, indent=2))
        return 0

    # Summary table
    converged = sum(1 for r in records if r["converged"])
    total = len(records)
    avg_iters = sum(r["iteration_count"] for r in records if r["converged"]) / max(converged, 1)
    total_parse_errors = sum(r["parse_error_count"] for r in records)

    print(f"{'='*64}")
    print(f"QFTCert LLM Repair Loop — Experiment Summary")
    print(f"{'='*64}")
    print(f"Total runs:           {total}")
    print(f"Converged:            {converged}/{total}  ({100*converged//total}%)")
    print(f"Avg iters (converged):{avg_iters:.1f}")
    print(f"Total parse errors:   {total_parse_errors}")
    print()

    # Per-run table
    header = f"{'run_id':<42} {'model':<22} {'conv':<6} {'iters':<6} {'status'}"
    print(header)
    print("-" * len(header))
    for r in records:
        conv = "YES" if r["converged"] else "NO"
        status = r["final_outward_status"].replace("_OBLIGATIONS", "").replace("_WITH_NOT_IMPLEMENTED", "+NI")
        print(f"{r['run_id']:<42} {r['model']:<22} {conv:<6} {r['iteration_count']:<6} {status}")

    print()

    # Failure types resolved
    all_resolved: dict[str, int] = {}
    for r in records:
        for t in r.get("failure_types_resolved", []):
            all_resolved[t] = all_resolved.get(t, 0) + 1

    if all_resolved:
        print("Failure types resolved (converged runs):")
        for ftype, count in sorted(all_resolved.items(), key=lambda x: -x[1]):
            print(f"  {ftype:<48} {count}x")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
