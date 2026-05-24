"""Phase 2b-β duality tests: dP_0 electric (toric) ↔ magnetic (Seiberg-dualized).

This is the first cross-theory duality verdict in the verifier. The
electric side is the dP_0 toric phase (3-node cyclic SU(3)^3 quiver
with 9 bifundamentals and the ε W from Phase 2a+); the magnetic side
is the single-node Seiberg dual of node A (12 bifundamentals on a
mixed-rank SU(6)×SU(3)×SU(3) quiver with the integrated-out W_eff
from Phase 2b-α). The two sides differ in:
  - Gauge ranks: (3, 3, 3) vs (6, 3, 3)
  - Field count: 9 vs 12 bifundamentals
  - Field R-charges: all 2/3 vs mixed {1/3, 1/3, 4/3}
  - W structure: 6-term antisymmetric ε vs 9-term symmetric meson coupling

Yet — by Seiberg duality — they should have isomorphic chiral rings at
every degree. The bounded chiral-ring consistency check pins this at
each (length, R-charge) block up to the cutoff.

Cutoff strategy:
  - L = 3 (this file's headline regression): 1 block (3, R=2) on each
    side, dim 10 = Sym^3(C^3). Tests run in milliseconds.
  - L = 6 (this file's slow regression, marked @pytest.mark.slow):
    2 blocks (3, R=2) → 10 and (6, R=4) → 28. Wall-clock ~70-80 s
    (magnetic side at L=6 dominates due to Fraction-Gaussian rank on
    a basis of ~378 cyclic words; the electric side is ~4 s by
    comparison). Run with default `pytest` or skip via
    `pytest -m "not slow"` for fast dev loop.

Spec source: docs/phase2b_dp0_magnetic.md describes the magnetic
construction; docs/phase2a_pure_quiver_chiral_ring.md describes the
verdict semantics this test exercises.
"""

from __future__ import annotations

import time
from fractions import Fraction

import pytest

from dualitycert.core.objects import DualityClaim, Theory
from dualitycert.core.status import Status
from dualitycert.groups.u1 import u1_r
from dualitycert.qft.dualities import evaluate_claim
from dualitycert.qft.pure_quiver_builder import (
    arrow_names,
    build_dp0_magnetic_effective,
    build_pure_quiver,
    dp0_superpotential,
)


def _electric_dp0() -> "Theory":
    """Build the dP_0 toric-phase electric theory (Phase 2a+ fixture)."""
    r = Fraction(2, 3)
    n01 = arrow_names(0, 1, 3)
    n12 = arrow_names(1, 2, 3)
    n20 = arrow_names(2, 0, 3)
    return build_pure_quiver(
        ranks=(3, 3, 3),
        arrows={(0, 1): [r] * 3, (1, 2): [r] * 3, (2, 0): [r] * 3},
        superpotential=dp0_superpotential(n01, n12, n20),
        u1_globals=(u1_r(),),
    )


def _dp0_duality_claim(*, max_length: int) -> DualityClaim:
    """Build the cross-theory dP_0 duality claim."""
    return DualityClaim(
        name=f"dP_0 duality L={max_length}",
        electric_theory=_electric_dp0(),
        magnetic_theory=build_dp0_magnetic_effective(N=3),
        metadata={
            "duality_profile": f"dp0_duality_L{max_length}",
            "theory_kind": "pure_quiver",
            "bounded_chiral_ring": {
                "max_length": max_length,
                "require_r_graded": True,
            },
        },
    )


def _results_by_name(certificate) -> dict:
    return {r.name: r for r in certificate.obligation_results}


# ---------------------------------------------------------------------------
# Fast regression: L=3 duality check
# ---------------------------------------------------------------------------

