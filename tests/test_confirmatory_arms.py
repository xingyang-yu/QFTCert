"""Confirmatory-phase harness additions (paper/analysis_protocol.md).

Covers the two frozen control arms (vf_masked E5, best_of_n E4 control),
the per-round instrumentation, total-cost accounting, and the E4
stop-first replay. Offline only — no API calls.
"""

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
from dualitycert.experiments.e4_replay import (
    load_run_records,
    mcnemar_exact,
    score_e4,
)
from dualitycert.experiments.generation import generate_fixtures
from dualitycert.experiments.repair import (
    _changed_paths,
    build_feedback,
    run_repair_loop,
    score_repair,
)
from dualitycert.experiments.seeds import SeedSpec, dp0_electric
from dualitycert.experiments.verifier import run_verifier


def _dp0_manifest(tmp_path, *, repair: RepairConfig | None = None):
    cfg = ExperimentConfig(
        name="conf",
        depths=(1,),
        fixture_classes=("positive", "drop_w_term"),
        n_per_cell=1,
        seed=5,
        verifier=VerifierConfig(),
        repair=repair
        or RepairConfig(
            max_rounds=5,
            feedback_mode="verifier_feedback",
            edit_mode="full_theory",
        ),
    )
    specs = [SeedSpec("dp0_toric", dp0_electric, node=0, N=3)]
    res = generate_fixtures(
        cfg, out_dir=tmp_path, seed_specs=specs, generated_at="t", git_commit="c"
    )
    return cfg, res, tmp_path


def _by_class(records, cls):
    return [r for r in records if r.perturbation_class == cls][0]


def _load(root, rel):
    return json.loads((Path(root) / rel).read_text())


# ----------------------------------------------------------------------
# vf_masked (E5 control).
# ----------------------------------------------------------------------


def test_masked_feedback_structure_no_identity_leak(tmp_path):
    cfg, res, root = _dp0_manifest(tmp_path)
    drop = _by_class(res.manifest, "drop_w_term")
    electric = _load(root, drop.theory_a_path)
    candidate = _load(root, drop.theory_b_path)
    outcome = run_verifier(electric, candidate, cfg.feedback_verifier())
    assert outcome.failed_obligations, "fixture must fail the feedback verifier"

    kwargs = dict(
        detail="medium",
        electric=electric,
        candidate=candidate,
        outcome=outcome,
        feedback_verifier=cfg.feedback_verifier(),
    )
    medium = build_feedback(arm="verifier_feedback", **kwargs)
    masked = build_feedback(arm="vf_masked", **kwargs)

    # Same preamble, same bullet count/structure.
    assert medium.splitlines()[0] == masked.splitlines()[0]
    assert len(medium.splitlines()) == len(masked.splitlines())
    # Positional placeholders present; obligation identities absent.
    assert "obligation-1 (category: category-1)" in masked
    for o in outcome.failed_obligations:
        assert o["name"] not in masked
    # Deterministic (position/count only).
    assert masked == build_feedback(arm="vf_masked", **kwargs)


def test_masked_arm_prompts_carry_placeholders(tmp_path):
    cfg, res, root = _dp0_manifest(tmp_path)
    drop = _by_class(res.manifest, "drop_w_term")
    seen: list[str] = []

    def capture(*, user, tool_name, schema):
        seen.append(user)
        return {"action": "no_change", "reasoning": ""}

    client = DryRunModelClient(structured_policy=capture)
    r = run_repair_loop(
        drop, theory_root=root, client=client, config=cfg, arm="vf_masked"
    )
    assert r.success is False
    assert r.n_rounds == 5
    assert all("obligation-1" in u for u in seen[1:] or seen)


# ----------------------------------------------------------------------
# best_of_n (E4 control).
# ----------------------------------------------------------------------


def test_best_of_n_draws_are_identical_and_capped(tmp_path):
    cfg, res, root = _dp0_manifest(tmp_path)
    drop = _by_class(res.manifest, "drop_w_term")
    seen: list[str] = []

    def capture(*, user, tool_name, schema):
        seen.append(user)
        return {"action": "no_change", "reasoning": ""}

    client = DryRunModelClient(structured_policy=capture)
    r = run_repair_loop(
        drop, theory_root=root, client=client, config=cfg, arm="best_of_n"
    )
    assert r.arm == "best_of_n"
    assert r.success is False
    assert r.n_rounds == 2 * cfg.repair.max_rounds + 1 == 11
    assert len(seen) == 11
    # Independence: every draw sees the byte-identical prompt (round_idx
    # pinned to 1, candidate always the unchanged original).
    assert len(set(seen)) == 1


