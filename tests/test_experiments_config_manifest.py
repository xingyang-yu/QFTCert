"""Config, manifest serialization, and Wilson CI (Deliverable 10)."""

from __future__ import annotations

import math

from dualitycert.experiments.config import (
    ExperimentConfig,
    RepairConfig,
    VerifierConfig,
)
from dualitycert.experiments.manifest import (
    AttritionRecord,
    ManifestRecord,
    SizeCovariates,
    compute_size_covariates,
    manifest_record_from_dict,
    manifest_record_to_dict,
    read_attrition_jsonl,
    read_manifest_jsonl,
    write_attrition_jsonl,
    write_manifest_csv,
    write_manifest_jsonl,
)
from dualitycert.experiments.stats import proportion_ci, wilson_interval


# ----------------------------------------------------------------------
# Config round-trip.
# ----------------------------------------------------------------------


def test_experiment_config_json_round_trip(tmp_path):
    cfg = ExperimentConfig(
        name="x",
        depths=(1, 2),
        fixture_classes=("positive", "drop_w_term"),
        n_per_cell=3,
        seed=42,
        verifier=VerifierConfig(chiral_ring_max_length=5),
        repair=RepairConfig(
            max_rounds=4,
            feedback_mode="verifier_feedback",
            feedback_detail="detailed",
            feedback_verifier=VerifierConfig(chiral_ring_max_length=3),
            final_eval_verifier=VerifierConfig(chiral_ring_max_length=6),
        ),
    )
    path = tmp_path / "cfg.json"
    cfg.to_json_file(path)
    back = ExperimentConfig.from_json_file(path)
    assert back.to_dict() == cfg.to_dict()
    assert back.config_hash() == cfg.config_hash()


def test_resolved_feedback_and_final_verifiers():
    cfg = ExperimentConfig(
        name="x",
        verifier=VerifierConfig(chiral_ring_max_length=3),
        repair=RepairConfig(final_eval_verifier=VerifierConfig(chiral_ring_max_length=6)),
    )
    # feedback falls back to top-level; final uses the override.
    assert cfg.feedback_verifier().chiral_ring_max_length == 3
    assert cfg.final_eval_verifier().chiral_ring_max_length == 6


def test_config_rejects_unknown_class():
    import pytest

    with pytest.raises(ValueError):
        ExperimentConfig(name="x", fixture_classes=("bogus_class",))


def test_repair_config_rejects_bad_mode():
    import pytest

    with pytest.raises(ValueError):
        RepairConfig(feedback_mode="telepathy")


# ----------------------------------------------------------------------
# Manifest serialization.
# ----------------------------------------------------------------------


def _sample_record() -> ManifestRecord:
    return ManifestRecord(
        fixture_id="fix_001",
        seed_id=123,
        depth=1,
        perturbation_class="drop_w_term",
        label="FAILED",
        repairable=True,
        theory_a_path="theories/fix_001.A.json",
        theory_b_path="theories/fix_001.B.json",
        sanitized=False,
        verifier_status="FAILED",
        failed_obligations=(
            {"name": "bounded chiral-ring consistency", "category": "chiral_ring"},
        ),
        verifier_config_hash="abc123",
        verifier_config={"chiral_ring_max_length": 3},
        size_covariates=SizeCovariates(
            n_gauge_nodes=3,
            n_fields=9,
            n_superpotential_terms=5,
            max_superpotential_monomial_length=3,
            n_r_charge_bearing_fields=9,
            input_token_estimate=400,
        ),
        generation_metadata={"rng_seed": 123, "generated_at": "t"},
        perturbation_metadata={"dropped_index": 2},
        mutation_chain_id="dp0:d1:node0",
        source="dp0_toric",
        split="eval",
    )


def test_manifest_record_round_trip():
    rec = _sample_record()
    back = manifest_record_from_dict(manifest_record_to_dict(rec))
    assert manifest_record_to_dict(back) == manifest_record_to_dict(rec)
    assert back.ground_truth_label == "not_dual"