def test_dp0_duality_certified_at_L3():
    """Headline regression: the cross-theory duality CERTIFIES at L=3.

    Asserts:
      - All four upstream gauge anomaly obligations CERTIFY on both
        sides (P4 prerequisite for r_graded mode).
      - bounded_chiral_ring_consistency CERTIFIES in R-graded mode at
        cutoff L=3.
      - The single (length=3, R=2) block has dim 10 on both sides.
      - No failed blocks; no fallback to length-only mode.
    """
    claim = _dp0_duality_claim(max_length=3)
    cert = evaluate_claim(claim)
    by_name = _results_by_name(cert)

    for key in (
        "electric gauge anomaly cancellation",
        "magnetic gauge anomaly cancellation",
        "electric gauge-global mixed anomaly cancellation",
        "magnetic gauge-global mixed anomaly cancellation",
    ):
        assert by_name[key].status == Status.CERTIFIED, (
            f"{key} was {by_name[key].status.value}"
        )

    bounded = by_name["bounded chiral-ring consistency"]
    assert bounded.status == Status.CERTIFIED
    assert "PASSED_BOUNDED_CHIRAL_RING_CONSISTENCY" in bounded.message
    details = bounded.details
    assert details["cutoff_L"] == 3
    assert details["r_graded"] is True
    assert details["r_graded_blocked_by"] == []
    assert details["failed_blocks"] == []

    tested = details["tested_blocks"]
    assert len(tested) == 1
    (block,) = tested
    assert block["length"] == 3
    assert block["r_charge"] == "2"
    assert block["electric_dim"] == 10
    assert block["magnetic_dim"] == 10


def test_dp0_duality_arrow_labels_differ_between_sides():
    """The two sides have structurally different arrow sets — the
    certificate must list each side's machine labels independently
    (electric has 9 bifund X01/X12/X20[0..2]; magnetic has 12 bifund
    X02/X10[0..2] + X21[0..5]). This pins arrow_machine_labels_*
    splitting in the §7 schema on a real cross-theory case."""
    claim = _dp0_duality_claim(max_length=3)
    cert = evaluate_claim(claim)
    bounded = _results_by_name(cert)["bounded chiral-ring consistency"]

    electric_labels = bounded.details["arrow_machine_labels_electric"]
    magnetic_labels = bounded.details["arrow_machine_labels_magnetic"]

    expected_electric = sorted(
        [f"X01[{i}]" for i in range(3)]
        + [f"X12[{i}]" for i in range(3)]
        + [f"X20[{i}]" for i in range(3)]
    )
    expected_magnetic = sorted(
        [f"X02[{i}]" for i in range(3)]
        + [f"X10[{i}]" for i in range(3)]
        + [f"X21[{i}]" for i in range(6)]
    )

    assert electric_labels == expected_electric
    assert magnetic_labels == expected_magnetic
    assert electric_labels != magnetic_labels  # structurally distinct quivers


# ---------------------------------------------------------------------------
# Slow regression: full L=6 duality check
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_dp0_duality_certified_at_L6():
    """The cross-theory duality CERTIFIES at the default L=6 cutoff.

    Two blocks must be tested and both must match:
      - (length=3, R=2): both sides have dim 10 (Sym^3(C^3))
      - (length=6, R=4): both sides have dim 28 (Sym^6(C^3))

    This is the physical Seiberg-duality check at the level the
    verifier can probe: the bounded single-trace chiral ring of the
    electric toric phase matches that of the magnetic Seiberg-dualized
    phase at every length up to 6, despite the magnetic having
    different rank, field count, R-charges, and W structure.

    Wall-clock ~70-80 s, dominated by the magnetic side at length 6.
    Marked slow; skip via `pytest -m "not slow"`.
    """
    claim = _dp0_duality_claim(max_length=6)

    t0 = time.perf_counter()
    cert = evaluate_claim(claim)
    elapsed = time.perf_counter() - t0
    # Sanity ceiling — 300s is far more than the observed ~75s,
    # but high enough to absorb CI noise without flaking.
    assert elapsed < 300.0, f"L=6 duality took {elapsed:.1f}s"

    bounded = _results_by_name(cert)["bounded chiral-ring consistency"]
    assert bounded.status == Status.CERTIFIED
    details = bounded.details
    assert details["cutoff_L"] == 6
    assert details["r_graded"] is True
    assert details["failed_blocks"] == []

    blocks = {(b["length"], b["r_charge"]): b for b in details["tested_blocks"]}
    assert len(blocks) == 2

    b3 = blocks[(3, "2")]
    assert b3["electric_dim"] == 10
    assert b3["magnetic_dim"] == 10

    b6 = blocks[(6, "4")]
    assert b6["electric_dim"] == 28
    assert b6["magnetic_dim"] == 28


# ---------------------------------------------------------------------------
# Adversarial: drop one W term from magnetic → bounded chiral-ring catches it
# ---------------------------------------------------------------------------

