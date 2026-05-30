"""Single-shot detection + diagnosis harness (Layer A/B, Deliverable 5).

Reads a fixture manifest, loads each fixture's theory files, sanitizes
them (no provenance leaks), and runs one detection call and/or one
diagnosis call per fixture against any `LLMClient`. Writes:

    <out>/<run_id>/model_outputs.jsonl   # raw + parsed per-task replies
    <out>/<run_id>/scored.jsonl          # one scored row per fixture
    <out>/<run_id>/scored.csv            # flat scored rows
    <out>/<run_id>/summary.json          # detection + diagnosis summaries
    <out>/<run_id>/metadata.json         # model, manifest hash, timestamp

Invalid model output (schema-violating payload or a refusal that raises)
is recorded per fixture and counted as wrong in primary accuracy, with a
separate invalid_rate in the summary.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from dualitycert.agent.client import LLMClient
from dualitycert.agent.detection import run_detection
from dualitycert.agent.diagnosis import run_diagnosis
from dualitycert.benchmark.fixtures import sanitize_for_prompt
from dualitycert.experiments.manifest import ManifestRecord
from dualitycert.experiments.scoring import (
    detection_correct,
    diagnosis_exact_match,
    gold_categories,
    summarize_detection,
    summarize_diagnosis,
)


__all__ = [
    "DEFAULT_TASKS",
    "SingleShotResult",
    "build_scored_rows",
    "build_single_shot_summary",
    "load_theory",
    "run_single_shot",
    "score_single_shot",
]


DEFAULT_TASKS: tuple[str, ...] = ("detection", "diagnosis")


@dataclass
class SingleShotResult:
    run_id: str
    run_dir: Path
    outputs: list[dict[str, Any]] = field(default_factory=list)
    scored_rows: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


def load_theory(theory_root: Path | str, rel_path: str) -> dict[str, Any]:
    """Load a theory JSON referenced (relative) by a manifest record."""

    p = Path(theory_root) / rel_path
    return json.loads(p.read_text(encoding="utf-8"))


def run_single_shot(
    records: Sequence[ManifestRecord],
    *,
    theory_root: Path | str,
    client: LLMClient,
    out_dir: Path | str,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 2048,
    tasks: Sequence[str] = DEFAULT_TASKS,
    run_id: str | None = None,
    config_snapshot: Mapping[str, Any] | None = None,
    timestamp_override: str | None = None,
) -> SingleShotResult:
    """Run detection / diagnosis over a manifest and write all artefacts."""

    tasks = tuple(tasks)
    for t in tasks:
        if t not in {"detection", "diagnosis"}:
            raise ValueError(f"unknown task {t!r}; expected detection / diagnosis")
    if not records:
        raise ValueError("run_single_shot: empty manifest")

    if run_id is None:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(out_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    outputs: list[dict[str, Any]] = []
    for rec in records:
        electric = load_theory(theory_root, rec.theory_a_path)
        candidate = load_theory(theory_root, rec.theory_b_path)
        sanitized_e = sanitize_for_prompt(electric, theory_label="Theory A")
        sanitized_c = sanitize_for_prompt(candidate, theory_label="Theory B")

        out: dict[str, Any] = {"fixture_id": rec.fixture_id, "model": model}
        if "detection" in tasks:
            out["detection"] = _call_detection(
                sanitized_e, sanitized_c, client, model, max_tokens
            )
        if "diagnosis" in tasks:
            out["diagnosis"] = _call_diagnosis(
                sanitized_e, sanitized_c, client, model, max_tokens
            )
        outputs.append(out)

    scored_rows = build_scored_rows(outputs, records)
    summary = build_single_shot_summary(scored_rows, tasks=tasks)

    _write_jsonl(run_dir / "model_outputs.jsonl", outputs)
    _write_jsonl(run_dir / "scored.jsonl", scored_rows)
    _write_scored_csv(run_dir / "scored.csv", scored_rows)
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    timestamp = timestamp_override or datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )
    metadata = {
        "run_id": run_id,
        "model": model,
        "max_tokens": int(max_tokens),
        "tasks": list(tasks),
        "n_fixtures": len(records),
        "timestamp": timestamp,
        "config": dict(config_snapshot or {}),
    }
    (run_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    return SingleShotResult(
        run_id=run_id,
        run_dir=run_dir,
        outputs=outputs,
        scored_rows=scored_rows,
        summary=summary,
    )


def _call_detection(
    sanitized_e: Mapping[str, Any],
    sanitized_c: Mapping[str, Any],
    client: LLMClient,
    model: str,
    max_tokens: int,
) -> dict[str, Any]:
    try:
        dec = run_detection(
            sanitized_electric=sanitized_e,
            sanitized_candidate=sanitized_c,
            client=client,
            model=model,
            max_tokens=max_tokens,
        )
    except Exception as exc:  # invalid output / refusal / schema violation
        return {
            "verdict": None,
            "confidence": None,
            "reasoning": None,
            "valid": False,
            "error": f"{type(exc).__name__}: {exc}",
            "latency_s": None,
            "input_tokens": None,
            "output_tokens": None,
        }
    return {
        "verdict": dec.verdict,
        "confidence": dec.confidence,
        "reasoning": dec.reasoning,
        "valid": True,
        "error": None,
        "latency_s": dec.latency_s,
        "input_tokens": dec.input_tokens,
        "output_tokens": dec.output_tokens,
    }


def _call_diagnosis(
    sanitized_e: Mapping[str, Any],
    sanitized_c: Mapping[str, Any],
    client: LLMClient,
    model: str,
    max_tokens: int,
) -> dict[str, Any]:
    try:
        dec = run_diagnosis(
            sanitized_electric=sanitized_e,
            sanitized_candidate=sanitized_c,
            client=client,
            model=model,
            max_tokens=max_tokens,
        )
    except Exception as exc:
        return {
            "failure_modes": None,
            "confidence": None,
            "reasoning": None,
            "valid": False,
            "error": f"{type(exc).__name__}: {exc}",
            "latency_s": None,
            "input_tokens": None,
            "output_tokens": None,
        }
    return {
        "failure_modes": list(dec.failure_modes),
        "confidence": dec.confidence,
        "reasoning": dec.reasoning,
        "valid": True,
        "error": None,
        "latency_s": dec.latency_s,
        "input_tokens": dec.input_tokens,
        "output_tokens": dec.output_tokens,
    }


def build_scored_rows(
    outputs: Sequence[Mapping[str, Any]],
    records: Sequence[ManifestRecord],
) -> list[dict[str, Any]]:
    """Join model outputs to manifest ground truth into scored rows."""

    by_id = {r.fixture_id: r for r in records}
    rows: list[dict[str, Any]] = []
    for out in outputs:
        fid = out["fixture_id"]
        if fid not in by_id:
            raise ValueError(f"output references unknown fixture_id {fid!r}")
        rec = by_id[fid]
        gt = rec.ground_truth_label
        gold = list(gold_categories(rec.failed_obligations))

        det = out.get("detection")
        det_valid = bool(det["valid"]) if det is not None else False
        det_verdict = det["verdict"] if (det is not None and det_valid) else None
        det_conf = det["confidence"] if det is not None else None

        diag = out.get("diagnosis")
        diag_valid = bool(diag["valid"]) if diag is not None else False
        diag_modes = (
            list(diag["failure_modes"])
            if (diag is not None and diag_valid)
            else None
        )
        diag_conf = diag["confidence"] if diag is not None else None

        latencies = [
            x["latency_s"]
            for x in (det, diag)
            if x is not None and x.get("latency_s") is not None
        ]
        in_toks = [
            x["input_tokens"]
            for x in (det, diag)
            if x is not None and x.get("input_tokens") is not None
        ]
        out_toks = [
            x["output_tokens"]
            for x in (det, diag)
            if x is not None and x.get("output_tokens") is not None
        ]

        rows.append(
            {
                "fixture_id": fid,
                "depth": rec.depth,
                "perturbation_class": rec.perturbation_class,
                "source": rec.source,
                "split": rec.split,
                "label": rec.label,
                "ground_truth_label": gt,
                "gold_categories": gold,
                "detection_verdict": det_verdict,
                "detection_valid": det_valid if det is not None else None,
                "detection_correct": (
                    detection_correct(gt, det_verdict) if det is not None else False
                ),
                "detection_confidence": det_conf,
                "diagnosis_modes": diag_modes,
                "diagnosis_valid": diag_valid if diag is not None else None,
                "diagnosis_exact_match": (
                    diagnosis_exact_match(diag_modes, gold)
                    if diag is not None
                    else False
                ),
                "diagnosis_confidence": diag_conf,
                "latency_s": sum(latencies) if latencies else None,
                "input_tokens": sum(in_toks) if in_toks else None,
                "output_tokens": sum(out_toks) if out_toks else None,
            }
        )
    return rows


def build_single_shot_summary(
    scored_rows: Sequence[Mapping[str, Any]],
    *,
    tasks: Sequence[str] = DEFAULT_TASKS,
) -> dict[str, Any]:
    summary: dict[str, Any] = {"n_fixtures": len(scored_rows)}
    if "detection" in tasks:
        summary["detection"] = summarize_detection(scored_rows)
    if "diagnosis" in tasks:
        summary["diagnosis"] = summarize_diagnosis(scored_rows)
    return summary


def score_single_shot(
    outputs: Sequence[Mapping[str, Any]],
    records: Sequence[ManifestRecord],
    *,
    out_dir: Path | str | None = None,
    tasks: Sequence[str] = DEFAULT_TASKS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Re-score existing model outputs against a manifest (CLI score step)."""

    scored_rows = build_scored_rows(outputs, records)
    summary = build_single_shot_summary(scored_rows, tasks=tasks)
    if out_dir is not None:
        d = Path(out_dir)
        d.mkdir(parents=True, exist_ok=True)
        _write_jsonl(d / "scored.jsonl", scored_rows)
        _write_scored_csv(d / "scored.csv", scored_rows)
        (d / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return scored_rows, summary


# ----------------------------------------------------------------------
# I/O helpers.
# ----------------------------------------------------------------------


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False))
            fh.write("\n")


