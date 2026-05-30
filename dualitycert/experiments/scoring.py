"""Scoring for single-shot detection + diagnosis (Deliverable 5).

Per-sample helpers (`detection_correct`, `gold_categories`,
`diagnosis_exact_match`) plus aggregate summaries
(`summarize_detection`, `summarize_diagnosis`). Invalid model output is
counted as wrong in the primary accuracy *and* reported as a separate
`invalid_rate`. Repair-loop success@K scoring lives in
`dualitycert.experiments.repair`.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence


__all__ = [
    "DIAGNOSIS_MACRO_LABELS",
    "detection_correct",
    "diagnosis_exact_match",
    "gold_categories",
    "gold_cause_for_class",
    "macro_f1",
    "suspected_cause_exact_match",
    "summarize_detection",
    "summarize_diagnosis",
]


# Fixed macro-F1 label vocabulary for diagnosis: the verifier obligation
# categories that can appear as ground truth. macro-F1 averages over
# THESE (not just observed labels) so the metric is comparable across
# runs even when a category never appears. "unknown" is excluded — it is
# never a gold label (obligations map to concrete categories).
DIAGNOSIS_MACRO_LABELS: tuple[str, ...] = (
    "anomaly",
    "superpotential",
    "r_charge",
    "chiral_ring",
)


# Map a perturbation_class to its ground-truth suspected-cause set (the
# SECONDARY diagnosis target). Positives have no cause.
_CLASS_TO_CAUSE = {
    "positive": (),
    "drop_w_term": ("drop_w_term",),
    "flip_w_sign": ("flip_w_sign",),
    "r_charge_perturb": ("r_charge_perturb",),
    "rank_perturb": ("rank_perturb",),
    "trivial_rank": ("rank_perturb",),  # alias
    "wrong_pair": ("wrong_pair",),
}


def gold_cause_for_class(perturbation_class: str) -> tuple[str, ...]:
    return _CLASS_TO_CAUSE.get(perturbation_class, ("unknown",))


def suspected_cause_exact_match(
    predicted: Sequence[str] | None, gold: Sequence[str]
) -> bool:
    if predicted is None:
        return False
    return set(predicted) == set(gold)


def detection_correct(ground_truth_label: str, verdict: str | None) -> bool:
    """CERTIFIED<->dual / FAILED<->not_dual; invalid (None) counts wrong."""

    if verdict is None:
        return False
    return verdict == ground_truth_label


def gold_categories(failed_obligations: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    """Sorted unique failure-mode categories from verifier obligations."""

    return tuple(sorted({str(o.get("category", "unknown")) for o in failed_obligations}))


def diagnosis_exact_match(
    predicted_modes: Sequence[str] | None,
    gold: Sequence[str],
) -> bool:
    """Exact-set match between predicted modes and gold categories.

    Invalid prediction (None) is never a match.
    """

    if predicted_modes is None:
        return False
    return set(predicted_modes) == set(gold)


def macro_f1(
    pred_sets: Iterable[frozenset[str] | None],
    gold_sets: Iterable[Sequence[str]],
    *,
    labels: Sequence[str] | None = None,
) -> tuple[float, dict[str, dict[str, float]]]:
    """Macro-averaged F1 over multi-label category predictions.

    Each fixture contributes a predicted label set and a gold label set.
    A None prediction (invalid output) contributes an empty predicted
    set (so every gold label becomes a false negative). Returns
    `(macro_f1, per_label_prf)` averaging over labels with nonzero
    support+prediction (or `labels` if given).
    """

    preds = [frozenset() if p is None else frozenset(p) for p in pred_sets]
    golds = [frozenset(g) for g in gold_sets]
    if len(preds) != len(golds):
        raise ValueError("macro_f1: pred / gold length mismatch")

    if labels is None:
        observed: set[str] = set()
        for s in preds:
            observed |= s
        for s in golds:
            observed |= s
        label_list = sorted(observed)
    else:
        label_list = list(labels)

    per_label: dict[str, dict[str, float]] = {}
    f1s: list[float] = []
    for label in label_list:
        tp = fp = fn = 0
        for p, g in zip(preds, golds):
            in_p = label in p
            in_g = label in g
            if in_p and in_g:
                tp += 1
            elif in_p and not in_g:
                fp += 1
            elif (not in_p) and in_g:
                fn += 1
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall)
            else 0.0
        )
        per_label[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": float(tp + fn),
        }
        # Only average over labels that have support or were predicted.
        if (tp + fn + fp) > 0:
            f1s.append(f1)

    macro = sum(f1s) / len(f1s) if f1s else 0.0
    return macro, per_label


def summarize_detection(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate detection scored rows into a summary dict.

    Each row must carry: ground_truth_label, detection_verdict (str|None),
    detection_valid (bool), detection_correct (bool).
    """

    rows = list(rows)
    n = len(rows)
    n_correct = sum(1 for r in rows if r["detection_correct"])
    n_invalid = sum(1 for r in rows if not r["detection_valid"])

    counts_by_class: dict[str, int] = {}
    correct_by_class: dict[str, int] = {}
    confusion = {
        "dual": {"dual": 0, "not_dual": 0, "invalid": 0},
        "not_dual": {"dual": 0, "not_dual": 0, "invalid": 0},
    }
    for r in rows:
        gt = r["ground_truth_label"]
        counts_by_class[gt] = counts_by_class.get(gt, 0) + 1
        correct_by_class[gt] = correct_by_class.get(gt, 0) + int(r["detection_correct"])
        verdict = r["detection_verdict"] if r["detection_valid"] else "invalid"
        if gt in confusion and verdict in confusion[gt]:
            confusion[gt][verdict] += 1

    acc_by_class = {
        k: (correct_by_class.get(k, 0) / v if v else 0.0)
        for k, v in counts_by_class.items()
    }
    n_dual = counts_by_class.get("dual", 0)
    n_not_dual = counts_by_class.get("not_dual", 0)
    balanced = (
        (acc_by_class.get("dual", 0.0) + acc_by_class.get("not_dual", 0.0)) / 2.0
        if (n_dual and n_not_dual)
        else None
    )
    return {
        "task": "detection",
        "n_total": n,
        "n_correct": n_correct,
        "accuracy": (n_correct / n) if n else 0.0,
        "balanced_accuracy": balanced,
        "always_not_dual_baseline": (n_not_dual / n) if n else 0.0,
        "always_dual_baseline": (n_dual / n) if n else 0.0,
        "invalid_rate": (n_invalid / n) if n else 0.0,
        "counts_by_class": counts_by_class,
        "accuracy_by_class": acc_by_class,
        "confusion_matrix": confusion,
    }