def test_best_of_n_continues_past_invalid_and_stops_at_final_cert(tmp_path):
    cfg, res, root = _dp0_manifest(tmp_path)
    drop = _by_class(res.manifest, "drop_w_term")
    pos = _by_class(res.manifest, "positive")
    good = _load(root, pos.theory_b_path)
    calls = {"n": 0}

    def flaky_then_oracle(*, user, tool_name, schema):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"action": "abstain", "reasoning": "pass this draw"}
        if calls["n"] == 2:
            return {"action": "edit_candidate", "full_theory": {"ranks": [1]},
                    "reasoning": "garbage"}
        return {"action": "edit_candidate", "full_theory": good,
                "reasoning": "oracle"}

    client = DryRunModelClient(structured_policy=flaky_then_oracle)
    r = run_repair_loop(
        drop, theory_root=root, client=client, config=cfg, arm="best_of_n"
    )
    assert r.success is True
    assert r.success_round == 3
    assert r.n_rounds == 3
    # Policy-level flags: a valid draw existed, so neither invalid nor
    # abstained even though individual draws were.
    assert r.invalid is False
    assert r.abstained is False
    assert r.generalization_to_final_check is True
    assert r.final_status == "CERTIFIED"
    assert [rd["action"] for rd in r.rounds] == [
        "abstain", "edit_candidate", "edit_candidate"
    ]
    assert r.edit_distance > 0


def test_best_of_n_all_abstain_flags_abstained(tmp_path):
    cfg, res, root = _dp0_manifest(tmp_path)
    drop = _by_class(res.manifest, "drop_w_term")

    def abstainer(*, user, tool_name, schema):
        return {"action": "abstain", "reasoning": "no"}

    client = DryRunModelClient(structured_policy=abstainer)
    r = run_repair_loop(
        drop, theory_root=root, client=client, config=cfg, arm="best_of_n"
    )
    assert r.abstained is True
    assert r.invalid is False
    assert r.n_rounds == 11


def test_best_of_n_rejects_force_mode(tmp_path):
    cfg, res, root = _dp0_manifest(tmp_path)
    drop = _by_class(res.manifest, "drop_w_term")
    with pytest.raises(ValueError, match="force_model_on_certified"):
        run_repair_loop(
            drop,
            theory_root=root,
            client=DryRunModelClient(),
            config=cfg,
            arm="best_of_n",
            force_model_on_certified=True,
        )


# ----------------------------------------------------------------------
# Instrumentation: changed paths + total-cost accounting.
# ----------------------------------------------------------------------


def test_changed_paths_semantic_diff():
    before = {
        "ranks": [3, 3, 3],
        "arrows": [
            {"label": "X01", "r_charge": "1/3", "source": 0, "target": 1},
            {"label": "X12", "r_charge": "1/3", "source": 1, "target": 2},
        ],
        "superpotential": [{"coefficient": "1", "factors": ["X01", "X12"]}],
        "name": "t",
    }
    after = json.loads(json.dumps(before))
    after["ranks"][0] = 6
    after["arrows"][0]["r_charge"] = "2/3"
    after["arrows"].append(
        {"label": "M02", "r_charge": "4/3", "source": 0, "target": 2}
    )
    del after["arrows"][1]
    after["superpotential"] = [{"coefficient": "-1", "factors": ["X01", "M02"]}]

    paths = _changed_paths(before, after)
    assert "ranks[0]" in paths
    assert "arrows[X01].r_charge" in paths
    assert "arrows[+M02]" in paths
    assert "arrows[-X12]" in paths
    assert "superpotential" in paths
    assert "name" not in paths


