"""Tests for the Phase 2c-a fixture generators.

Pins three contracts:

  - Rule 6: verifier-gating. CERTIFIED -> label "dual", FAILED ->
    "not_dual"; anything else -> discarded log entry, no fixture.
  - Rule 9: every accepted negative has overall_status == FAILED in its
    verifier_ground_truth — i.e. the generator never silently mislabels
    a CERTIFIED result as "not_dual" (the W-sign-swap silent miss is
    the canonical example).
  - Determinism: same `seed` argument produces byte-identical fixtures
    (so committed fixture files stay byte-identical on re-generation).
"""

from __future__ import annotations

import itertools
import json
from fractions import Fraction

import pytest

from dualitycert.benchmark.fixtures import (
    Fixture,
    fixture_to_dict,
)
from dualitycert.benchmark.generators import (
    DETECTION_DUALITY_PROFILE,
    PROMPT_VISIBLE_FIELDS,
    attempt_positive,
    attempt_r_naive,
    attempt_rank_perturb,
    attempt_w_drop,
    attempt_w_sign_swap,
    attempt_wrong_pair,
    evaluate_pair_ground_truth,
    gate_and_build_fixture,
)
from dualitycert.benchmark.fixtures import FixtureMetadata
from dualitycert.core.objects import SuperpotentialTerm
from dualitycert.groups.u1 import u1_r
from dualitycert.qft.pure_quiver_builder import (
    arrow_names,
    build_pure_quiver,
    dp0_superpotential,
)
from dualitycert.qft.pure_quiver_json import pure_quiver_to_json


# ----------------------------------------------------------------------
# Shared seeds.
# ----------------------------------------------------------------------


def _dp0_electric_json(N: int = 3) -> dict:
    n01 = arrow_names(0, 1, 3)
    n12 = arrow_names(1, 2, 3)
    n20 = arrow_names(2, 0, 3)
    return pure_quiver_to_json(
        build_pure_quiver(
            ranks=(N, N, N),
            arrows={
                (0, 1): [Fraction(2, 3)] * 3,
                (1, 2): [Fraction(2, 3)] * 3,
                (2, 0): [Fraction(2, 3)] * 3,
            },
            superpotential=dp0_superpotential(n01, n12, n20),
            u1_globals=(u1_r(),),
        )
    )


def _f0_phase_ii_electric_json(N: int = 3) -> dict:
    def eps(a: int, b: int) -> int:
        if (a, b) == (0, 1):
            return 1
        if (a, b) == (1, 0):
            return -1
        return 0

    R_BD = Fraction(1, 2)
    R_DI = Fraction(1, 1)

    W: list[SuperpotentialTerm] = []
    for a, i, alpha, beta in itertools.product(range(2), repeat=4):
        sign = eps(a, alpha) * eps(i, beta)
        if sign == 0:
            continue
        W.append(
            SuperpotentialTerm(
                factors=(
                    (f"X01[{a}]", 1),
                    (f"X12[{i}]", 1),
                    (f"X20[{2 * alpha + beta}]", 1),
                ),
                coefficient=Fraction(sign),
            )
        )
    for a, i, alpha, beta in itertools.product(range(2), repeat=4):
        sign = eps(a, alpha) * eps(i, beta)
        if sign == 0:
            continue
        W.append(
            SuperpotentialTerm(
                factors=(
                    (f"X03[{a}]", 1),
                    (f"X32[{i}]", 1),
                    (f"X20[{2 * alpha + beta}]", 1),
                ),
                coefficient=Fraction(-sign),
            )
        )
    return pure_quiver_to_json(
        build_pure_quiver(
            ranks=(N, N, N, N),
            arrows={
                (0, 1): [R_BD] * 2,
                (0, 3): [R_BD] * 2,
                (2, 0): [R_DI] * 4,
                (1, 2): [R_BD] * 2,
                (3, 2): [R_BD] * 2,
            },
            superpotential=tuple(W),
            u1_globals=(u1_r(),),
        )
    )


