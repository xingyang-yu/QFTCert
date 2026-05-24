"""Verify that Phase 1 anomaly obligations run correctly on pure_quiver claims.

Step 0 finding: applicable_kinds=None in CheckSpec already covers pure_quiver
(registry skips FLAVORED_QUIVER only). anomalies.py runners are K-agnostic.
No CheckSpec changes were needed; this file documents and pins that coverage.

Physics note on the design-doc toy fixture (Phi/X/Y, W=Tr(Phi X Y), all R=2/3):
That 2-node quiver is NOT ABJ-free under U(1)_R for any SU(N1) x SU(N2) with
N1, N2 >= 2.  At node 1: N1*r_Phi + (N2/2)*(r_X + r_Y - 2) = 0 and at node 2:
(N1/2)*(r_X + r_Y - 2) + N2 = 0.  With r_Phi + r_X + r_Y = 2 (W has R=2) these
give N1*r_Phi = N2^2/N1, which requires irrational or unphysical ranks for generic
R-charges.  The toy is therefore a structural test (require_r_graded=False) only.

For R-graded verification use the 3-node SU(N)^3 cyclic fixture below, which IS
ABJ-free with R = 2/3 (it is the minimal dP_0-like pure quiver).

Gauge group choice: SU(3), not SU(2).  SU(2) fundamentals are pseudoreal so the
"SU(2)^3 cubic anomaly" is degenerate (the standard perturbative SU(N)^3 with
N>=3 is the physically clean case; SU(2) has a separate Witten global anomaly
that this verifier does not implement).  SU(3) avoids that ambiguity for any
future reader.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from dualitycert.core.objects import DualityClaim, Field, SymmetryMap, Theory
from dualitycert.core.status import Status
from dualitycert.groups.su import antifundamental, fundamental, su
from dualitycert.groups.u1 import u1_r
from dualitycert.qft.anomalies import gauge_anomaly_cancellation
from dualitycert.qft.dualities import evaluate_claim


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _three_node_theory(r_charge: Fraction = Fraction(2, 3)) -> Theory:
    """3-node SU(3)^3 cyclic quiver with 3 bifundamentals per directed edge pair.

    Each directed edge carries ONE Field object with multiplicity = 3 (not three
    Field objects).  The mixed SU(3)^2 U(1)_R anomaly contribution from a single
    such Field at the gauge node where it carries a (anti)fundamental rep is:

        T(rep) * (r_charge - 1) * multiplicity * dim(spectator)

    where T(fund) = T(antifund) = 1/2, multiplicity = 3, and the only spectator
    factor for a bifundamental excluding the chosen node is the dim of its rep
    at the other node = 3.  So each Field contributes (1/2)(r-1)(3)(3).

    At every node, exactly two such Fields are incident (one outgoing fund, one
    incoming antifund), plus the gaugino with contribution dynkin_index(adj, SU(3)) = 3:

        node total = 2 * (1/2)(r-1)(3)(3) + 3 = 9(r-1) + 3

    Zero iff r = 2/3.  Concrete values:
      r = 2/3:  -3/2 + -3/2 + 3 =  0     (ABJ-free)
      r = 1/2:  -9/4 + -9/4 + 3 = -3/2   (fails as expected)

    Cubic SU(3)^3 cancels by fund/antifund symmetry for any R-charge.
    """
    node1 = su(3, label="SU(3)_1")
    node2 = su(3, label="SU(3)_2")
    node3 = su(3, label="SU(3)_3")
    ur = u1_r()
    return Theory(
        name="3-node SU(3)^3 cyclic",
        gauge_nodes=(node1, node2, node3),
        global_symmetries=(ur,),
        fields=(
            Field(
                name="X12",
                field_type="chiral multiplet",
                gauge_reps={node1.label: fundamental(), node2.label: antifundamental()},
                r_charge=r_charge,
                multiplicity=3,
            ),
            Field(
                name="X23",
                field_type="chiral multiplet",
                gauge_reps={node2.label: fundamental(), node3.label: antifundamental()},
                r_charge=r_charge,
                multiplicity=3,
            ),
            Field(
                name="X31",
                field_type="chiral multiplet",
                gauge_reps={node3.label: fundamental(), node1.label: antifundamental()},
                r_charge=r_charge,
                multiplicity=3,
            ),
        ),
    )


def _three_node_self_dual_claim(r_charge: Fraction = Fraction(2, 3)) -> DualityClaim:
    """Self-dual claim: electric == magnetic == 3-node SU(3)^3 cyclic quiver."""
    theory = _three_node_theory(r_charge)
    return DualityClaim(
        name="3-node cyclic self-dual",
        electric_theory=theory,
        magnetic_theory=theory,
        metadata={"theory_kind": "pure_quiver"},
    )


def _get_result(cert, obligation_name: str):
    """Extract a single obligation result by name; raise if not found."""
    matches = [r for r in cert.obligation_results if r.name == obligation_name]
    if not matches:
        available = [r.name for r in cert.obligation_results]
        raise KeyError(f"{obligation_name!r} not in results: {available}")
    return matches[0]


# ---------------------------------------------------------------------------
# Theory-kind classification
# ---------------------------------------------------------------------------

def test_three_node_quiver_classified_as_pure_quiver():
    cert = evaluate_claim(_three_node_self_dual_claim())
    result = _get_result(cert, "theory kind classification")
    assert result.status == Status.CERTIFIED
    assert result.details["theory_kind"] == "pure_quiver"


# ---------------------------------------------------------------------------
# Cubic gauge anomaly (SU(N)^3): already K-agnostic, fires for pure_quiver
# ---------------------------------------------------------------------------

def test_cubic_gauge_anomaly_fires_for_pure_quiver():
    cert = evaluate_claim(_three_node_self_dual_claim())
    obligation_names = {r.name for r in cert.obligation_results}
    assert "electric gauge anomaly cancellation" in obligation_names
    assert "magnetic gauge anomaly cancellation" in obligation_names


def test_cubic_gauge_anomaly_certified_for_three_node_cyclic():
    cert = evaluate_claim(_three_node_self_dual_claim())
    for side in ("electric", "magnetic"):
        result = _get_result(cert, f"{side} gauge anomaly cancellation")
        assert result.status == Status.CERTIFIED, (
            f"{side} cubic gauge anomaly not CERTIFIED: {result.message}"
        )


def test_cubic_gauge_anomaly_result_has_three_nodes():
    cert = evaluate_claim(_three_node_self_dual_claim())
    result = _get_result(cert, "electric gauge anomaly cancellation")
    assert len(result.details) == 3  # one entry per gauge node


# ---------------------------------------------------------------------------
# Mixed gauge-global anomaly SU(gauge)^2 U(1)_R
# ---------------------------------------------------------------------------

def test_mixed_anomaly_fires_for_pure_quiver_with_u1r():
    cert = evaluate_claim(_three_node_self_dual_claim())
    obligation_names = {r.name for r in cert.obligation_results}
    assert "electric gauge-global mixed anomaly cancellation" in obligation_names
    assert "magnetic gauge-global mixed anomaly cancellation" in obligation_names


def test_mixed_anomaly_certified_at_r_two_thirds():
    """R = 2/3 makes the 3-node SU(3)^3 ABJ-free: -3/2 - 3/2 + 3 = 0 per node."""
    cert = evaluate_claim(_three_node_self_dual_claim(r_charge=Fraction(2, 3)))
    for side in ("electric", "magnetic"):
        result = _get_result(cert, f"{side} gauge-global mixed anomaly cancellation")
        assert result.status == Status.CERTIFIED, (
            f"{side} mixed anomaly not CERTIFIED at R=2/3: {result.message}"
        )


def test_mixed_anomaly_fails_at_wrong_r_charge():
    """R = 1/2 gives -9/4 - 9/4 + 3 = -3/2 != 0 per node."""
    cert = evaluate_claim(_three_node_self_dual_claim(r_charge=Fraction(1, 2)))
    for side in ("electric", "magnetic"):
        result = _get_result(cert, f"{side} gauge-global mixed anomaly cancellation")
        assert result.status == Status.FAILED, (
            f"{side} mixed anomaly should FAIL at R=1/2 but got {result.status}"
        )


def test_mixed_anomaly_not_applicable_without_u1r():
    """Without a U(1)_R global symmetry object the check correctly returns NOT_APPLICABLE."""
    node1 = su(3, label="SU(3)_1")
    node2 = su(3, label="SU(3)_2")
    theory_no_u1 = Theory(
        name="2-node, no global symmetries",
        gauge_nodes=(node1, node2),
        fields=(
            Field(
                name="X",
                field_type="chiral multiplet",
                gauge_reps={node1.label: fundamental(), node2.label: antifundamental()},
                r_charge=Fraction(1, 2),
            ),
        ),
    )
    claim = DualityClaim(
        name="no-u1 pure quiver",
        electric_theory=theory_no_u1,
        magnetic_theory=theory_no_u1,
        metadata={"theory_kind": "pure_quiver"},
    )
    cert = evaluate_claim(claim)
    for side in ("electric", "magnetic"):
        result = _get_result(cert, f"{side} gauge-global mixed anomaly cancellation")
        assert result.status == Status.NOT_APPLICABLE


# ---------------------------------------------------------------------------
# Regression: multiplicity must not be double-counted in cubic gauge anomaly
# ---------------------------------------------------------------------------
# Bug pattern: gauge_anomaly_cancellation multiplied by field.multiplicity
# explicitly AND through _spectator_dimension (which already starts at
# field.multiplicity).  Symmetric fixtures still cancel to 0, so a zero/non-zero
# test misses it.  This test pins linear scaling of the per-field contribution.

def test_cubic_anomaly_multiplicity_scales_linearly():
    node = su(3, label="SU(3)")

    def _single_fund_theory(mult: int) -> Theory:
        return Theory(
            name=f"SU(3) with mult={mult} fund",
            gauge_nodes=(node,),
            fields=(
                Field(
                    name="F",
                    field_type="chiral multiplet",
                    gauge_reps={node.label: fundamental()},
                    r_charge=Fraction(2, 3),
                    multiplicity=mult,
                ),
            ),
        )

    c1 = gauge_anomaly_cancellation(_single_fund_theory(1)).details[node.label][
        "field_contributions"
    ]["F"]
    c3 = gauge_anomaly_cancellation(_single_fund_theory(3)).details[node.label][
        "field_contributions"
    ]["F"]
    assert c3 == 3 * c1, (
        f"cubic anomaly contribution must scale linearly with multiplicity; "
        f"got mult=1 -> {c1}, mult=3 -> {c3}, expected mult=3 -> {3 * c1}"
    )


# ---------------------------------------------------------------------------
# Confirm pure_quiver claims do NOT trigger SQCD/Kutasov-specific checks
# ---------------------------------------------------------------------------

def test_sqcd_specific_checks_not_applicable_for_pure_quiver():
    cert = evaluate_claim(_three_node_self_dual_claim())
    sqcd_names = {
        "SQCD magnetic meson F-term lifting",
        "SQCD one-flavor mass deformation",
        "SQCD mesonic flat-direction flow",
        "operator map non-Abelian flavor matching",
        "Kutasov meson tower completeness",
    }
    obligation_names = {r.name for r in cert.obligation_results}
    for name in sqcd_names:
        if name in obligation_names:
            result = _get_result(cert, name)
            assert result.status == Status.NOT_APPLICABLE, (
                f"Expected NOT_APPLICABLE for {name!r} on pure_quiver, got {result.status}"
            )
