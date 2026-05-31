"""Endpoint-pool pair sampling tests (Phase 2d-ext, offline)."""

from __future__ import annotations

import json
import tempfile
from collections import Counter
from pathlib import Path

import pytest

from dualitycert.agent.detection import build_detection_user_message
from dualitycert.benchmark.fixtures import sanitize_for_prompt
from dualitycert.experiments.config import EndpointPoolConfig, ExperimentConfig
from dualitycert.experiments.endpoint_pool import build_endpoint_pool
from dualitycert.experiments.generation import generate_fixtures
from dualitycert.experiments.seeds import default_seed_specs


def _ep_config(**ep_kw) -> ExperimentConfig:
    ep = EndpointPoolConfig(max_pool_depth=1, max_pairs_per_theory=6, **ep_kw)
    return ExperimentConfig(
        name="ep_test",
        depths=(1,),
        pair_generation_mode="endpoint_pool",
        endpoint_pool=ep,
        seed=2026,
    )


@pytest.fixture(scope="module")
def pool_run():
    """Generate one endpoint-pool manifest (shared across tests)."""

    cfg = _ep_config()
    out = Path(tempfile.mkdtemp())
    res = generate_fixtures(cfg, out_dir=out, generated_at="t", git_commit="c")
    return res, out, cfg


# ----------------------------------------------------------------------
# Pool construction.
# ----------------------------------------------------------------------


def test_build_endpoint_pool_is_deterministic():
    ep = EndpointPoolConfig(max_pool_depth=1)
    a = build_endpoint_pool(default_seed_specs(), ep)
    b = build_endpoint_pool(default_seed_specs(), ep)
    assert [e.theory_id for e in a] == [e.theory_id for e in b]
    assert [e.canonical_hash for e in a] == [e.canonical_hash for e in b]
    # T0 (depth 0) present for each orbit, plus depth-1 endpoints.
    depths = {e.orbit_id: set() for e in a}
    for e in a:
        depths[e.orbit_id].add(e.generation_depth)
    for orbit, ds in depths.items():
        assert 0 in ds and 1 in ds


def test_pool_endpoints_carry_provenance():
    ep = EndpointPoolConfig(max_pool_depth=1)
    pool = build_endpoint_pool(default_seed_specs(), ep)
    for e in pool:
        assert e.orbit_id and e.seed_id and e.canonical_hash
        assert "n_fields" in e.size_covariates
        if e.generation_depth == 0:
            assert e.mutation_sequence == ()
        else:
            assert len(e.mutation_sequence) == e.generation_depth


# ----------------------------------------------------------------------
# Sampling / pairing.
# ----------------------------------------------------------------------


def test_sampler_produces_non_seed_pairs(pool_run):
    res, _out, _cfg = pool_run
    same = [
        r for r in res.manifest
        if r.pair_metadata.get("pair_origin") == "same_orbit_endpoint_pair"
    ]
    assert same, "expected same-orbit positive pairs"
    # At least one positive pairs two non-seed endpoints (both depth >= 1),
    # i.e. it is NOT a (T0, T_K) pair.
    non_seed = [
        r for r in same
        if r.pair_metadata["generation_depth_a"] >= 1
        and r.pair_metadata["generation_depth_b"] >= 1
    ]
    assert non_seed, "expected at least one (T_i, T_j) positive with no seed side"


def test_max_pairs_per_theory_respected(pool_run):
    res, _out, cfg = pool_run
    counts: Counter = Counter()
    for r in res.manifest:
        counts[r.pair_metadata["theory_id_a"]] += 1
        counts[r.pair_metadata["theory_id_b"]] += 1
    assert counts
    assert max(counts.values()) <= cfg.endpoint_pool.max_pairs_per_theory


def test_orientation_is_balanced(pool_run):
    res, _out, _cfg = pool_run
    swaps = [bool(r.pair_metadata["pair_swapped"]) for r in res.manifest]
    # Both orientations occur (not always lower-depth as A).
    assert 0 < sum(swaps) < len(swaps)


def test_same_orbit_main_records_are_certified(pool_run):
    res, _out, _cfg = pool_run
    for r in res.manifest:
        if r.pair_metadata.get("pair_origin") == "same_orbit_endpoint_pair":
            assert r.label == "CERTIFIED"
            assert r.pair_metadata["orbit_id_a"] == r.pair_metadata["orbit_id_b"]


def test_cross_orbit_main_records_are_failed(pool_run):
    res, _out, _cfg = pool_run
    cross_origins = {"cross_orbit_pair", "size_matched_cross_pair", "wrong_pair"}
    cross = [
        r for r in res.manifest
        if r.pair_metadata.get("pair_origin") in cross_origins
    ]
    assert cross, "expected cross-orbit negatives"
    for r in cross:
        assert r.label == "FAILED"
        assert r.pair_metadata["orbit_id_a"] != r.pair_metadata["orbit_id_b"]


def test_label_source_and_pair_depth_metadata(pool_run):
    res, _out, _cfg = pool_run
    r = res.manifest[0]
    pm = r.pair_metadata
    assert pm["label_source"] == "endpoint_qftcert"
    assert pm["generation_history_shown_to_model"] is False
    for key in (
        "pair_generation_depth_max",
        "pair_generation_depth_sum",
        "pair_generation_depth_delta",
    ):
        assert key in pm
    assert pm["pair_generation_depth_delta"] == abs(
        pm["generation_depth_a"] - pm["generation_depth_b"]
    )


def test_prompt_hides_provenance(pool_run):
    res, out, _cfg = pool_run
    r = res.manifest[0]
    electric = json.loads((out / r.theory_a_path).read_text())
    candidate = json.loads((out / r.theory_b_path).read_text())
    msg = build_detection_user_message(
        sanitize_for_prompt(electric, theory_label="Theory A"),
        sanitize_for_prompt(candidate, theory_label="Theory B"),
    )
    pm = r.pair_metadata
    # No provenance leaks into the prompt the model sees.
    assert pm["orbit_id_a"] not in msg
    assert pm["theory_id_a"] not in msg
    assert pm["theory_id_b"] not in msg
    assert "generation_depth" not in msg
    assert "orbit" not in msg
    assert "mutation_sequence" not in msg


def test_legacy_mode_has_empty_pair_metadata(tmp_path):
    # Default (legacy_seed_endpoint) leaves pair_metadata empty.
    cfg = ExperimentConfig(
        name="legacy",
        depths=(1,),
        fixture_classes=("positive", "drop_w_term"),
        n_per_cell=1,
        seed=5,
    )
    res = generate_fixtures(cfg, out_dir=tmp_path, generated_at="t", git_commit="c")
    assert cfg.pair_generation_mode == "legacy_seed_endpoint"
    assert all(r.pair_metadata == {} for r in res.manifest)