def test_manifest_jsonl_and_csv_round_trip(tmp_path):
    recs = [_sample_record()]
    jsonl = tmp_path / "manifest.jsonl"
    write_manifest_jsonl(jsonl, recs)
    back = read_manifest_jsonl(jsonl)
    assert [manifest_record_to_dict(r) for r in back] == [
        manifest_record_to_dict(r) for r in recs
    ]
    csv_path = tmp_path / "manifest.csv"
    write_manifest_csv(csv_path, recs)
    text = csv_path.read_text(encoding="utf-8")
    assert "fixture_id" in text
    assert "chiral_ring" in text  # failed_obligation_categories flattened


def test_attrition_round_trip(tmp_path):
    a = AttritionRecord(
        fixture_id="x",
        seed_id=1,
        depth=2,
        perturbation_class="positive",
        attrition_reason="depth_not_implemented",
        detail="engine depth=1 only",
        verifier_status=None,
    )
    path = tmp_path / "attrition.jsonl"
    write_attrition_jsonl(path, [a])
    back = read_attrition_jsonl(path)
    assert back[0].to_dict() == a.to_dict()


def test_attrition_rejects_unknown_reason():
    import pytest

    with pytest.raises(ValueError):
        AttritionRecord(
            fixture_id="x",
            seed_id=1,
            depth=1,
            perturbation_class="positive",
            attrition_reason="made_up_reason",
            detail="",
            verifier_status=None,
        )


def test_manifest_record_rejects_non_gated_status():
    import pytest

    with pytest.raises(ValueError):
        ManifestRecord(
            fixture_id="x",
            seed_id=1,
            depth=1,
            perturbation_class="positive",
            label="UNKNOWN",  # not CERTIFIED/FAILED
            repairable=False,
            theory_a_path="a",
            theory_b_path="b",
            sanitized=False,
            verifier_status="UNKNOWN",
            failed_obligations=(),
            verifier_config_hash="h",
            verifier_config={},
            size_covariates=SizeCovariates(0, 0, 0, 0, 0),
            generation_metadata={},
        )


def test_compute_size_covariates():
    candidate = {
        "ranks": [2, 3, 4],
        "arrows": [
            {"label": "X01[0]", "source": 0, "target": 1, "r_charge": "2/3"},
            {"label": "X12[0]", "source": 1, "target": 2, "r_charge": "1/2"},
        ],
        "superpotential": [
            {"factors": ["X01[0]", "X12[0]", "X20[0]"], "coefficient": "1"},
            {"factors": ["X01[0]"], "coefficient": "1"},
        ],
    }
    sc = compute_size_covariates(candidate)
    assert sc.n_gauge_nodes == 3
    assert sc.n_fields == 2
    assert sc.n_superpotential_terms == 2
    assert sc.max_superpotential_monomial_length == 3
    assert sc.n_r_charge_bearing_fields == 2
    assert sc.input_token_estimate is not None and sc.input_token_estimate > 0


# ----------------------------------------------------------------------
# Wilson CI.
# ----------------------------------------------------------------------


def test_wilson_interval_known_value():
    # 8 of 10 successes; Wilson 95% CI ~ [0.490, 0.943].
    low, high = wilson_interval(8, 10)
    assert math.isclose(low, 0.4901, abs_tol=1e-3)
    assert math.isclose(high, 0.9430, abs_tol=1e-3)
    assert low < 0.8 < high


def test_wilson_interval_edges():
    assert wilson_interval(0, 0) == (0.0, 0.0)
    low, high = wilson_interval(10, 10)
    assert high == 1.0
    assert 0.0 <= low <= 1.0
    low0, high0 = wilson_interval(0, 10)
    assert low0 == 0.0
    assert 0.0 < high0 < 1.0


def test_proportion_ci_shape():
    ci = proportion_ci(3, 4)
    assert ci["n"] == 4 and ci["k"] == 3
    assert ci["p"] == 0.75
    assert ci["wilson_low"] <= 0.75 <= ci["wilson_high"]
