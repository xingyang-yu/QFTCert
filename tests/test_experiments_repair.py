"""Repair-loop harness, arms, success@K, and the L guardrail (Deliverable 10)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dualitycert.agent.dryrun import DryRunModelClient
from dualitycert.experiments.config import (
    ExperimentConfig,
    RepairConfig,
    VerifierConfig,
)
from dualitycert.experiments.generation import generate_fixtures
from dualitycert.experiments.repair import (
    run_repair_experiment,
    run_repair_loop,
    score_repair,
    theory_edit_distance,
)
from dualitycert.experiments.seeds import SeedSpec, dp0_electric
from dualitycert.experiments.verifier import run_verifier


def _dp0_manifest(tmp_path, *, repair: RepairConfig | None = None):
    cfg = ExperimentConfig(
        name="rep",
        depths=(1,),
        fixture_classes=("positive", "drop_w_term"),
        n_per_cell=1,
        seed=5,
        verifier=VerifierConfig(),  # gate at L=3
        repair=repair or RepairConfig(max_rounds=5, feedback_mode="verifier_feedback"),
    )
    specs = [SeedSpec("dp0_toric", dp0_electric, node=0, N=3)]
    res = generate_fixtures(
        cfg, out_dir=tmp_path, seed_specs=specs, generated_at="t", git_commit="c"
    )
    return cfg, res, tmp_path


def _by_class(records, cls):
    return [r for r in records if r.perturbation_class == cls][0]


# ----------------------------------------------------------------------
# Oracle success / noop failure / arms.
# ----------------------------------------------------------------------


def test_repair_oracle_succeeds_round1(tmp_path):
    cfg, res, root = _dp0_manifest(tmp_path)
    drop = _by_class(res.manifest, "drop_w_term")
    pos = _by_class(res.manifest, "positive")
    good = json.loads((Path(root) / pos.theory_b_path).read_text())

    def oracle(*, user, tool_name, schema):
        return {"action": "edit_candidate", "full_theory": good, "reasoning": "oracle"}

    client = DryRunModelClient(structured_policy=oracle)
    r = run_repair_loop(drop, theory_root=root, client=client, config=cfg, arm="verifier_feedback")
    assert r.success is True
    assert r.success_round == 1
    assert r.final_status == "CERTIFIED"
    assert r.generalization_to_final_check is True


def test_repair_noop_fails_and_exhausts_k(tmp_path):
    cfg, res, root = _dp0_manifest(tmp_path)
    drop = _by_class(res.manifest, "drop_w_term")
    client = DryRunModelClient()  # default no_change
    r = run_repair_loop(drop, theory_root=root, client=client, config=cfg, arm="verifier_feedback")
    assert r.success is False
    assert r.n_rounds == 5
    assert r.final_status == "FAILED"


def test_repair_single_shot_arm_is_one_round(tmp_path):
    cfg, res, root = _dp0_manifest(tmp_path)
    drop = _by_class(res.manifest, "drop_w_term")
    client = DryRunModelClient()
    r = run_repair_loop(drop, theory_root=root, client=client, config=cfg, arm="single_shot_repair")
    assert r.n_rounds == 1
    assert r.success is False


def test_repair_abstain(tmp_path):
    cfg, res, root = _dp0_manifest(tmp_path)
    drop = _by_class(res.manifest, "drop_w_term")

    def abstainer(*, user, tool_name, schema):
        return {"action": "abstain", "reasoning": "cannot fix"}

    client = DryRunModelClient(structured_policy=abstainer)
    r = run_repair_loop(drop, theory_root=root, client=client, config=cfg, arm="verifier_feedback")
    assert r.abstained is True
    assert r.success is False


def test_repair_invalid_patch_recorded(tmp_path):
    cfg, res, root = _dp0_manifest(tmp_path)
    drop = _by_class(res.manifest, "drop_w_term")

    def bad_patch(*, user, tool_name, schema):
        return {
            "action": "edit_candidate",
            "patches": [{"op": "replace", "path": "/nonexistent/9", "value": 1}],
            "reasoning": "oops",
        }

    client = DryRunModelClient(structured_policy=bad_patch)
    r = run_repair_loop(drop, theory_root=root, client=client, config=cfg, arm="verifier_feedback")
    assert r.invalid is True
    assert r.success is False


def test_repair_rejects_verifier_setting_injection(tmp_path):
    cfg, res, root = _dp0_manifest(tmp_path)
    drop = _by_class(res.manifest, "drop_w_term")

    def inject(*, user, tool_name, schema):
        return {
            "action": "edit_candidate",
            "patches": [{"op": "add", "path": "/metadata", "value": {"x": 1}}],
            "reasoning": "sneaky",
        }

    client = DryRunModelClient(structured_policy=inject)
    r = run_repair_loop(drop, theory_root=root, client=client, config=cfg, arm="verifier_feedback")
    # The patch is rejected -> invalid round, never applied.
    assert r.invalid is True
    assert r.success is False


# ----------------------------------------------------------------------
# Do-no-harm on positives.
# ----------------------------------------------------------------------


def test_repair_do_no_harm_on_positive(tmp_path):
    cfg, res, root = _dp0_manifest(tmp_path)
    pos = _by_class(res.manifest, "positive")
    client = DryRunModelClient()
    r = run_repair_loop(pos, theory_root=root, client=client, config=cfg, arm="verifier_feedback")
    # A passing candidate is recognized immediately; the model is not invoked.
    assert r.success is True
    assert r.n_rounds == 1
    assert r.edit_distance == 0
    assert not client.structured_calls  # never asked to edit


# ----------------------------------------------------------------------
# Anti-gaming guardrail: final verifier stricter than feedback.
# ----------------------------------------------------------------------


def test_final_eval_stricter_than_feedback_catches_gaming(tmp_path):
    # Feedback at L=2 certifies a dropped-W candidate that the stricter
    # final eval at L=3 rejects -> success=False, generalization gap flagged.
    repair = RepairConfig(
        max_rounds=3,
        feedback_mode="verifier_feedback",
        feedback_detail="medium",
        feedback_verifier=VerifierConfig(chiral_ring_max_length=2),
        final_eval_verifier=VerifierConfig(chiral_ring_max_length=3),
    )
    cfg, res, root = _dp0_manifest(tmp_path, repair=repair)
    drop = _by_class(res.manifest, "drop_w_term")

    electric = json.loads((Path(root) / drop.theory_a_path).read_text())
    candidate = json.loads((Path(root) / drop.theory_b_path).read_text())
    # Precondition: this candidate is L-sensitive (passes L=2, fails L=3).
    assert run_verifier(electric, candidate, VerifierConfig(chiral_ring_max_length=2)).is_certified
    assert run_verifier(electric, candidate, VerifierConfig(chiral_ring_max_length=3)).is_failed

    client = DryRunModelClient()  # no_change; feedback verifier already certifies
    r = run_repair_loop(drop, theory_root=root, client=client, config=cfg, arm="verifier_feedback")
    assert r.success is False
    assert r.final_status == "FAILED"
    assert r.generalization_to_final_check is False  # passed feedback, failed final


# ----------------------------------------------------------------------
# success@K scoring + experiment driver.
# ----------------------------------------------------------------------


def test_score_repair_success_at_k(tmp_path):
    cfg, res, root = _dp0_manifest(tmp_path)
    drop = _by_class(res.manifest, "drop_w_term")
    pos = _by_class(res.manifest, "positive")
    good = json.loads((Path(root) / pos.theory_b_path).read_text())

    def oracle(*, user, tool_name, schema):
        return {"action": "edit_candidate", "full_theory": good, "reasoning": "oracle"}

    success = run_repair_loop(
        drop, theory_root=root, client=DryRunModelClient(structured_policy=oracle),
        config=cfg, arm="verifier_feedback",
    )
    failure = run_repair_loop(
        drop, theory_root=root, client=DryRunModelClient(), config=cfg,
        arm="verifier_feedback",
    )
    summary = score_repair([success, failure], max_rounds=5)
    assert summary["n_fixtures"] == 2
    assert summary["n_success"] == 1
    assert summary["success_rate"] == 0.5
    assert summary["success_at_1"] == 0.5
    assert summary["success_at_5"] == 0.5
    assert summary["iterations_to_success"] == [1]


def test_run_repair_experiment_writes_artifacts(tmp_path):
    cfg, res, root = _dp0_manifest(tmp_path)
    client = DryRunModelClient()
    out = tmp_path / "reprun"
    exp = run_repair_experiment(
        res.manifest, theory_root=root, client=client, config=cfg,
        arm="verifier_feedback", out_dir=out, run_id="rr", timestamp_override="t",
    )
    assert (exp.run_dir / "repair_results.jsonl").exists()
    assert (exp.run_dir / "summary.json").exists()
    assert (exp.run_dir / "metadata.json").exists()
    # only repairable negatives selected by default.
    assert all(r.repairable for r in res.manifest if r.fixture_id in
               {x.fixture_id for x in exp.results})


def test_theory_edit_distance():
    a = {"ranks": [2, 3], "name": "x"}
    b = {"ranks": [2, 4], "name": "x"}
    assert theory_edit_distance(a, b) == 1
    assert theory_edit_distance(a, a) == 0