def test_rounds_carry_instrumentation_and_totals(tmp_path):
    cfg, res, root = _dp0_manifest(tmp_path)
    drop = _by_class(res.manifest, "drop_w_term")
    pos = _by_class(res.manifest, "positive")
    good = _load(root, pos.theory_b_path)

    def oracle(*, user, tool_name, schema):
        return {"action": "edit_candidate", "full_theory": good, "reasoning": "o"}

    client = DryRunModelClient(structured_policy=oracle)
    r = run_repair_loop(
        drop, theory_root=root, client=client, config=cfg, arm="verifier_feedback"
    )
    assert r.success is True
    (rd,) = r.rounds
    assert rd["model_called"] is True
    assert rd["changed_paths"], "an applied edit must record changed paths"
    assert rd["candidate_hash"]
    summary = score_repair([r], max_rounds=cfg.repair.max_rounds)
    assert summary["total_model_calls"] == 1
    assert "total_input_tokens" in summary
    assert "total_output_tokens" in summary


# ----------------------------------------------------------------------
# E4 replay.
# ----------------------------------------------------------------------


def test_mcnemar_exact_values():
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(1, 1) == 1.0
    assert abs(mcnemar_exact(7, 0) - 2 / 128) < 1e-12


def _write_run(tmp_path, name, recs):
    d = tmp_path / name
    d.mkdir()
    with (d / "repair_results.jsonl").open("w") as fh:
        for rec in recs:
            fh.write(json.dumps(rec) + "\n")
    return d


def _rec(fid, success, *, n_calls=1, verifier_calls=1):
    return {
        "fixture_id": fid,
        "success": success,
        "verifier_calls": verifier_calls,
        "rounds": [
            {"model_called": True, "input_tokens": 10, "output_tokens": 5}
            for _ in range(n_calls)
        ],
    }


def test_score_e4_replay_and_pairing(tmp_path):
    ss = _write_run(
        tmp_path, "ss",
        [_rec("A", True), _rec("B", False), _rec("C", False)],
    )
    gr = _write_run(
        tmp_path, "gr",
        [_rec("A", False, n_calls=5), _rec("B", False, n_calls=5),
         _rec("C", False, n_calls=5)],
    )
    vf = _write_run(
        tmp_path, "vf",
        [_rec("A", False, n_calls=5), _rec("B", True, n_calls=3),
         _rec("C", False, n_calls=5)],
    )
    ctl = _write_run(
        tmp_path, "ctl",
        [_rec("A", False, n_calls=11), _rec("B", True, n_calls=4),
         _rec("C", True, n_calls=7)],
    )

    summary = score_e4(
        ss_dir=ss, gr_dir=gr, vf_dir=vf, control_dir=ctl, out_dir=tmp_path / "out"
    )
    assert summary["portfolio_n_success"] == 2  # A via ss, B via vf
    assert summary["portfolio_stopped_at_arm_counts"] == {"ss": 1, "gr": 0, "vf": 1}
    # Deployed calls: A stops after ss (1); B runs ss+gr+vf (1+5+3);
    # C exhausts all (1+5+5).
    assert summary["portfolio_deployed_model_calls"] == 1 + 9 + 11
    assert summary["paired"] == {
        "both": 1, "portfolio_only": 1, "control_only": 1, "neither": 0
    }
    assert summary["mcnemar_exact_p"] == 1.0
    assert summary["control_n_success"] == 2

    rows = [
        json.loads(x)
        for x in (tmp_path / "out" / "e4_replay.jsonl").read_text().splitlines()
    ]
    assert [r["fixture_id"] for r in rows] == ["A", "B", "C"]
    assert rows[0]["stopped_at_arm"] == "ss"
    assert rows[1]["component_success"] == {"ss": False, "gr": False, "vf": True}


def test_score_e4_rejects_mismatched_fixture_sets(tmp_path):
    ss = _write_run(tmp_path, "ss", [_rec("A", True)])
    gr = _write_run(tmp_path, "gr", [_rec("A", False)])
    vf = _write_run(tmp_path, "vf", [_rec("B", False)])
    with pytest.raises(ValueError, match="fixture sets differ"):
        score_e4(ss_dir=ss, gr_dir=gr, vf_dir=vf, out_dir=tmp_path / "out")


def test_load_run_records_rejects_duplicates(tmp_path):
    d = _write_run(tmp_path, "dup", [_rec("A", True), _rec("A", False)])
    with pytest.raises(ValueError, match="duplicate fixture_id"):
        load_run_records(d)
