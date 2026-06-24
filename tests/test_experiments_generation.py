"""Generation, perturbations, chains, and JSON patch (Deliverable 10)."""

from __future__ import annotations

import json
import random

import pytest

from dualitycert.experiments.chains import generate_mutation_chain
from dualitycert.benchmark.fixtures import sanitize_for_prompt
from dualitycert.benchmark.generators import attempt_positive, attempt_w_drop
from dualitycert.experiments.config import (
    ChainConfig,
    ExperimentConfig,
    VerifierConfig,
)
from dualitycert.experiments.generation import IncompleteCellsError, generate_fixtures
from dualitycert.experiments.jsonpatch import apply_patches
from dualitycert.experiments.perturbations import _edit_drop_w
from dualitycert.experiments.verifier import run_verifier
from dualitycert.experiments.manifest import manifest_record_to_dict
from dualitycert.experiments.perturbations import (
    PerturbationError,
    apply_single_positive_edit,
)
from dualitycert.experiments.seeds import SeedSpec, default_seed_specs, dp0_electric
from dualitycert.experiments.seed_catalog import spp_electric


def _mvp_config(**kw) -> ExperimentConfig:
    base = dict(
        name="t",
        depths=(1,),
        fixture_classes=(
            "positive",
            "drop_w_term",
            "flip_w_sign",
            "r_charge_perturb",
            "rank_perturb",
            "wrong_pair",
        ),
        n_per_cell=2,
        seed=10000,
        verifier=VerifierConfig(),
    )
    base.update(kw)
    return ExperimentConfig(**base)


# ----------------------------------------------------------------------
# Verifier-gated generation.
# ----------------------------------------------------------------------


def test_generation_only_keeps_certified_or_failed(tmp_path):
    res = generate_fixtures(
        _mvp_config(), out_dir=tmp_path, generated_at="t", git_commit="c"
    )
    assert res.manifest, "expected a non-empty manifest"
    for r in res.manifest:
        assert r.label in {"CERTIFIED", "FAILED"}
        assert r.verifier_status in {"CERTIFIED", "FAILED"}
    # positives certify, repairable negatives fail.
    for r in res.manifest:
        if r.perturbation_class == "positive":
            assert r.label == "CERTIFIED" and not r.repairable
        if r.perturbation_class in {"drop_w_term", "flip_w_sign", "r_charge_perturb", "rank_perturb"}:
            assert r.label == "FAILED" and r.repairable


def test_generation_is_deterministic(tmp_path):
    a = generate_fixtures(
        _mvp_config(), out_dir=tmp_path / "a", generated_at="t", git_commit="c"
    )
    b = generate_fixtures(
        _mvp_config(), out_dir=tmp_path / "b", generated_at="t", git_commit="c"
    )
    assert [manifest_record_to_dict(r) for r in a.manifest] == [
        manifest_record_to_dict(r) for r in b.manifest
    ]
    assert [x.to_dict() for x in a.attrition] == [x.to_dict() for x in b.attrition]


# dp0-only seed + small chain budget: dp0 depth-2 fails fast at the
# engine level (no verifier calls), keeping these tests quick.
_DP0_SPEC = [SeedSpec("dp0_toric", dp0_electric, node=0, N=3)]
# SPP still cannot be re-mutated at depth 2 (its second-step F-equation needs
# a quadratic / multi-field elimination beyond current engine scope), so it is
# the standing "empty depth-2 cell" example now that dp0 succeeds.
_SPP_SPEC = [SeedSpec("spp", spp_electric, node=0, N=2)]


def _depth_cfg(depths, **kw):
    return ExperimentConfig(
        name="depthtest",
        depths=depths,
        fixture_classes=("positive", "drop_w_term"),
        n_per_cell=1,
        seed=7,
        chain=ChainConfig(max_chain_attempts_per_cell=2),
        **kw,
    )


