"""Phase 2b adversarial characterization: probe what the dP_0 duality
verifier catches and what it misses.

Each test perturbs the magnetic side of the dP_0 electric ↔ magnetic
Seiberg duality fixture in a controlled way, runs the perturbed claim
through `evaluate_claim`, and pins the resulting verdict. Together
these tests build a "catch/miss map" of the verifier on dP_0:

  CATCHES via bounded chiral-ring consistency:
    - Drop a diagonal W term            → FAILED, dim 10 ≠ 14 (test_dp0_duality.py)
    - Drop an off-diagonal W term       → FAILED, dim 10 ≠  4
    - Add a non-redundant fake W term   → FAILED, dim 10 ≠  7

  CATCHES via upstream P3 / P4 (anomaly + superpotential):
    - R-charge reshuffle on q (breaks anomaly + breaks W R=2 simultaneously
      due to magnetic R-charges being uniquely determined by anomalies)

  MISSES (true blindspots):
    - Overall W rescale W → c·W (any c ≠ 0):
        Mathematically provable — F-ideal is the linear span of {∂_X W};
        rescaling W by c rescales every generator by c, leaving the
        ideal invariant. Verifier necessarily cannot detect this.
    - Overall sign flip W → −W: same as above with c = −1.
    - Single-term coefficient change W[0] → 2·W[0]:
        NOT a provable blindspot in general — depends on whether the
        coefficient-perturbed F-ideal happens to equal the original.
        On dP_0 magnetic this specific change IS invisible due to an
        algebraic coincidence: the perturbed generator differs from the
        original by a vector that is already in the original ideal.
        Pinned here, but not a generic verifier limitation.
    - Add a redundant R=2 closed-walk W term M^{(0,0)} q̃[1] q[1]:
        The added F-relation is already implied by existing F-ideal —
        a "no-op add". Different from C' in that the redundancy is at
        the ideal level, not at the generator level.

  MISSES under r_graded=False (length-only fallback):
    - R-charge reshuffle: with the R-grading turned off, the F-ideal
      structure alone is unchanged, so quotient dims still match → the
      bounded chiral-ring check returns CERTIFIED even though magnetic
      anomalies / W consistency have FAILED upstream. Documents the
      layered defense: in r_graded mode the upstream catches; in
      length-only fallback the catch is gone.

The point of pinning ALL of these — both catches and misses — is to
give downstream evaluation tools a precise specification of what the
verifier asserts and what it does NOT assert.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from dualitycert.core.objects import (
    DualityClaim,
    Field,
    SuperpotentialTerm,
    Theory,
)
from dualitycert.core.status import Status
from dualitycert.groups.u1 import u1_r
from dualitycert.qft.dualities import evaluate_claim
from dualitycert.qft.pure_quiver_builder import (
    arrow_names,
    build_dp0_magnetic_effective,
    build_pure_quiver,
    dp0_superpotential,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _electric_dp0() -> Theory:
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


def _full_magnetic() -> Theory:
    return build_dp0_magnetic_effective(N=3)


def _claim_with_magnetic(magnetic: Theory, *, max_length: int = 3,
                         require_r_graded: bool = True,
                         label: str) -> DualityClaim:
    return DualityClaim(
        name=f"dP_0 adversarial: {label}",
        electric_theory=_electric_dp0(),
        magnetic_theory=magnetic,
        metadata={
            "duality_profile": f"adv_{label}",
            "theory_kind": "pure_quiver",
            "bounded_chiral_ring": {
                "max_length": max_length,
                "require_r_graded": require_r_graded,
            },
        },
    )


def _results_by_name(certificate) -> dict:
    return {r.name: r for r in certificate.obligation_results}


def _magnetic_with_W(W_terms: tuple[SuperpotentialTerm, ...], *,
                     label: str) -> Theory:
    base = _full_magnetic()
    return Theory(
        name=f"dP_0 magnetic ({label})",
        gauge_nodes=base.gauge_nodes,
        fields=base.fields,
        superpotential_terms=W_terms,
        global_symmetries=base.global_symmetries,
    )


def _magnetic_drop_term(target_factor_labels: tuple[str, ...], *,
                        label: str) -> Theory:
    base = _full_magnetic()
    kept = tuple(
        t for t in base.superpotential_terms
        if tuple(name for name, _ in t.factors) != target_factor_labels
    )
    if len(kept) != len(base.superpotential_terms) - 1:
        raise AssertionError(f"Expected to drop 1 term matching {target_factor_labels}")
    return _magnetic_with_W(kept, label=label)


def _magnetic_add_term(factors_to_add: tuple[str, ...], *,
                       coefficient: Fraction = Fraction(1),
                       label: str) -> Theory:
    base = _full_magnetic()
    new_term = SuperpotentialTerm(
        factors=tuple((name, 1) for name in factors_to_add),
        coefficient=coefficient,
    )
    return _magnetic_with_W(base.superpotential_terms + (new_term,), label=label)


# ---------------------------------------------------------------------------
# A: drop an OFF-DIAGONAL W term (M^{(0,1)} q̃[0] q[1])
# ---------------------------------------------------------------------------

def test_off_diagonal_W_drop_caught_dim_e10_m4():
    """Drop the W monomial M^{(0,1)} q̃[0] q[1] = X10[1] · X02[0] · X21[1].

    Counter-intuitive in direction: dropping this term *increases* the
    F-ideal at length 3 (magnetic dim drops below electric dim 10),
    rather than weakening it as in the diagonal-drop case. The
    intuition: M^{(0,1)} originally couples to a SYMMETRIC sum
    (q̃[0] q[1] + q̃[1] q[0]). Dropping one of the two monomials breaks
    the symmetric structure, leaving the OTHER monomial as a stronger,
    more restrictive F-relation (X02[1] · X10[0] = 0 in the chiral
    ring rather than a symmetric combination).

    Pinned dim 4 — any algorithm change that shifts this number will
    flag a regression.
    """
    magnetic = _magnetic_drop_term(("X10[1]", "X02[0]", "X21[1]"),
                                   label="off_diag_drop")
    cert = evaluate_claim(_claim_with_magnetic(magnetic, label="A"))
    by_name = _results_by_name(cert)

    # Anomaly + W-consistency still pass — they can't see this perturbation.
    for k in ("electric gauge anomaly cancellation",
              "magnetic gauge anomaly cancellation",
              "electric gauge-global mixed anomaly cancellation",
              "magnetic gauge-global mixed anomaly cancellation",
              "electric superpotential consistency",
              "magnetic superpotential consistency"):
        assert by_name[k].status == Status.CERTIFIED

    bounded = by_name["bounded chiral-ring consistency"]
    assert bounded.status == Status.FAILED
    failed = bounded.details["failed_blocks"]
    assert len(failed) == 1
    assert failed[0]["length"] == 3
    assert failed[0]["electric_dim"] == 10
    assert failed[0]["magnetic_dim"] == 4


# ---------------------------------------------------------------------------
# B: add a fake R=2 closed-walk W term
# ---------------------------------------------------------------------------

def test_redundant_fake_W_add_is_invisible():
    """Add M^{(0,0)} q̃[1] q[1] = X10[1] · X02[1] · X21[0] to the
    magnetic W. This is a valid closed walk of R = 2 / 3 + 2 / 3 + 4 / 3
    = 2, so P3, P5 still pass on the magnetic side. The fake F-relation
    it induces is, however, already implied by the original F-ideal —
    so the chiral-ring quotient at length 3 is unchanged.

    Pinned because:
      - It documents that the verifier does NOT alarm on every R=2
        closed-walk W addition — some are no-ops.
      - It pairs with the next test (test_non_redundant_fake_W_add)
        which uses a *different* fake term that IS caught, sharpening
        the boundary between redundant and non-redundant adds.
    """
    magnetic = _magnetic_add_term(("X10[1]", "X02[1]", "X21[0]"),
                                  label="fake_redundant")
    cert = evaluate_claim(_claim_with_magnetic(magnetic, label="B1"))
    bounded = _results_by_name(cert)["bounded chiral-ring consistency"]
    assert bounded.status == Status.CERTIFIED
    block = bounded.details["tested_blocks"][0]
    assert block["electric_dim"] == 10
    assert block["magnetic_dim"] == 10


def test_non_redundant_fake_W_add_caught_dim_e10_m7():
    """Add M^{(0,0)} q̃[1] q[2] = X10[2] · X02[1] · X21[0] to the
    magnetic W. Same closed-walk shape and R = 2 as the redundant
    case, but mixing different q̃ and q flavor indices — this F-relation
    is NOT already implied by the original symmetric coupling structure.
    The F-ideal expands, chiral ring shrinks, magnetic dim drops to 7.

    The contrast with the redundant case (test above) is the headline:
    the verifier catches non-redundant additions but not redundant ones,
    and the boundary tracks a specific algebraic structure of dP_0
    magnetic (M^{(a,a)} couples only to q̃[a] q[a] in the original W).
    """
    magnetic = _magnetic_add_term(("X10[2]", "X02[1]", "X21[0]"),
                                  label="fake_detected")
    cert = evaluate_claim(_claim_with_magnetic(magnetic, label="B2"))
    bounded = _results_by_name(cert)["bounded chiral-ring consistency"]
    assert bounded.status == Status.FAILED
    failed = bounded.details["failed_blocks"]
    assert len(failed) == 1
    assert failed[0]["electric_dim"] == 10
    assert failed[0]["magnetic_dim"] == 7


# ---------------------------------------------------------------------------
# C: overall W rescale / sign flip — provable blindspot
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scale,label", [
    (Fraction(2), "W_times_2"),
    (Fraction(-1), "W_sign_flip"),
    (Fraction(7, 3), "W_times_7_3"),
])
def test_overall_W_rescale_is_provable_blindspot(scale, label):
    """W → c · W for any c ≠ 0 leaves the F-ideal invariant
    (∂_X (cW) = c · ∂_X W; the ideal generated by {c · u_X} equals
    the ideal generated by {u_X}). The bounded chiral-ring check
    therefore MUST return CERTIFIED on this perturbation — this is
    not a fixture-specific accident, it is a mathematical property of
    the F-ideal as a linear span.

    Three rescale factors tested (positive, negative, fractional) to
    rule out any spurious sign or rationality edge case.
    """
    base = _full_magnetic()
    scaled_W = tuple(
        SuperpotentialTerm(factors=t.factors, coefficient=t.coefficient * scale)
        for t in base.superpotential_terms
    )
    magnetic = _magnetic_with_W(scaled_W, label=label)
    cert = evaluate_claim(_claim_with_magnetic(magnetic, label=label))
    bounded = _results_by_name(cert)["bounded chiral-ring consistency"]
    assert bounded.status == Status.CERTIFIED
    block = bounded.details["tested_blocks"][0]
    assert block["electric_dim"] == 10
    assert block["magnetic_dim"] == 10


# ---------------------------------------------------------------------------
# C': single-term coefficient change — *not* a provable blindspot
#    but happens to be invisible on dP_0 magnetic
# ---------------------------------------------------------------------------

def test_single_coefficient_change_invisible_on_dp0_specifically():
    """Multiply ONLY the coefficient of W[0] = M^{(0,0)} q̃[0] q[0] by 2
    (leaving the other 8 terms unchanged). The perturbed F-ideal is
    generated by 9 modified relations, only 3 of which involve W[0].

    Mathematically this could change the F-ideal in general — unlike
    overall rescaling, single-term coefficient changes don't preserve
    the ideal as a linear span. On dP_0 magnetic specifically, the
    "delta" between perturbed and original generators lies inside the
    original ideal, so the perturbed ideal equals the original ideal
    and the chiral ring is unchanged.

    Pinned dim 10 = 10 — but the docstring is explicit that this is a
    *fixture-specific algebraic coincidence*, not a generic verifier
    blindspot. Other quivers may detect single-coefficient changes.
    """
    base = _full_magnetic()
    new_terms = (
        SuperpotentialTerm(
            factors=base.superpotential_terms[0].factors,
            coefficient=base.superpotential_terms[0].coefficient * 2,
        ),
    ) + tuple(base.superpotential_terms[1:])
    magnetic = _magnetic_with_W(new_terms, label="W0_coef_2x")
    cert = evaluate_claim(_claim_with_magnetic(magnetic, label="Cp"))
    bounded = _results_by_name(cert)["bounded chiral-ring consistency"]
    assert bounded.status == Status.CERTIFIED
    block = bounded.details["tested_blocks"][0]
    assert block["electric_dim"] == 10
    assert block["magnetic_dim"] == 10


# ---------------------------------------------------------------------------
# D: R-charge perturbation — caught upstream, missed in length-only fallback
# ---------------------------------------------------------------------------

def _magnetic_with_q_r_charge(new_q_r: Fraction) -> Theory:
    """Build the magnetic theory but with all q[c] (X10[c]) R-charges
    set to `new_q_r`. Leaves q̃ and M R-charges untouched.

    Mathematical aside: dP_0 magnetic R-charges are uniquely determined
    by anomaly cancellation + W R = 2 (R(q) = R(q̃) = 1/3, R(M) = 4/3).
    ANY change to a single R-charge necessarily breaks at least one of
    those constraints simultaneously, so we expect mixed-anomaly
    cancellation OR W R-consistency (or both) to FAIL upstream.
    """
    base = _full_magnetic()
    new_fields = []
    for f in base.fields:
        if f.name.startswith("X10["):
            new_fields.append(
                Field(
                    name=f.name,
                    field_type=f.field_type,
                    gauge_reps=f.gauge_reps,
                    global_reps=f.global_reps,
                    u1_charges=f.u1_charges,
                    r_charge=new_q_r,
                    multiplicity=f.multiplicity,
                )
            )
        else:
            new_fields.append(f)
    return Theory(
        name="dP_0 magnetic (q R-charge perturbed)",
        gauge_nodes=base.gauge_nodes,
        fields=tuple(new_fields),
        superpotential_terms=base.superpotential_terms,
        global_symmetries=base.global_symmetries,
    )


def test_r_charge_reshuffle_blocked_by_upstream_in_r_graded_mode():
    """Set R(q) = 1/4 (rather than 1/3). This necessarily breaks
    BOTH the SU(N)² × U(1)_R mixed anomaly (because R(q) + R(q̃) = 2/3
    is required) AND W R-consistency (because R(W) = R(M) + R(q̃) +
    R(q) = 4/3 + 1/3 + 1/4 ≠ 2). Under require_r_graded=True the
    bounded chiral-ring check refuses to run, returning NOT_APPLICABLE
    with P4 listed as the blocker (the magnetic mixed anomaly check
    has FAILED).

    Documents the *layered defense*: anomaly + W-consistency are the
    upstream gate in r_graded mode; the chiral-ring layer doesn't
    need to detect this perturbation independently.
    """
    magnetic = _magnetic_with_q_r_charge(Fraction(1, 4))
    cert = evaluate_claim(_claim_with_magnetic(magnetic, label="D_rg"))
    by_name = _results_by_name(cert)

    # Upstream catches it.
    assert by_name["magnetic gauge-global mixed anomaly cancellation"].status == Status.FAILED
    assert by_name["magnetic superpotential consistency"].status == Status.FAILED

    # Bounded chiral-ring refuses to run.
    bounded = by_name["bounded chiral-ring consistency"]
    assert bounded.status == Status.NOT_APPLICABLE
    assert "P4" in bounded.details["r_graded_blocked_by"]


def test_r_charge_reshuffle_invisible_in_length_only_fallback():
    """Same R(q) = 1/4 perturbation, but require_r_graded=False so
    length-only fallback runs. The F-ideal is unchanged (it depends
    on W coefficients, not R-charges); cyclic-word block counts are
    unchanged; the bounded chiral-ring check CERTIFIES even though
    the magnetic theory is physically inconsistent (anomalous,
    W R ≠ 2).

    This is the REAL blindspot of bounded chiral-ring in length-only
    mode: it cannot see R-charge perturbations. Length-only fallback
    is therefore strictly weaker — its CERTIFIED verdict carries no
    R-symmetry / anomaly guarantee. Callers must keep
    require_r_graded=True for the full physical assertion, and the
    upstream P3/P4 obligations must CERTIFY for that to mean anything.
    """
    magnetic = _magnetic_with_q_r_charge(Fraction(1, 4))
    cert = evaluate_claim(
        _claim_with_magnetic(magnetic, require_r_graded=False, label="D_lo")
    )
    by_name = _results_by_name(cert)

    # Upstream still flags the physical problem.
    assert by_name["magnetic gauge-global mixed anomaly cancellation"].status == Status.FAILED
    assert by_name["magnetic superpotential consistency"].status == Status.FAILED

    # But bounded chiral-ring missed it.
    bounded = by_name["bounded chiral-ring consistency"]
    assert bounded.status == Status.CERTIFIED
    assert bounded.details["r_graded"] is False
    block = bounded.details["tested_blocks"][0]
    assert block["electric_dim"] == 10
    assert block["magnetic_dim"] == 10