@pytest.fixture(scope="module")
def dp0_positive_n3_node0() -> Fixture:
    fix, _ = attempt_positive(
        electric_json=_dp0_electric_json(N=3),
        node=0,
        N=3,
        source_name="dp0_toric",
        fixture_id="dp0_node0_positive_N3_seed0",
        seed=0,
    )
    assert fix is not None
    return fix


@pytest.fixture(scope="module")
def f0_positive_n3_node0() -> Fixture:
    fix, _ = attempt_positive(
        electric_json=_f0_phase_ii_electric_json(N=3),
        node=0,
        N=3,
        source_name="f0_phase_ii",
        fixture_id="f0_phase_ii_node0_positive_N3_seed0",
        seed=0,
    )
    assert fix is not None
    return fix


# ----------------------------------------------------------------------
# Positives.
# ----------------------------------------------------------------------


def test_attempt_positive_dp0_certifies_at_all_three_nodes():
    """The Z_3 cyclic symmetry of dP_0 means every node's mutation
    must yield a CERTIFIED claim."""

    electric = _dp0_electric_json(N=3)
    for node in (0, 1, 2):
        fix, log = attempt_positive(
            electric_json=electric,
            node=node,
            N=3,
            source_name="dp0_toric",
            fixture_id=f"dp0_node{node}_positive_N3_seed0",
            seed=0,
        )
        assert fix is not None, f"node {node} unexpectedly discarded: {log.discard_reason}"
        assert fix.ground_truth_label == "dual"
        assert fix.verifier_ground_truth["overall_status"] == "CERTIFIED"
        assert fix.verifier_ground_truth["failed_obligations"] == []
        assert fix.metadata.perturbation_type == "none"
        assert fix.metadata.extra["mutation_node"] == node
        assert fix.metadata.extra["mutation_depth"] == 1
        assert fix.metadata.extra["N"] == 3
        # Accepted log entry mirrors the fixture.
        assert log.generation_status == "accepted"
        assert log.discard_reason is None
        assert log.prompt_visible_fields == PROMPT_VISIBLE_FIELDS


def test_attempt_positive_dp0_n4_also_certifies():
    """Rule 8 augmentation: dP_0 at N=4 must also certify."""

    fix, _ = attempt_positive(
        electric_json=_dp0_electric_json(N=4),
        node=0,
        N=4,
        source_name="dp0_toric",
        fixture_id="dp0_node0_positive_N4_seed0",
        seed=0,
    )
    assert fix is not None
    assert fix.ground_truth_label == "dual"
    assert fix.metadata.extra["N"] == 4


def test_attempt_positive_f0_phase_ii_certifies():
    """F_0 II at node 0 with N=3 (post-R-repair) certifies — the
    Phase 2c1 acceptance gate output, validated as a positive here."""

    fix, log = attempt_positive(
        electric_json=_f0_phase_ii_electric_json(N=3),
        node=0,
        N=3,
        source_name="f0_phase_ii",
        fixture_id="f0_n0_pos",
        seed=0,
    )
    assert fix is not None, log.discard_reason
    assert fix.ground_truth_label == "dual"


# ----------------------------------------------------------------------
# Type-4 W drop.
# ----------------------------------------------------------------------


def test_w_drop_produces_failed_negative(dp0_positive_n3_node0: Fixture):
    """Dropping a W term from a dP_0-mutated candidate must fail bounded
    chiral-ring consistency (Phase 2b sediment)."""

    fix, log = attempt_w_drop(
        positive=dp0_positive_n3_node0,
        fixture_id="dp0_node0_wdrop_seed0",
        seed=0,
    )
    assert fix is not None, log.discard_reason
    assert fix.ground_truth_label == "not_dual"
    assert fix.verifier_ground_truth["overall_status"] == "FAILED"
    assert "bounded chiral-ring consistency" in fix.verifier_ground_truth[
        "failed_obligations"
    ]
    assert fix.metadata.perturbation_type == "w_drop"
    assert fix.metadata.extra["source_fixture_id"] == dp0_positive_n3_node0.fixture_id
    assert "dropped_term" in fix.metadata.extra
    # The candidate has one fewer W term than the positive.
    assert (
        len(fix.candidate["superpotential"])
        == len(dp0_positive_n3_node0.candidate["superpotential"]) - 1
    )