def test_strict_completeness_raises_on_empty_depth2_cell(tmp_path):
    # Strict by default: a seed whose depth-2 cell stays empty (spp cannot be
    # re-mutated yet) makes the post-generation completeness check fail loudly.
    cfg = _depth_cfg((1, 2))
    with pytest.raises(IncompleteCellsError):
        generate_fixtures(
            cfg, out_dir=tmp_path, seed_specs=_SPP_SPEC,
            generated_at="t", git_commit="c",
        )


def test_depth2_attrition_is_precise_when_allowed(tmp_path):
    cfg = _depth_cfg((1, 2))
    res = generate_fixtures(
        cfg, out_dir=tmp_path, seed_specs=_SPP_SPEC, generated_at="t",
        git_commit="c", allow_incomplete_cells=True,
    )
    # depth-1 main fixtures exist; depth-2 produced none on spp.
    assert all(r.depth == 1 for r in res.manifest)
    assert any(r.depth == 1 for r in res.manifest)
    reasons = {a.attrition_reason for a in res.attrition}
    # The placeholder is gone; the reason is a real chain-runner reason.
    assert "depth_not_implemented" not in reasons
    assert any(
        a.depth == 2 and a.attrition_reason == "single_step_mutation_failed"
        for a in res.attrition
    )


def test_dp0_depth2_now_generates_certified_positive(tmp_path):
    # The multi-term F-term integration unblocks GENUINE depth-2 on dp0: a
    # second mutation at a DIFFERENT node, certified end to end.
    cfg = ExperimentConfig(
        name="depthtest",
        depths=(1, 2),
        fixture_classes=("positive", "drop_w_term"),
        n_per_cell=1,
        seed=7,
        chain=ChainConfig(max_chain_attempts_per_cell=8),
    )
    res = generate_fixtures(
        cfg, out_dir=tmp_path, seed_specs=_DP0_SPEC, generated_at="t",
        git_commit="c", allow_incomplete_cells=True,
    )
    d2_pos = [
        r for r in res.manifest if r.depth == 2 and r.perturbation_class == "positive"
    ]
    assert d2_pos, "dp0 should now yield a genuine depth-2 positive"
    assert d2_pos[0].label == "CERTIFIED"
    assert d2_pos[0].chain_depth == 2
    assert len(set(d2_pos[0].mutation_node_sequence)) == 2  # genuine, not a round-trip


def test_decoupled_edit_matches_mvp_generator(tmp_path):
    # Regression: the experiments drop-W edit must produce the same
    # candidate as the locked MVP operator for the same positive + seed.
    electric = dp0_electric(3)
    positive, _ = attempt_positive(
        electric_json=electric, node=0, N=3, source_name="dp0",
        fixture_id="p", seed=0,
    )
    assert positive is not None
    found = False
    for seed in range(40):
        mvp_fix, _ = attempt_w_drop(positive=positive, fixture_id="d", seed=seed)
        if mvp_fix is None:
            continue  # silent miss / discard at this seed
        edited, _meta = _edit_drop_w(positive.candidate, random.Random(seed))
        assert json.dumps(edited, sort_keys=True) == json.dumps(
            mvp_fix.candidate, sort_keys=True
        )
        found = True
        break
    assert found, "expected at least one accepted MVP w_drop to compare against"


def test_sanitize_is_verifier_invariant(tmp_path):
    # The repair loop verifies sanitized theories; the verdict must match
    # the raw theories' verdict (sanitize only neutralizes provenance).
    cfg = _mvp_config(fixture_classes=("positive", "drop_w_term"))
    res = generate_fixtures(cfg, out_dir=tmp_path, generated_at="t", git_commit="c")
    for r in res.manifest[:6]:
        e = json.loads((tmp_path / r.theory_a_path).read_text())
        c = json.loads((tmp_path / r.theory_b_path).read_text())
        raw = run_verifier(e, c, VerifierConfig())
        san = run_verifier(
            sanitize_for_prompt(e, theory_label="A"),
            sanitize_for_prompt(c, theory_label="B"),
            VerifierConfig(),
        )
        assert raw.status == san.status


