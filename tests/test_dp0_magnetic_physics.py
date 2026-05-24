"""Phase 2b-α physics tests for the dP_0 magnetic dual (effective form).

Black-box validation of the magnetic side of dP_0 single-node Seiberg
duality alone — no DualityClaim cross-side comparison yet (that's
Phase 2b-β). The goal here is to confirm the magnetic theory is
well-formed standalone:

  - All four upstream gauge anomaly obligations CERTIFY through
    evaluate_claim on a self-equivalence claim (electric = magnetic =
    the dP_0 magnetic dual).
  - bounded_chiral_ring_consistency CERTIFIES on the self-equivalence.
  - The single block at length 3 has dim 10 — the same Sym^3(C^3)
    mesonic count as the electric side (Phase 2a+ pinned dim 10 at
    length 3 there). This is the physical signal that "magnetic
    chiral ring matches electric at the degree-3 piece" even though
    the magnetic field content (12 bifund, mixed-rank SU(6)×SU(3)×SU(3),
    different R-charges) is structurally unlike electric.

Cutoff: we use L = 3 in the tests so each evaluate_claim call stays in
the few-seconds range. The magnetic theory at L = 6 also CERTIFIES
(verified offline) with dim 28 at length 6, matching electric — but
that run is ~140 s due to Fraction-Gaussian rank scaling on the larger
basis, so we don't put it in the regular pytest path. Phase 2b-β will
take that hit deliberately when it compares electric ↔ magnetic.

Spec source: see docs/phase2b_dp0_magnetic.md for the physics
derivation (field content, R-charges, anomaly verification, W_eff).
"""

from __future__ import annotations

import time

import pytest

from dualitycert.core.objects import DualityClaim
from dualitycert.core.status import Status
from dualitycert.qft.dualities import evaluate_claim
from dualitycert.qft.pure_quiver_builder import build_dp0_magnetic_effective


_TIMING_BUDGET_SECONDS = 60.0  # Generous cap; L=3 runs land around a few seconds.