def test_w_drop_no_w_discards():
    """Empty-W positive must be discarded with a clear reason."""

    base = Fixture(
        fixture_id="empty_W_positive",
        ground_truth_label="dual",
        verifier_ground_truth={"overall_status": "CERTIFIED", "failed_obligations": []},
        electric=_dp0_electric_json(N=3),
        candidate={
            **_dp0_electric_json(N=3),
            "superpotential": [],
        },
        metadata=FixtureMetadata(source="dp0_toric", seed=0, perturbation_type="none"),
    )
    fix, log = attempt_w_drop(positive=base, fixture_id="bad", seed=0)
    assert fix is None
    assert log.generation_status == "discarded"
    assert "cannot_drop_W" in log.discard_reason


def test_w_drop_determinism(dp0_positive_n3_node0: Fixture):
    """Same seed -> byte-identical fixture (Rule 10 reproducibility)."""

    a, _ = attempt_w_drop(
        positive=dp0_positive_n3_node0,
        fixture_id="dp0_wdrop_det",
        seed=7,
    )
    b, _ = attempt_w_drop(
        positive=dp0_positive_n3_node0,
        fixture_id="dp0_wdrop_det",
        seed=7,
    )
    assert a is not None and b is not None
    assert fixture_to_dict(a) == fixture_to_dict(b)


# ----------------------------------------------------------------------
# Type-4 W sign swap (with silent-miss handling).
# ----------------------------------------------------------------------


def test_w_sign_swap_failed_seed_labels_correctly(dp0_positive_n3_node0: Fixture):
    """For a seed where the swap breaks the verifier, label must be 'not_dual'."""

    fix, log = attempt_w_sign_swap(
        positive=dp0_positive_n3_node0,
        fixture_id="dp0_wsign_seed0",
        seed=0,
    )
    assert fix is not None, log.discard_reason
    assert fix.ground_truth_label == "not_dual"
    assert fix.metadata.extra["flipped_term"]
    assert Fraction(fix.metadata.extra["new_coefficient"]) == -Fraction(
        fix.metadata.extra["old_coefficient"]
    )


def test_w_sign_swap_silent_miss_seed_labels_as_dual(
    dp0_positive_n3_node0: Fixture,
) -> None:
    """Rule 9 silent-miss handling: at seed=2 the dP_0 W sign swap stays
    CERTIFIED (Phase 2b sediment). The generator must label the fixture
    as 'dual' (per Rule 6) — NOT mislabel as 'not_dual'. The script
    driver is responsible for noticing and retrying with a different
    seed; the generator just reports honestly."""

    fix, log = attempt_w_sign_swap(
        positive=dp0_positive_n3_node0,
        fixture_id="dp0_wsign_silent_miss",
        seed=2,
    )
    assert fix is not None, log.discard_reason
    # Pin: the verifier accepts this perturbation as still CERTIFIED.
    if fix.verifier_ground_truth["overall_status"] == "CERTIFIED":
        assert fix.ground_truth_label == "dual"
    else:
        # If the underlying physics ever changes such that seed=2 starts
        # failing, accept that too — but the labeling must stay
        # consistent with the verifier verdict.
        assert fix.ground_truth_label == "not_dual"


# ----------------------------------------------------------------------
# Type-3 R naive.
# ----------------------------------------------------------------------


def test_r_naive_failed_negative(dp0_positive_n3_node0: Fixture):
    fix, log = attempt_r_naive(
        positive=dp0_positive_n3_node0,
        fixture_id="dp0_rnaive_seed0",
        seed=0,
    )
    assert fix is not None, log.discard_reason
    assert fix.ground_truth_label == "not_dual"
    assert fix.verifier_ground_truth["overall_status"] == "FAILED"
    assert fix.metadata.perturbation_type == "r_naive"
    extra = fix.metadata.extra
    assert extra["perturbed_field"]
    assert Fraction(extra["new_r"]) == Fraction(extra["old_r"]) + Fraction(
        extra["delta"]
    )
    # The candidate has exactly one arrow with the new R-charge.
    by_label = {a["label"]: a["r_charge"] for a in fix.candidate["arrows"]}
    assert by_label[extra["perturbed_field"]] == extra["new_r"]