def _magnetic_with_term_dropped(target_factor_labels: tuple[str, ...]) -> Theory:
    """Build the magnetic theory with one specific W monomial deleted.

    `target_factor_labels` identifies the monomial by its (machine-label)
    factor tuple in the order build_dp0_magnetic_effective emits them
    (q, q̃, M). Returns a Theory identical in gauge nodes, fields, and
    global symmetries — only the superpotential is shortened by one term.
    """
    full = build_dp0_magnetic_effective(N=3)
    factor_names_to_drop = target_factor_labels

    kept_terms = tuple(
        term for term in full.superpotential_terms
        if tuple(name for name, _ in term.factors) != factor_names_to_drop
    )
    if len(kept_terms) != len(full.superpotential_terms) - 1:
        raise AssertionError(
            f"Expected to drop exactly 1 term matching {factor_names_to_drop!r}; "
            f"matched {len(full.superpotential_terms) - len(kept_terms)} terms"
        )
    return Theory(
        name="dP_0 magnetic with one W term dropped",
        gauge_nodes=full.gauge_nodes,
        fields=full.fields,
        superpotential_terms=kept_terms,
        global_symmetries=full.global_symmetries,
    )


def test_dp0_duality_with_magnetic_W_diagonal_dropped_fails_at_length_3():
    """Adversarial Type-4 regression: drop the M^{(0,0)} q̃[0] q[0] term
    from the magnetic superpotential. R-charges and gauge content
    unchanged → all upstream anomaly + superpotential checks still
    CERTIFY (they cannot see this perturbation). But the F-term ideal
    on the magnetic side weakens: ∂_{X02[0]}, ∂_{X10[0]}, ∂_{X21[0]}
    each lose one path, so the bounded chiral-ring quotient at length
    3 grows from the Seiberg-duality-required Sym^3(C^3) = 10 to a
    larger 14.

    This is precisely the failure mode the bounded chiral-ring check
    was designed to catch and that anomaly / superpotential-R checks
    miss — exactly the adversarial signal of the verifier: a proposer
    might pattern-match "dP_0 + Seiberg dual = consistent" but still
    fail to detect that *this particular W* has been broken without
    doing the F-ideal arithmetic.
    """
    broken_magnetic = _magnetic_with_term_dropped(("X10[0]", "X02[0]", "X21[0]"))
    claim = DualityClaim(
        name="dP_0 duality (magnetic W[0] dropped)",
        electric_theory=_electric_dp0(),
        magnetic_theory=broken_magnetic,
        metadata={
            "duality_profile": "dp0_duality_W_dropped",
            "theory_kind": "pure_quiver",
            "bounded_chiral_ring": {"max_length": 3, "require_r_graded": True},
        },
    )
    cert = evaluate_claim(claim)
    by_name = _results_by_name(cert)

    # Upstream checks remain CERTIFIED — they cannot detect this
    # superpotential perturbation:
    for key in (
        "electric gauge anomaly cancellation",
        "magnetic gauge anomaly cancellation",
        "electric gauge-global mixed anomaly cancellation",
        "magnetic gauge-global mixed anomaly cancellation",
        "electric superpotential consistency",
        "magnetic superpotential consistency",
    ):
        assert by_name[key].status == Status.CERTIFIED, (
            f"{key} unexpectedly status {by_name[key].status.value} "
            "— this regression assumes the perturbation is invisible to "
            "anomaly / R-charge / W-consistency checks"
        )

    # Bounded chiral-ring catches it:
    bounded = by_name["bounded chiral-ring consistency"]
    assert bounded.status == Status.FAILED
    assert "FAILED_AT_BLOCK" in bounded.message
    assert "length=3" in bounded.message
    assert "r_charge=2" in bounded.message

    details = bounded.details
    assert len(details["failed_blocks"]) == 1
    (failed,) = details["failed_blocks"]
    assert failed["length"] == 3
    assert failed["r_charge"] == "2"
    assert failed["electric_dim"] == 10
    assert failed["magnetic_dim"] == 14

    # Sample operators populated on failed block — diagnostic value
    # for downstream consumers and human inspection.
    samples = details["sample_operators"]
    block_key = "length=3,r=2"
    assert block_key in samples
    assert len(samples[block_key]["electric"]) > 0
    assert len(samples[block_key]["magnetic"]) > 0
