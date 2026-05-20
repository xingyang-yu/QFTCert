"""Accuracy and breakdown metrics for the Phase 2c-a detection benchmark.

The runner writes `results.jsonl` (one line per fixture) and this
module turns that record list — plus the source fixtures — into the
`summary.json` blob that gets committed alongside each run.

Locked summary shape (Rule 10, plan §10 "Runner outputs"):

    {
      "n_total": int,
      "n_correct": int,
      "accuracy": float,
      "accuracy_by_class": {"dual": float, "not_dual": float},
      "accuracy_by_source": {"dp0_toric": float, "f0_phase_ii": float, ...},
      "accuracy_by_perturbation_type": {"none": float, "w_drop": float, ...},
      "confusion_matrix": {
        "dual": {"dual": int, "not_dual": int},
        "not_dual": {"dual": int, "not_dual": int}
      },
      "latency_s": {"min": ..., "median": ..., "mean": ..., "max": ...},
      "tokens": {"input": ..., "output": ...}     # totals
    }

"accuracy_by_source" plays the role of the plan's "accuracy_by_seed":
the analytically interesting bucket is the source seed theory family
(`dp0_toric` / `f0_phase_ii`), not the per-fixture RNG seed.
"""

from __future__ import annotations

import statistics
from typing import Any, Iterable, Mapping

from dualitycert.benchmark.fixtures import Fixture


__all__ = [
    "ResultRecord",
    "build_summary",
]


# Type alias — kept as a TypedDict-like Mapping so the runner can build
# records without importing this module. The runner is the source of
# truth for the schema; this module is a consumer.
ResultRecord = Mapping[str, Any]


def build_summary(
    results: Iterable[ResultRecord],
    fixtures: Iterable[Fixture],
) -> dict[str, Any]:
    """Compute the summary.json payload from results + source fixtures.

    Inputs must be parallel (same fixture_id at each index). The
    function is order-independent for accuracy / matrix, but the
    latency_s and tokens aggregates respect input order trivially.
    """

    results_list = list(results)
    fixtures_list = list(fixtures)

    if len(results_list) != len(fixtures_list):
        raise ValueError(
            f"results / fixtures length mismatch: "
            f"len(results)={len(results_list)}, len(fixtures)={len(fixtures_list)}"
        )

    by_id_fix = {f.fixture_id: f for f in fixtures_list}
    n_total = len(results_list)
    n_correct = 0

    counts_by_class: dict[str, int] = {}
    correct_by_class: dict[str, int] = {}
    counts_by_source: dict[str, int] = {}
    correct_by_source: dict[str, int] = {}
    counts_by_ptype: dict[str, int] = {}
    correct_by_ptype: dict[str, int] = {}

    confusion: dict[str, dict[str, int]] = {
        "dual": {"dual": 0, "not_dual": 0},
        "not_dual": {"dual": 0, "not_dual": 0},
    }

    latencies: list[float] = []
    total_input_tokens = 0
    total_output_tokens = 0

    for record in results_list:
        fid = record["fixture_id"]
        if fid not in by_id_fix:
            raise ValueError(
                f"results record references fixture_id {fid!r} "
                "not present in fixtures input"
            )
        fixture = by_id_fix[fid]
        gt = fixture.ground_truth_label
        decision = record["llm_decision"]
        correct = bool(record["correct"])
        n_correct += int(correct)

        counts_by_class[gt] = counts_by_class.get(gt, 0) + 1
        correct_by_class[gt] = correct_by_class.get(gt, 0) + int(correct)

        source = fixture.metadata.source
        counts_by_source[source] = counts_by_source.get(source, 0) + 1
        correct_by_source[source] = correct_by_source.get(source, 0) + int(correct)

        ptype = fixture.metadata.perturbation_type
        counts_by_ptype[ptype] = counts_by_ptype.get(ptype, 0) + 1
        correct_by_ptype[ptype] = correct_by_ptype.get(ptype, 0) + int(correct)

        if gt in confusion and decision in confusion[gt]:
            confusion[gt][decision] += 1

        latency_s = record.get("latency_s")
        if latency_s is not None:
            latencies.append(float(latency_s))
        if record.get("input_tokens") is not None:
            total_input_tokens += int(record["input_tokens"])
        if record.get("output_tokens") is not None:
            total_output_tokens += int(record["output_tokens"])

    accuracy = (n_correct / n_total) if n_total else 0.0
    accuracy_by_class = _ratio_table(correct_by_class, counts_by_class)
    accuracy_by_source = _ratio_table(correct_by_source, counts_by_source)
    accuracy_by_ptype = _ratio_table(correct_by_ptype, counts_by_ptype)

    summary: dict[str, Any] = {
        "n_total": n_total,
        "n_correct": n_correct,
        "accuracy": accuracy,
        "accuracy_by_class": accuracy_by_class,
        "accuracy_by_source": accuracy_by_source,
        "accuracy_by_perturbation_type": accuracy_by_ptype,
        "counts_by_class": counts_by_class,
        "counts_by_source": counts_by_source,
        "counts_by_perturbation_type": counts_by_ptype,
        "confusion_matrix": confusion,
    }
    if latencies:
        summary["latency_s"] = {
            "min": min(latencies),
            "median": statistics.median(latencies),
            "mean": statistics.fmean(latencies),
            "max": max(latencies),
        }
    if total_input_tokens or total_output_tokens:
        summary["tokens"] = {
            "input": total_input_tokens,
            "output": total_output_tokens,
        }
    return summary


def _ratio_table(
    numerators: dict[str, int],
    denominators: dict[str, int],
) -> dict[str, float]:
    """{key: numerator/denominator} with 0.0 for missing denominators."""

    out: dict[str, float] = {}
    for key, denom in denominators.items():
        out[key] = (numerators.get(key, 0) / denom) if denom else 0.0
    return out