def test_silent_miss_routes_to_attrition(tmp_path):
    # A perturbation that the verifier does not catch must NOT enter the
    # main manifest; it should be an unexpected_label attrition row.
    res = generate_fixtures(
        _mvp_config(n_per_cell=4), out_dir=tmp_path, generated_at="t", git_commit="c"
    )
    # main manifest never holds a negative-class fixture labeled CERTIFIED.
    for r in res.manifest:
        if r.perturbation_class != "positive":
            assert r.label == "FAILED"


def test_perturbation_metadata_is_recorded(tmp_path):
    res = generate_fixtures(
        _mvp_config(), out_dir=tmp_path, generated_at="t", git_commit="c"
    )
    drops = [r for r in res.manifest if r.perturbation_class == "drop_w_term"]
    assert drops
    for r in drops:
        assert "dropped_term" in r.perturbation_metadata
        assert "dropped_index" in r.perturbation_metadata
    flips = [r for r in res.manifest if r.perturbation_class == "flip_w_sign"]
    for r in flips:
        assert "old_coefficient" in r.perturbation_metadata
        assert "new_coefficient" in r.perturbation_metadata


def test_theory_files_written_and_loadable(tmp_path):
    res = generate_fixtures(
        _mvp_config(), out_dir=tmp_path, generated_at="t", git_commit="c"
    )
    r = res.manifest[0]
    a = json.loads((tmp_path / r.theory_a_path).read_text())
    b = json.loads((tmp_path / r.theory_b_path).read_text())
    assert "ranks" in a and "arrows" in a
    assert "superpotential" in b


# ----------------------------------------------------------------------
# Perturbation operators.
# ----------------------------------------------------------------------


def test_perturbation_edits_are_deterministic_and_pure():
    chain = generate_mutation_chain(
        dp0_electric(3), 1, random.Random(0), source_name="dp0", node=0
    )
    candidate = chain.final_theory
    snapshot = json.dumps(candidate, sort_keys=True)

    e1, m1 = apply_single_positive_edit("drop_w_term", candidate, random.Random(7))
    e2, m2 = apply_single_positive_edit("drop_w_term", candidate, random.Random(7))
    assert json.dumps(e1, sort_keys=True) == json.dumps(e2, sort_keys=True)
    assert m1 == m2
    # input not mutated.
    assert json.dumps(candidate, sort_keys=True) == snapshot


def test_rank_edit_respects_su2_floor():
    theory = {
        "name": "t",
        "node_labels": ["G0"],
        "ranks": [2],
        "u1_globals": [],
        "arrows": [],
        "superpotential": [],
    }
    # Many seeds: never drop below 2.
    for s in range(20):
        edited, meta = apply_single_positive_edit("rank_perturb", theory, random.Random(s))
        assert edited["ranks"][0] >= 2
        assert meta["new_rank"] >= 2


def test_drop_w_on_empty_superpotential_raises():
    theory = {
        "name": "t",
        "node_labels": ["G0"],
        "ranks": [2],
        "u1_globals": [],
        "arrows": [],
        "superpotential": [],
    }
    with pytest.raises(PerturbationError):
        apply_single_positive_edit("drop_w_term", theory, random.Random(0))


# Mutation chain-runner unit tests live in tests/test_experiments_chains.py.


# ----------------------------------------------------------------------
# JSON patch applier.
# ----------------------------------------------------------------------


def test_json_patch_replace_add_remove():
    doc = {"ranks": [2, 3], "w": [{"c": "1"}], "name": "x"}
    out, err = apply_patches(
        doc,
        [
            {"op": "replace", "path": "/ranks/0", "value": 5},
            {"op": "add", "path": "/ranks/-", "value": 7},
            {"op": "replace", "path": "/w/0/c", "value": "-1"},
            {"op": "remove", "path": "/name"},
        ],
    )
    assert err is None
    assert out["ranks"] == [5, 3, 7]
    assert out["w"][0]["c"] == "-1"
    assert "name" not in out
    # original untouched.
    assert doc["ranks"] == [2, 3] and doc["name"] == "x"


def test_json_patch_error_on_bad_path():
    doc = {"a": 1}
    out, err = apply_patches(doc, [{"op": "replace", "path": "/missing", "value": 2}])
    assert err is not None
    assert out == doc  # unchanged on failure