_SCORED_CSV_COLUMNS: tuple[str, ...] = (
    "fixture_id",
    "depth",
    "perturbation_class",
    "source",
    "split",
    "label",
    "ground_truth_label",
    "detection_verdict",
    "detection_valid",
    "detection_correct",
    "detection_confidence",
    "diagnosis_modes",
    "diagnosis_valid",
    "diagnosis_exact_match",
    "gold_categories",
    "latency_s",
    "input_tokens",
    "output_tokens",
)


def _write_scored_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(_SCORED_CSV_COLUMNS))
        writer.writeheader()
        for r in rows:
            writer.writerow(
                {
                    "fixture_id": r["fixture_id"],
                    "depth": r["depth"],
                    "perturbation_class": r["perturbation_class"],
                    "source": r["source"],
                    "split": r.get("split", ""),
                    "label": r["label"],
                    "ground_truth_label": r["ground_truth_label"],
                    "detection_verdict": _csv_val(r["detection_verdict"]),
                    "detection_valid": _csv_val(r["detection_valid"]),
                    "detection_correct": int(bool(r["detection_correct"])),
                    "detection_confidence": _csv_val(r["detection_confidence"]),
                    "diagnosis_modes": (
                        ";".join(r["diagnosis_modes"])
                        if r["diagnosis_modes"]
                        else _csv_val(r["diagnosis_modes"])
                    ),
                    "diagnosis_valid": _csv_val(r["diagnosis_valid"]),
                    "diagnosis_exact_match": int(bool(r["diagnosis_exact_match"])),
                    "gold_categories": ";".join(r["gold_categories"]),
                    "latency_s": _csv_val(r["latency_s"]),
                    "input_tokens": _csv_val(r["input_tokens"]),
                    "output_tokens": _csv_val(r["output_tokens"]),
                }
            )


def _csv_val(v: Any) -> Any:
    if v is None:
        return ""
    if isinstance(v, bool):
        return int(v)
    return v
