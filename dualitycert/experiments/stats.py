"""Statistics + publication-ready reporting (Deliverable 8).

Pure-stdlib (the repo has no scipy/statsmodels). Provides:

  - `wilson_interval` : 95% Wilson score CI for a proportion.
  - cell tables       : per-depth / per-class / per-source / per-cell
                        accuracy with Wilson CIs, for detection,
                        diagnosis, and repair success.
  - tidy CSV export   : one row per fixture x model x arm, ready for
                        external mixed-effects (GLMM) modeling in R/Python.
  - attrition summary : counts by reason / depth / class.

We deliberately do NOT fit a GLMM here; the tidy CSV is the handoff.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


__all__ = [
    "attrition_summary",
    "cell_table",
    "detection_cell_tables",
    "diagnosis_cell_tables",
    "proportion_ci",
    "repair_cell_tables",
    "tidy_detection_rows",
    "tidy_repair_rows",
    "wilson_interval",
    "write_tidy_csv",
]


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for k successes out of n (z=1.96).

    center     = (p + z^2/2n) / (1 + z^2/n)
    half_width = z*sqrt(p(1-p)/n + z^2/4n^2) / (1 + z^2/n)
    Returns (low, high), clamped to [0, 1]. n=0 -> (0.0, 0.0).
    """

    if n <= 0:
        return (0.0, 0.0)
    p = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def proportion_ci(k: int, n: int, z: float = 1.96) -> dict[str, Any]:
    low, high = wilson_interval(k, n, z)
    return {
        "n": int(n),
        "k": int(k),
        "p": (k / n) if n else 0.0,
        "wilson_low": low,
        "wilson_high": high,
    }


def cell_table(
    rows: Iterable[Mapping[str, Any]],
    group_key: Callable[[Mapping[str, Any]], str],
    correct_key: str,
) -> dict[str, dict[str, Any]]:
    """Group rows by `group_key`; report proportion + Wilson CI per cell.

    `correct_key` is a boolean-ish field on each row (e.g.
    "detection_correct", "diagnosis_exact_match", "success").
    """

    agg: dict[str, list[int]] = {}
    for r in rows:
        g = group_key(r)
        bucket = agg.setdefault(g, [0, 0])  # [k, n]
        bucket[1] += 1
        bucket[0] += int(bool(r[correct_key]))
    return {g: proportion_ci(k, n) for g, (k, n) in sorted(agg.items())}


def detection_cell_tables(
    rows: Sequence[Mapping[str, Any]]
) -> dict[str, dict[str, dict[str, Any]]]:
    return {
        "by_depth": cell_table(rows, lambda r: f"d{r['depth']}", "detection_correct"),
        "by_class": cell_table(
            rows, lambda r: str(r["perturbation_class"]), "detection_correct"
        ),
        "by_source": cell_table(
            rows, lambda r: str(r["source"]), "detection_correct"
        ),
        "by_depth_class": cell_table(
            rows,
            lambda r: f"d{r['depth']}|{r['perturbation_class']}",
            "detection_correct",
        ),
    }


def diagnosis_cell_tables(
    rows: Sequence[Mapping[str, Any]]
) -> dict[str, dict[str, dict[str, Any]]]:
    return {
        "by_depth": cell_table(
            rows, lambda r: f"d{r['depth']}", "diagnosis_exact_match"
        ),
        "by_class": cell_table(
            rows, lambda r: str(r["perturbation_class"]), "diagnosis_exact_match"
        ),
        "by_depth_class": cell_table(
            rows,
            lambda r: f"d{r['depth']}|{r['perturbation_class']}",
            "diagnosis_exact_match",
        ),
    }


def repair_cell_tables(
    results: Sequence[Mapping[str, Any]]
) -> dict[str, dict[str, dict[str, Any]]]:
    """`results` are repair-result dicts (RepairResult.to_dict())."""

    return {
        "by_depth": cell_table(results, lambda r: f"d{r['depth']}", "success"),
        "by_class": cell_table(
            results, lambda r: str(r["perturbation_class"]), "success"
        ),
        "by_arm": cell_table(results, lambda r: str(r["arm"]), "success"),
        "by_depth_class": cell_table(
            results, lambda r: f"d{r['depth']}|{r['perturbation_class']}", "success"
        ),
    }


def tidy_detection_rows(
    scored_rows: Sequence[Mapping[str, Any]],
    *,
    model: str,
    arm: str = "single_shot",
) -> list[dict[str, Any]]:
    """One tidy row per fixture x model x arm for GLMM import."""

    out: list[dict[str, Any]] = []
    for r in scored_rows:
        out.append(
            {
                "fixture_id": r["fixture_id"],
                "model": model,
                "arm": arm,
                "depth": r["depth"],
                "perturbation_class": r["perturbation_class"],
                "source": r["source"],
                "ground_truth_label": r["ground_truth_label"],
                "detection_correct": int(bool(r["detection_correct"])),
                "detection_valid": int(bool(r.get("detection_valid"))),
                "diagnosis_exact_match": int(bool(r.get("diagnosis_exact_match"))),
            }
        )
    return out


def tidy_repair_rows(
    results: Sequence[Mapping[str, Any]],
    *,
    model: str,
) -> list[dict[str, Any]]:
    """One tidy row per fixture x model x arm for repair GLMM import."""

    out: list[dict[str, Any]] = []
    for r in results:
        out.append(
            {
                "fixture_id": r["fixture_id"],
                "model": model,
                "arm": r["arm"],
                "depth": r["depth"],
                "perturbation_class": r["perturbation_class"],
                "success": int(bool(r["success"])),
                "success_round": (
                    r["success_round"] if r["success_round"] is not None else ""
                ),
                "n_rounds": r["n_rounds"],
                "verifier_calls": r["verifier_calls"],
                "edit_distance": r["edit_distance"],
                "generalization_to_final_check": (
                    "" if r["generalization_to_final_check"] is None
                    else int(bool(r["generalization_to_final_check"]))
                ),
            }
        )
    return out


def write_tidy_csv(
    path: Path | str,
    rows: Sequence[Mapping[str, Any]],
    *,
    columns: Sequence[str] | None = None,
) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        p.write_text("", encoding="utf-8")
        return
    cols = list(columns) if columns is not None else list(rows[0].keys())
    with p.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        for r in rows:
            writer.writerow({c: r.get(c, "") for c in cols})


def attrition_summary(
    attrition_records: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Counts of attrition by reason / depth / perturbation_class."""

    by_reason: dict[str, int] = {}
    by_depth: dict[str, int] = {}
    by_class: dict[str, int] = {}
    for a in attrition_records:
        by_reason[a["attrition_reason"]] = by_reason.get(a["attrition_reason"], 0) + 1
        dk = f"d{a['depth']}"
        by_depth[dk] = by_depth.get(dk, 0) + 1
        by_class[a["perturbation_class"]] = (
            by_class.get(a["perturbation_class"], 0) + 1
        )
    return {
        "n_total": len(attrition_records),
        "by_reason": by_reason,
        "by_depth": by_depth,
        "by_perturbation_class": by_class,
    }
