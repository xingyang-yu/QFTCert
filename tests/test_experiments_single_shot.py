"""Single-shot detection/diagnosis harness + scoring (Deliverable 10)."""

from __future__ import annotations

import json

from dualitycert.agent.dryrun import DryRunModelClient
from dualitycert.experiments.config import ExperimentConfig, VerifierConfig
from dualitycert.experiments.generation import generate_fixtures
from dualitycert.experiments.scoring import (
    detection_correct,
    diagnosis_exact_match,
    gold_categories,
    macro_f1,
    summarize_detection,
    summarize_diagnosis,
)
from dualitycert.experiments.single_shot import (
    build_scored_rows,
    run_single_shot,
    score_single_shot,
)


def _make_manifest(tmp_path):
    cfg = ExperimentConfig(
        name="ss",
        depths=(1,),
        fixture_classes=("positive", "drop_w_term", "r_charge_perturb", "wrong_pair"),
        n_per_cell=1,
        seed=99,
        verifier=VerifierConfig(),
    )
    res = generate_fixtures(cfg, out_dir=tmp_path, generated_at="t", git_commit="c")
    return res.manifest, tmp_path


# ----------------------------------------------------------------------
# Dry-run end-to-end.
# ----------------------------------------------------------------------


def test_single_shot_dry_run_end_to_end(tmp_path):
    records, root = _make_manifest(tmp_path)
    client = DryRunModelClient(detection_verdict="not_dual", diagnosis_modes=("anomaly",))
    out = tmp_path / "out"
    res = run_single_shot(
        records, theory_root=root, client=client, out_dir=out, model="dryrun",
        tasks=("detection", "diagnosis"), run_id="r1",
    )
    assert res.summary["n_fixtures"] == len(records)
    assert "detection" in res.summary and "diagnosis" in res.summary
    assert res.summary["detection"]["invalid_rate"] == 0.0
    for fname in ("model_outputs.jsonl", "scored.jsonl", "scored.csv", "summary.json", "metadata.json"):
        assert (res.run_dir / fname).exists()


def test_single_shot_constant_policy_matches_baseline(tmp_path):
    records, root = _make_manifest(tmp_path)
    client = DryRunModelClient(detection_verdict="not_dual")
    res = run_single_shot(
        records, theory_root=root, client=client, out_dir=tmp_path / "o",
        model="dryrun", tasks=("detection",), run_id="r",
    )
    det = res.summary["detection"]
    # "always not_dual" => raw accuracy equals the not_dual prior, bal_acc = 0.5.
    assert abs(det["accuracy"] - det["always_not_dual_baseline"]) < 1e-9
    if det["balanced_accuracy"] is not None:
        assert abs(det["balanced_accuracy"] - 0.5) < 1e-9


def test_single_shot_invalid_output_counts_wrong(tmp_path):
    records, root = _make_manifest(tmp_path)

    def bad_policy(*, user, tool_name, schema):
        if tool_name == "duality_decision":
            return {"verdict": "maybe", "confidence": "low", "reasoning": "x"}
        return {"failure_modes": [], "confidence": "low", "reasoning": "x"}

    client = DryRunModelClient(structured_policy=bad_policy)
    res = run_single_shot(
        records, theory_root=root, client=client, out_dir=tmp_path / "o",
        model="dryrun", tasks=("detection",), run_id="r",
    )
    det = res.summary["detection"]
    assert det["invalid_rate"] == 1.0  # every detection output invalid
    assert det["n_correct"] == 0  # invalid counts as wrong


def test_score_single_shot_matches_run(tmp_path):
    records, root = _make_manifest(tmp_path)
    client = DryRunModelClient()
    res = run_single_shot(
        records, theory_root=root, client=client, out_dir=tmp_path / "o",
        model="dryrun", tasks=("detection", "diagnosis"), run_id="r",
    )
    outputs = [json.loads(l) for l in (res.run_dir / "model_outputs.jsonl").read_text().splitlines() if l]
    scored_rows, summary = score_single_shot(outputs, records, tasks=("detection", "diagnosis"))
    assert summary["detection"] == res.summary["detection"]
    assert summary["diagnosis"] == res.summary["diagnosis"]


# ----------------------------------------------------------------------
# Scoring units.
# ----------------------------------------------------------------------


def test_detection_correct_and_invalid():
    assert detection_correct("dual", "dual") is True
    assert detection_correct("dual", "not_dual") is False
    assert detection_correct("not_dual", None) is False  # invalid -> wrong


def test_gold_categories_and_exact_match():
    obligations = [
        {"name": "global anomaly matching", "category": "anomaly"},
        {"name": "bounded chiral-ring consistency", "category": "chiral_ring"},
    ]
    gold = gold_categories(obligations)
    assert set(gold) == {"anomaly", "chiral_ring"}
    assert diagnosis_exact_match(["chiral_ring", "anomaly"], gold) is True
    assert diagnosis_exact_match(["anomaly"], gold) is False
    assert diagnosis_exact_match(None, gold) is False


def test_macro_f1_perfect_and_partial():
    preds = [frozenset({"anomaly"}), frozenset({"chiral_ring"})]
    golds = [["anomaly"], ["chiral_ring"]]
    macro, per = macro_f1(preds, golds)
    assert abs(macro - 1.0) < 1e-9

    preds2 = [frozenset({"anomaly"}), frozenset()]  # second missed
    golds2 = [["anomaly"], ["chiral_ring"]]
    macro2, per2 = macro_f1(preds2, golds2)
    assert 0.0 < macro2 < 1.0


def test_summarize_detection_and_diagnosis():
    rows = [
        {
            "ground_truth_label": "not_dual",
            "detection_verdict": "not_dual",
            "detection_valid": True,
            "detection_correct": True,
            "gold_categories": ["anomaly"],
            "diagnosis_modes": ["anomaly"],
            "diagnosis_valid": True,
            "diagnosis_exact_match": True,
        },
        {
            "ground_truth_label": "dual",
            "detection_verdict": "not_dual",
            "detection_valid": True,
            "detection_correct": False,
            "gold_categories": [],
            "diagnosis_modes": ["anomaly"],
            "diagnosis_valid": True,
            "diagnosis_exact_match": False,
        },
    ]
    d = summarize_detection(rows)
    assert d["n_total"] == 2 and d["n_correct"] == 1
    assert d["accuracy"] == 0.5
    g = summarize_diagnosis(rows)
    assert g["exact_set_match_rate"] == 0.5
    assert 0.0 <= g["macro_f1"] <= 1.0