def _magnetic_self_claim(*, max_length: int = 3) -> DualityClaim:
    """Self-equivalence claim on the magnetic theory: electric side =
    magnetic side = the same dP_0 magnetic dual."""
    magnetic = build_dp0_magnetic_effective(N=3)
    return DualityClaim(
        name=f"dP_0 magnetic self (L={max_length})",
        electric_theory=magnetic,
        magnetic_theory=magnetic,
        metadata={
            "duality_profile": f"dp0_mag_self_L{max_length}",
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
# Field content sanity (no evaluate_claim, just constructor)
# ---------------------------------------------------------------------------

def test_dp0_magnetic_field_content_12_bifund_with_3_3_6_multiplicities():
    """The effective magnetic theory has 12 bifundamental fields organized
    as edges (3, 3, 6): 3 q̃ on A→C (X02), 3 q on B→A (X10), 6 M^{(a,c)}
    on C→B (X21). All Field.multiplicity values are 1 (the builder
    expands multi-copy edges into one Field per copy)."""
    magnetic = build_dp0_magnetic_effective(N=3)

    assert len(magnetic.fields) == 12
    assert all(f.multiplicity == 1 for f in magnetic.fields)

    names = sorted(f.name for f in magnetic.fields)
    expected = sorted(
        [f"X02[{i}]" for i in range(3)]
        + [f"X10[{i}]" for i in range(3)]
        + [f"X21[{i}]" for i in range(6)]
    )
    assert names == expected


def test_dp0_magnetic_gauge_groups_are_su6_su3_su3():
    """Gauge group structure SU(2N) × SU(N) × SU(N) at nodes A, B, C.
    With N = 3: SU(6) × SU(3) × SU(3)."""
    magnetic = build_dp0_magnetic_effective(N=3)
    ranks = tuple(g.N for g in magnetic.gauge_nodes)
    assert ranks == (6, 3, 3)


def test_dp0_magnetic_w_has_9_cubic_terms():
    """W_eff = M^{(a,c)} q̃[a] q[c] expanded over the 6 symmetric pairs:
    3 diagonal terms (a = c) + 3 off-diagonal pairs × 2 monomials each
    = 9 SuperpotentialTerms, each cubic."""
    magnetic = build_dp0_magnetic_effective(N=3)
    assert len(magnetic.superpotential_terms) == 9
    for term in magnetic.superpotential_terms:
        # Each W term has 3 factors, each with power 1.
        powers = [p for _, p in term.factors]
        assert powers == [1, 1, 1]


# ---------------------------------------------------------------------------
# Anomaly + bounded chiral-ring via evaluate_claim (the regression gate)
# ---------------------------------------------------------------------------

def test_dp0_magnetic_self_equivalence_anomalies_and_bounded_certify_at_L3():
    """End-to-end on the magnetic side: every upstream anomaly check
    CERTIFIES (validating my Phase 2b-α derivation in
    docs/phase2b_dp0_magnetic.md §4) and the bounded chiral-ring check
    CERTIFIES at L = 3 in R-graded mode. This is the headline regression
    gate for "the magnetic theory is well-formed standalone"."""
    claim = _magnetic_self_claim(max_length=3)

    t0 = time.perf_counter()
    cert = evaluate_claim(claim)
    elapsed = time.perf_counter() - t0
    assert elapsed < _TIMING_BUDGET_SECONDS, (
        f"magnetic L=3 evaluate_claim took {elapsed:.1f}s, exceeding budget"
    )

    by_name = _results_by_name(cert)

    # All 4 upstream anomaly obligations must CERTIFY.
    for key in (
        "electric gauge anomaly cancellation",
        "magnetic gauge anomaly cancellation",
        "electric gauge-global mixed anomaly cancellation",
        "magnetic gauge-global mixed anomaly cancellation",
    ):
        assert key in by_name, f"upstream {key!r} missing from certificate"
        assert by_name[key].status == Status.CERTIFIED, (
            f"{key} was {by_name[key].status.value}, expected CERTIFIED"
        )

    bounded = by_name["bounded chiral-ring consistency"]
    assert bounded.status == Status.CERTIFIED
    assert bounded.details["cutoff_L"] == 3
    assert bounded.details["r_graded"] is True
    assert bounded.details["r_graded_blocked_by"] == []


def test_dp0_magnetic_self_equivalence_block_dim_matches_electric_at_L3():
    """At L = 3 the magnetic theory's bounded chiral-ring quotient
    dimension matches the electric side's: a single (length=3, R=2)
    block with dim 10 = Sym^3(C^3).

    Physical significance: the electric and magnetic theories differ in
    rank ((3,3,3) vs (6,3,3)), in field count (9 vs 12 bifund), in
    field R-charges (all 2/3 vs mixed 1/3 + 4/3), and in superpotential
    structure (cubic ε-form vs cubic meson-coupling). Yet the degree-3
    piece of the bounded single-trace chiral ring is the same 10-dim
    Sym^3(C^3) — exactly what Seiberg duality requires.

    (Length 4/5 emit no blocks because magnetic arrows also realize a
    3-cycle A → C → B → A, closing only at multiples of 3.)
    """
    claim = _magnetic_self_claim(max_length=3)
    cert = evaluate_claim(claim)
    bounded = _results_by_name(cert)["bounded chiral-ring consistency"]

    tested = bounded.details["tested_blocks"]
    assert len(tested) == 1, f"expected 1 block at L=3, got {len(tested)}"

    (block,) = tested
    assert block["length"] == 3
    assert block["r_charge"] == "2"
    assert block["electric_dim"] == 10
    assert block["magnetic_dim"] == 10


def test_dp0_magnetic_arrow_machine_labels_match_spec():
    """Verify the certificate carries the 12 machine labels from the
    spec — X02[0..2] (q̃), X10[0..2] (q), X21[0..5] (M^{(a,c)}). The
    naming is what docs/phase2b_dp0_magnetic.md §3.1 documents and what
    the Phase 2b-β duality test will rely on."""
    claim = _magnetic_self_claim(max_length=3)
    cert = evaluate_claim(claim)
    bounded = _results_by_name(cert)["bounded chiral-ring consistency"]

    expected = sorted(
        [f"X02[{i}]" for i in range(3)]
        + [f"X10[{i}]" for i in range(3)]
        + [f"X21[{i}]" for i in range(6)]
    )
    # Self-equivalence: both sides have the same labels.
    assert bounded.details["arrow_machine_labels_electric"] == expected
    assert bounded.details["arrow_machine_labels_magnetic"] == expected
