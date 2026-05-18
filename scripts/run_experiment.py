#!/usr/bin/env python3
"""Run a single LLM repair experiment and write structured artifacts to runs/.

Usage:
    python scripts/run_experiment.py claims/wrong_magnetic_rank.json \\
        --run-id 001_wrong_magnetic_rank_sonnet \\
        [--model claude-sonnet-4-6] \\
        [--max-iterations 4]

Output directory: runs/<run_id>/
    initial_claim.json      input broken claim
    certificate_before.json verifier output on the initial claim
    final_claim.json        claim after repair (converged or last attempt)
    certificate_after.json  verifier output on the final claim
    trace.json              full LLMRepairResult iteration log
    metrics.json            summary metrics for aggregate_runs.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running from repo root without installing
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dualitycert.agent import run_llm_repair_loop
from dualitycert.qft.claims import build_claim_from_data
from dualitycert.qft.critic import build_repair_hints
from dualitycert.qft.dualities import evaluate_claim


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("claim_file", help="Path to JSON claim file.")
    parser.add_argument("--run-id", required=True, help="Unique run identifier (used as directory name).")
    parser.add_argument("--model", default="claude-sonnet-4-6")
    parser.add_argument("--max-iterations", type=int, default=4)
    parser.add_argument("--runs-dir", default="runs", help="Root directory for run artifacts.")
    args = parser.parse_args(argv)

    claim_path = Path(args.claim_file)
    if not claim_path.exists():
        print(f"error: claim file not found: {claim_path}", file=sys.stderr)
        return 2

    initial_data = json.loads(claim_path.read_text(encoding="utf-8"))

    out_dir = Path(args.runs_dir) / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    # Certificate before
    claim_before = build_claim_from_data(initial_data)
    cert_before = evaluate_claim(claim_before)

    # Run repair loop
    result = run_llm_repair_loop(
        initial_data,
        model=args.model,
        max_iterations=args.max_iterations,
    )

    # Final claim data: last iteration's claim_data
    final_data = result.iterations[-1].claim_data

    # Write artifacts
    (out_dir / "initial_claim.json").write_text(
        json.dumps(initial_data, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "certificate_before.json").write_text(
        cert_before.to_json() + "\n", encoding="utf-8"
    )
    (out_dir / "final_claim.json").write_text(
        json.dumps(final_data, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "certificate_after.json").write_text(
        result.final_certificate.to_json() + "\n", encoding="utf-8"
    )

    trace_data = _serialize_trace(result)
    (out_dir / "trace.json").write_text(
        json.dumps(trace_data, indent=2) + "\n", encoding="utf-8"
    )

    # Metrics
    failed_before = [r.name for r in cert_before.failed_obligations]
    failed_after = [r.name for r in result.final_certificate.failed_obligations]
    parse_errors = sum(1 for it in result.iterations if it.parse_error is not None)

    # Hint types that were present before and are now absent after convergence
    hints_before = build_repair_hints(claim_before, cert_before)
    resolved_hint_types = (
        [h.type for h in hints_before] if result.converged else []
    )

    metrics = {
        "run_id": args.run_id,
        "fixture": claim_path.stem,
        "model": result.model,
        "converged": result.converged,
        "iteration_count": result.iteration_count,
        "final_outward_status": result.final_outward_status,
        "failed_obligations_before": failed_before,
        "failed_obligations_after": failed_after,
        "parse_error_count": parse_errors,
        "failure_types_resolved": resolved_hint_types,
    }
    (out_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n", encoding="utf-8"
    )

    print(f"Run artifacts written to: {out_dir}")
    print(f"  converged={result.converged}  iterations={result.iteration_count}  status={result.final_outward_status}")
    return 0 if result.converged else 1


def _serialize_trace(result) -> dict:
    return {
        "model": result.model,
        "converged": result.converged,
        "final_outward_status": result.final_outward_status,
        "iterations": [
            {
                "iteration": it.iteration,
                "outward_status": it.outward_status,
                "failed_obligation_names": list(it.failed_obligation_names),
                "claim_data": it.claim_data,
                "prompt_sent": it.prompt_sent,
                "llm_raw_response": it.llm_raw_response,
                "llm_repaired_data": it.llm_repaired_data,
                "parse_error": it.parse_error,
            }
            for it in result.iterations
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