def test_r_naive_uses_delta_choices(dp0_positive_n3_node0: Fixture):
    """The delta is drawn from `delta_choices`; an empty argument set surfaces."""

    custom = (Fraction(1, 6),)
    fix, _ = attempt_r_naive(
        positive=dp0_positive_n3_node0,
        fixture_id="dp0_rnaive_custom",
        seed=0,
        delta_choices=custom,
    )
    assert fix is not None
    assert Fraction(fix.metadata.extra["delta"]) == Fraction(1, 6)


# ----------------------------------------------------------------------
# Type-1/2 rank perturb.
# ----------------------------------------------------------------------


def test_rank_perturb_failed_negative(dp0_positive_n3_node0: Fixture):
    fix, log = attempt_rank_perturb(
        positive=dp0_positive_n3_node0,
        fixture_id="dp0_rank_seed0",
        seed=0,
    )
    assert fix is not None, log.discard_reason
    assert fix.ground_truth_label == "not_dual"
    assert fix.metadata.perturbation_type == "rank_perturb"
    extra = fix.metadata.extra
    assert extra["new_rank"] == extra["old_rank"] + extra["delta"]
    assert extra["new_rank"] >= 2  # SU(N>=2) guarantee


def test_rank_perturb_lifts_su2_off_floor():
    """The SU(N>=2) clamp: if the chosen node has rank 2 and delta=-1
    would land at 1, the generator must bump to +1."""

    candidate = _dp0_electric_json(N=3)
    candidate["ranks"] = [2, 3, 3]  # node 0 is at the SU(2) floor.

    seed_positive = Fixture(
        fixture_id="su2_floor_positive",
        ground_truth_label="dual",
        verifier_ground_truth={"overall_status": "CERTIFIED", "failed_obligations": []},
        electric=_dp0_electric_json(N=3),
        candidate=candidate,
        metadata=FixtureMetadata(
            source="synthetic", seed=0, perturbation_type="none"
        ),
    )

    # Find a seed that lands the rng on node 0 with delta=-1; then check
    # the generator clamps it. We just sweep a few seeds.
    saw_clamp = False
    for seed in range(20):
        fix, _ = attempt_rank_perturb(
            positive=seed_positive,
            fixture_id=f"su2_floor_{seed}",
            seed=seed,
        )
        if fix is None:
            continue
        e = fix.metadata.extra
        if e["old_rank"] == 2 and e["new_rank"] < 2:
            pytest.fail("rank dropped below 2")
        if e["old_rank"] == 2 and e["delta"] == 1:
            saw_clamp = True
    # We don't strictly require the clamp branch to fire in the sweep —
    # the assertion above is the real safety net. This second check is
    # just a sanity that the clamp path is reachable at all.
    assert saw_clamp, "did not exercise the SU(2) floor clamp path"


# ----------------------------------------------------------------------
# Wrong-pair: only meaningful across families.
# ----------------------------------------------------------------------


def test_wrong_pair_across_families_fails(
    dp0_positive_n3_node0: Fixture,
    f0_positive_n3_node0: Fixture,
):
    """Mixing a dP_0 electric with an F_0 II candidate must FAIL on
    structural global anomalies / chiral-ring matching."""

    fix, log = attempt_wrong_pair(
        electric_from=dp0_positive_n3_node0,
        candidate_from=f0_positive_n3_node0,
        fixture_id="wrong_pair_dp0_x_f0",
        seed=0,
    )
    assert fix is not None, log.discard_reason
    assert fix.ground_truth_label == "not_dual"
    assert fix.metadata.perturbation_type == "wrong_pair"
    assert fix.metadata.extra["source_electric_id"] == dp0_positive_n3_node0.fixture_id
    assert fix.metadata.extra["source_candidate_id"] == f0_positive_n3_node0.fixture_id