def summarize_diagnosis(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate diagnosis scored rows into a summary dict.

    Each row must carry: gold_categories (list[str]), diagnosis_modes
    (list[str]|None), diagnosis_valid (bool), diagnosis_exact_match (bool).
    """

    rows = list(rows)
    n = len(rows)
    n_exact = sum(1 for r in rows if r["diagnosis_exact_match"])
    n_invalid = sum(1 for r in rows if not r["diagnosis_valid"])

    pred_sets = [
        None if r["diagnosis_modes"] is None else frozenset(r["diagnosis_modes"])
        for r in rows
    ]
    gold_sets = [list(r["gold_categories"]) for r in rows]
    macro, per_label = macro_f1(pred_sets, gold_sets, labels=DIAGNOSIS_MACRO_LABELS)

    summary = {
        "task": "diagnosis",
        "n_total": n,
        "exact_set_match": n_exact,
        "exact_set_match_rate": (n_exact / n) if n else 0.0,
        "macro_f1": macro,
        "macro_f1_labels": list(DIAGNOSIS_MACRO_LABELS),
        "per_category": per_label,
        "invalid_rate": (n_invalid / n) if n else 0.0,
    }

    # Secondary analysis: suspected-cause exact match (only if recorded).
    cause_rows = [r for r in rows if "suspected_cause_exact_match" in r]
    if cause_rows:
        n_cause = len(cause_rows)
        n_cause_match = sum(1 for r in cause_rows if r["suspected_cause_exact_match"])
        summary["suspected_cause"] = {
            "n_total": n_cause,
            "exact_match": n_cause_match,
            "exact_match_rate": (n_cause_match / n_cause) if n_cause else 0.0,
        }
    return summary
