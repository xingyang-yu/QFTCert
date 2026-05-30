"""CLI handlers for the paper-scale experiment harness (Deliverable 9).

Registered as subcommands of the existing `dualitycert` CLI (see
`dualitycert.cli`). All imports of heavy experiment modules happen here,
so `dualitycert check` etc. stay lightweight.

Commands (mirroring the paper plan, under the `dualitycert` binary):

    dualitycert generate-fixtures --config configs/mvp.json --out runs/mvp
    dualitycert verify-manifest --manifest runs/mvp/manifest.jsonl --out runs/mvp/verified
    dualitycert run-single-shot  --manifest ... --config ... --model dryrun --out ...
    dualitycert score-single-shot --results .../model_outputs.jsonl --manifest ... --out ...
    dualitycert run-repair-loop  --manifest ... --config ... --arm verifier_feedback --model dryrun --out ...
    dualitycert score-repair     --run runs/repair_dryrun --out runs/repair_dryrun/scores
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any


def add_subparsers(subparsers) -> None:
    """Register the experiment subcommands on an argparse subparsers object."""

    gen = subparsers.add_parser(
        "generate-fixtures", help="Generate a verifier-gated fixture manifest."
    )
    gen.add_argument("--config", required=True, help="Experiment config JSON path.")
    gen.add_argument("--out", required=True, help="Output directory.")
    gen.add_argument(
        "--allow-incomplete-cells",
        action="store_true",
        help=(
            "Allow depth>=2 cells (unimplemented) to route to attrition instead "
            "of preflight-failing the run."
        ),
    )
    gen.set_defaults(func=cmd_generate_fixtures)

    ver = subparsers.add_parser(
        "verify-manifest",
        help="Re-run the verifier on every manifest fixture (dataset validation).",
    )
    ver.add_argument("--manifest", required=True, help="manifest.jsonl path.")
    ver.add_argument("--out", required=True, help="Output directory.")
    ver.add_argument(
        "--theory-root",
        default=None,
        help="Root for theory paths (default: manifest's parent directory).",
    )
    ver.set_defaults(func=cmd_verify_manifest)

    ss = subparsers.add_parser(
        "run-single-shot", help="Run single-shot detection + diagnosis."
    )
    ss.add_argument("--manifest", required=True)
    ss.add_argument("--config", required=True)
    ss.add_argument("--out", required=True)
    ss.add_argument("--model", default="dryrun", help="dryrun | <anthropic model id>.")
    ss.add_argument("--theory-root", default=None)
    ss.add_argument(
        "--tasks",
        default="detection,diagnosis",
        help="Comma-separated subset of detection,diagnosis.",
    )
    ss.add_argument("--run-id", default=None)
    ss.set_defaults(func=cmd_run_single_shot)

    score_ss = subparsers.add_parser(
        "score-single-shot", help="Score existing single-shot model outputs."
    )
    score_ss.add_argument("--results", required=True, help="model_outputs.jsonl path.")
    score_ss.add_argument("--manifest", required=True)
    score_ss.add_argument("--out", required=True)
    score_ss.add_argument("--model", default="model")
    score_ss.add_argument("--tasks", default="detection,diagnosis")
    score_ss.set_defaults(func=cmd_score_single_shot)

    rep = subparsers.add_parser(
        "run-repair-loop", help="Run the verifier-in-the-loop repair experiment."
    )
    rep.add_argument("--manifest", required=True)
    rep.add_argument("--config", required=True)
    rep.add_argument("--out", required=True)
    rep.add_argument(
        "--arm",
        default="verifier_feedback",
        help="single_shot_repair | generic_retry | llm_critic | verifier_feedback.",
    )
    rep.add_argument("--model", default="dryrun")
    rep.add_argument("--theory-root", default=None)
    rep.add_argument("--run-id", default=None)
    rep.add_argument(
        "--include-non-repairable",
        action="store_true",
        help="Also run positives / wrong_pair (do-no-harm / abstention stress).",
    )
    rep.add_argument(
        "--force-model-on-certified",
        action="store_true",
        help=(
            "Challenge mode: do not short-circuit passing candidates; force the "
            "model to act so harm / unnecessary-edit rates are measurable."
        ),
    )
    rep.set_defaults(func=cmd_run_repair_loop)

    score_rep = subparsers.add_parser(
        "score-repair", help="Score an existing repair run directory."
    )
    score_rep.add_argument("--run", required=True, help="Repair run directory.")
    score_rep.add_argument("--out", required=True)
    score_rep.add_argument("--model", default="model")
    score_rep.add_argument("--max-rounds", type=int, default=5)
    score_rep.set_defaults(func=cmd_score_repair)


# ----------------------------------------------------------------------
# Client builder.
# ----------------------------------------------------------------------


def _build_client(model: str):
    from dualitycert.agent.dryrun import DryRunModelClient

    if model == "dryrun":
        return DryRunModelClient(), "dryrun"
    from dualitycert.agent.client import AnthropicAdapter

    return AnthropicAdapter(), model


# ----------------------------------------------------------------------
# Handlers.
# ----------------------------------------------------------------------


def cmd_generate_fixtures(args) -> int:
    from dualitycert.experiments.config import ExperimentConfig
    from dualitycert.experiments.generation import generate_fixtures

    config = ExperimentConfig.from_json_file(args.config)
    result = generate_fixtures(
        config, out_dir=args.out, allow_incomplete_cells=args.allow_incomplete_cells
    )
    print(f"[generate-fixtures] config={config.name} out={args.out}")
    print(f"  manifest: {len(result.manifest)} fixtures  {result.label_counts()}")
    print(f"  by class: {result.class_counts()}")
    print(f"  attrition: {len(result.attrition)}")
    return 0


def cmd_verify_manifest(args) -> int:
    from dualitycert.experiments.config import VerifierConfig
    from dualitycert.experiments.manifest import (
        AttritionRecord,
        read_manifest_jsonl,
        write_attrition_jsonl,
        write_manifest_jsonl,
    )
    from dualitycert.experiments.single_shot import load_theory
    from dualitycert.experiments.verifier import run_verifier

    manifest_path = Path(args.manifest)
    theory_root = Path(args.theory_root) if args.theory_root else manifest_path.parent
    records = read_manifest_jsonl(manifest_path)

    verified = []
    drift = []
    for rec in records:
        electric = load_theory(theory_root, rec.theory_a_path)
        candidate = load_theory(theory_root, rec.theory_b_path)
        vcfg = VerifierConfig.from_dict(rec.verifier_config)
        outcome = run_verifier(electric, candidate, vcfg, claim_name=rec.fixture_id)
        if outcome.status == rec.verifier_status:
            verified.append(rec)
        else:
            drift.append(
                AttritionRecord(
                    fixture_id=rec.fixture_id,
                    seed_id=rec.seed_id,
                    depth=rec.depth,
                    perturbation_class=rec.perturbation_class,
                    attrition_reason=(
                        "unexpected_label"
                        if outcome.in_scope
                        else outcome.attrition_reason()
                    ),
                    detail=(
                        f"re-verify drift: stored {rec.verifier_status}, "
                        f"now {outcome.status}"
                    ),
                    verifier_status=outcome.status,
                    source=rec.source,
                )
            )

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_manifest_jsonl(out_dir / "verified.jsonl", verified)
    write_attrition_jsonl(out_dir / "drift.jsonl", drift)
    print(
        f"[verify-manifest] {len(verified)}/{len(records)} agree with stored "
        f"verifier_status; {len(drift)} drifted -> {out_dir}/drift.jsonl"
    )
    return 0 if not drift else 1


def cmd_run_single_shot(args) -> int:
    from dualitycert.experiments.config import ExperimentConfig
    from dualitycert.experiments.manifest import read_manifest_jsonl
    from dualitycert.experiments.single_shot import run_single_shot

    config = ExperimentConfig.from_json_file(args.config)
    manifest_path = Path(args.manifest)
    theory_root = Path(args.theory_root) if args.theory_root else manifest_path.parent
    records = read_manifest_jsonl(manifest_path)
    tasks = tuple(t.strip() for t in args.tasks.split(",") if t.strip())

    client, model_name = _build_client(args.model)
    result = run_single_shot(
        records,
        theory_root=theory_root,
        client=client,
        out_dir=args.out,
        model=model_name,
        max_tokens=config.model.max_tokens,
        tasks=tasks,
        run_id=args.run_id,
        config_snapshot=config.to_dict(),
    )
    _write_stats_single_shot(result.scored_rows, model_name, tasks, result.run_dir)
    print(f"[run-single-shot] run_dir={result.run_dir}")
    if "detection" in tasks:
        d = result.summary["detection"]
        print(
            f"  detection: acc={d['accuracy']:.3f} "
            f"bal_acc={d['balanced_accuracy']} invalid={d['invalid_rate']:.3f}"
        )
    if "diagnosis" in tasks:
        g = result.summary["diagnosis"]
        print(
            f"  diagnosis: exact={g['exact_set_match_rate']:.3f} "
            f"macroF1={g['macro_f1']:.3f} invalid={g['invalid_rate']:.3f}"
        )
    return 0


def cmd_score_single_shot(args) -> int:
    from dualitycert.experiments.manifest import read_manifest_jsonl
    from dualitycert.experiments.single_shot import score_single_shot

    outputs = _read_jsonl(args.results)
    records = read_manifest_jsonl(args.manifest)
    tasks = tuple(t.strip() for t in args.tasks.split(",") if t.strip())
    scored_rows, summary = score_single_shot(
        outputs, records, out_dir=args.out, tasks=tasks
    )
    _write_stats_single_shot(scored_rows, args.model, tasks, Path(args.out))
    print(f"[score-single-shot] {len(scored_rows)} rows -> {args.out}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def cmd_run_repair_loop(args) -> int:
    from dualitycert.experiments.config import ExperimentConfig
    from dualitycert.experiments.manifest import read_manifest_jsonl
    from dualitycert.experiments.repair import run_repair_experiment

    config = ExperimentConfig.from_json_file(args.config)
    manifest_path = Path(args.manifest)
    theory_root = Path(args.theory_root) if args.theory_root else manifest_path.parent
    records = read_manifest_jsonl(manifest_path)

    client, model_name = _build_client(args.model)
    result = run_repair_experiment(
        records,
        theory_root=theory_root,
        client=client,
        config=config,
        arm=args.arm,
        out_dir=args.out,
        run_id=args.run_id,
        model=model_name,
        repairable_only=not args.include_non_repairable,
        force_model_on_certified=args.force_model_on_certified,
    )
    s = result.summary
    print(f"[run-repair-loop] arm={args.arm} run_dir={result.run_dir}")
    print(
        f"  success_rate={s['success_rate']:.3f} "
        f"@1={s['success_at_1']:.3f} @3={s['success_at_3']:.3f} "
        f"@5={s['success_at_5']:.3f} invalid={s['invalid_json_rate']:.3f} "
        f"abstain={s['abstention_rate']:.3f}"
    )
    return 0


def cmd_score_repair(args) -> int:
    from dualitycert.experiments.repair import score_repair
    from dualitycert.experiments.stats import repair_cell_tables, tidy_repair_rows, write_tidy_csv

    run_dir = Path(args.run)
    result_dicts = _read_jsonl(run_dir / "repair_results.jsonl")
    results_ns = [SimpleNamespace(**d) for d in result_dicts]
    summary = score_repair(results_ns, max_rounds=args.max_rounds)
    cells = repair_cell_tables(result_dicts)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "cell_tables.json").write_text(
        json.dumps(cells, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_tidy_csv(out_dir / "tidy_repair.csv", tidy_repair_rows(result_dicts, model=args.model))
    print(f"[score-repair] {len(result_dicts)} results -> {out_dir}")
    print(
        f"  success_rate={summary['success_rate']:.3f} "
        f"@1={summary['success_at_1']:.3f} @5={summary['success_at_5']:.3f}"
    )
    return 0


# ----------------------------------------------------------------------
# Helpers.
# ----------------------------------------------------------------------


def _write_stats_single_shot(scored_rows, model_name, tasks, out_dir: Path) -> None:
    from dualitycert.experiments.stats import (
        detection_cell_tables,
        diagnosis_cell_tables,
        tidy_detection_rows,
        write_tidy_csv,
    )

    cells: dict[str, Any] = {}
    if "detection" in tasks:
        cells["detection"] = detection_cell_tables(scored_rows)
    if "diagnosis" in tasks:
        cells["diagnosis"] = diagnosis_cell_tables(scored_rows)
    (out_dir / "cell_tables.json").write_text(
        json.dumps(cells, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_tidy_csv(
        out_dir / "tidy_detection.csv",
        tidy_detection_rows(scored_rows, model=model_name),
    )


def _read_jsonl(path: Path | str) -> list[dict]:
    out: list[dict] = []
    with Path(path).open("r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if line:
                out.append(json.loads(line))
    return out