def test_wrong_pair_within_family_can_remain_dual():
    """dP_0 mutations at different nodes give magnetically equivalent
    theories (the engine output certifies cross-pair). This is why the
    benchmark wrong-pair class must use unrelated *families*, not
    different mutations of the same seed.

    The generator itself reports honestly (label follows verifier);
    discarding such accidents is the script's job."""

    electric = _dp0_electric_json(N=3)
    pos0, _ = attempt_positive(
        electric_json=electric, node=0, N=3, source_name="dp0_toric",
        fixture_id="dp0_p0", seed=0,
    )
    pos1, _ = attempt_positive(
        electric_json=electric, node=1, N=3, source_name="dp0_toric",
        fixture_id="dp0_p1", seed=0,
    )
    fix, _ = attempt_wrong_pair(
        electric_from=pos0, candidate_from=pos1,
        fixture_id="dp0_x_dp0", seed=0,
    )
    assert fix is not None
    # Per Rule 6 the label follows the verifier verdict; same-family
    # mixing routes through CERTIFIED so the label is "dual".
    assert fix.ground_truth_label == "dual"


# ----------------------------------------------------------------------
# Verifier-gate behaviour (Rule 6 ambiguous-discard).
# ----------------------------------------------------------------------


def test_evaluate_pair_ground_truth_on_malformed_json_returns_error():
    """Wrong-pair across families with incompatible label conventions
    might fail the pure-quiver JSON validator — that gets surfaced as
    "ERROR" so callers can discard rather than crash."""

    malformed = {
        "name": "broken",
        "node_labels": ["G0"],
        "ranks": [3],
        "u1_globals": ["U(1)_R"],
        "arrows": [
            # Two arrows on the same edge but with wrong machine labels.
            {"label": "Wrong[99]", "source": 0, "target": 0, "r_charge": "1"},
        ],
        "superpotential": [],
    }
    overall, failed = evaluate_pair_ground_truth(malformed, malformed)
    assert overall == "ERROR"
    assert failed and "Wrong[99]" in failed[0]


def test_gate_and_build_fixture_discards_ambiguous_overall_status():
    """Synthetic test: when evaluate yields neither CERTIFIED nor FAILED,
    no fixture is built and the log records the discard reason."""

    md = FixtureMetadata(source="synthetic", seed=0, perturbation_type="none")
    malformed = {
        "name": "broken",
        "node_labels": ["G0"],
        "ranks": [3],
        "u1_globals": ["U(1)_R"],
        "arrows": [
            {"label": "Wrong[0]", "source": 0, "target": 0, "r_charge": "1"},
        ],
        "superpotential": [],
    }
    fix, log = gate_and_build_fixture(
        electric_json=malformed,
        candidate_json=malformed,
        fixture_id="bad_pair",
        metadata=md,
    )
    assert fix is None
    assert log.generation_status == "discarded"
    assert log.discard_reason.startswith("ambiguous_ground_truth(overall=ERROR")


# ----------------------------------------------------------------------
# Determinism / repeatability.
# ----------------------------------------------------------------------


def test_positive_is_deterministic():
    """Same arguments -> byte-identical fixture; positive generation has
    no internal randomness."""

    a, _ = attempt_positive(
        electric_json=_dp0_electric_json(N=3),
        node=0, N=3, source_name="dp0_toric",
        fixture_id="dp0_det", seed=42,
    )
    b, _ = attempt_positive(
        electric_json=_dp0_electric_json(N=3),
        node=0, N=3, source_name="dp0_toric",
        fixture_id="dp0_det", seed=42,
    )
    assert a is not None and b is not None
    assert fixture_to_dict(a) == fixture_to_dict(b)


def test_negative_seed_changes_perturbation_target(dp0_positive_n3_node0: Fixture):
    """Different seeds should reach different perturbation indices."""

    seen_targets = set()
    for seed in range(10):
        fix, _ = attempt_w_drop(
            positive=dp0_positive_n3_node0,
            fixture_id=f"dp0_wdrop_seed{seed}",
            seed=seed,
        )
        if fix is None:
            continue
        seen_targets.add(tuple(fix.metadata.extra["dropped_term"]))
    assert len(seen_targets) > 1, "seed sweep should hit more than one W term"
