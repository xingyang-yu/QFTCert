"""Generation, perturbations, chains, and JSON patch (Deliverable 10)."""

from __future__ import annotations

import json
import random

import pytest

from dualitycert.experiments.chains import (
    DepthNotImplementedError,
    generate_mutation_chain,
)
from dualitycert.experiments.config import ExperimentConfig, VerifierConfig
from dualitycert.experiments.generation import generate_fixtures
from dualitycert.experiments.jsonpatch import apply_patches
from dualitycert.experiments.manifest import manifest_record_to_dict
from dualitycert.experiments.perturbations import (
    PerturbationError,
    apply_single_positive_edit,
)
from dualitycert.experiments.seeds import default_seed_specs, dp0_electric


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


def test_depth_ge_2_routes_to_attrition_not_manifest(tmp_path):
    cfg = _mvp_config(depths=(1, 2, 3))
    res = generate_fixtures(cfg, out_dir=tmp_path, generated_at="t", git_commit="c")
    assert all(r.depth == 1 for r in res.manifest)
    reasons = {a.attrition_reason for a in res.attrition}
    assert "depth_not_implemented" in reasons
    # every depth>=2 attrition row is labeled depth_not_implemented.
    for a in res.attrition:
        if a.depth >= 2:
            assert a.attrition_reason == "depth_not_implemented"


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


# ----------------------------------------------------------------------
# Mutation chain runner.
# ----------------------------------------------------------------------


def test_chain_depth1_builds():
    chain = generate_mutation_chain(
        dp0_electric(3), 1, random.Random(0), source_name="dp0", node=0
    )
    assert chain.node_sequence == (0,)
    assert chain.in_scope
    assert "ranks" in chain.final_theory
    assert len(chain.intermediate_theories) == 2


def test_chain_depth2_raises():
    with pytest.raises(DepthNotImplementedError):
        generate_mutation_chain(dp0_electric(3), 2, random.Random(0), node=0)


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
