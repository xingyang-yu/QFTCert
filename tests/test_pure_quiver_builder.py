"""Tests for pure_quiver_builder: build_pure_quiver, arrow_names, dp0_superpotential."""

from __future__ import annotations

from fractions import Fraction

import pytest

from dualitycert.core.objects import SuperpotentialTerm, Theory
from dualitycert.core.status import Status
from dualitycert.groups.u1 import u1_r
from dualitycert.qft.anomalies import (
    gauge_anomaly_cancellation,
    gauge_global_mixed_anomaly_cancellation,
)
from dualitycert.qft.pure_quiver_builder import (
    arrow_names,
    build_pure_quiver,
    dp0_superpotential,
)


# ---------------------------------------------------------------------------
# Basic construction
# ---------------------------------------------------------------------------

def test_two_node_basic_construction():
    theory = build_pure_quiver(
        ranks=(3, 3),
        arrows={(0, 1): [Fraction(2, 3)], (1, 0): [Fraction(2, 3)]},
        u1_globals=(u1_r(),),
    )
    assert len(theory.gauge_nodes) == 2
    assert len(theory.fields) == 2
    assert {f.name for f in theory.fields} == {"X01[0]", "X10[0]"}


def test_builder_all_fields_multiplicity_one():
    theory = build_pure_quiver(
        ranks=(3, 3),
        arrows={(0, 1): [Fraction(2, 3), Fraction(2, 3), Fraction(2, 3)]},
    )
    assert all(f.multiplicity == 1 for f in theory.fields)
    assert len(theory.fields) == 3
    assert {f.name for f in theory.fields} == {"X01[0]", "X01[1]", "X01[2]"}


def test_multi_arrow_r_charges_assigned_per_copy():
    r_list = [Fraction(1, 3), Fraction(2, 3), Fraction(1)]
    theory = build_pure_quiver(ranks=(3, 3), arrows={(0, 1): r_list})
    by_name = {f.name: f for f in theory.fields}
    for k, r in enumerate(r_list):
        assert by_name[f"X01[{k}]"].r_charge == r


def test_adjoint_arrow_gets_adjoint_rep():
    theory = build_pure_quiver(ranks=(3,), arrows={(0, 0): [Fraction(2, 3)]})
    assert len(theory.fields) == 1
    phi = theory.fields[0]
    assert phi.name == "Phi0[0]"
    assert phi.gauge_reps[theory.gauge_nodes[0].label].name == "adjoint"


def test_bifundamental_gauge_reps():
    """Design doc §3.2 convention: source = antifund, target = fund.

    Arrow (i, j) → field has antifundamental at node i and fundamental at node j,
    matching the Jacobi-algebra / derived-category direction "antifund → fund."
    """
    theory = build_pure_quiver(ranks=(3, 5), arrows={(0, 1): [Fraction(2, 3)]})
    field = theory.fields[0]
    node0_label = theory.gauge_nodes[0].label  # source
    node1_label = theory.gauge_nodes[1].label  # target
    assert field.gauge_reps[node0_label].name == "antifundamental"
    assert field.gauge_reps[node1_label].name == "fundamental"


def test_custom_node_labels():
    theory = build_pure_quiver(
        ranks=(3, 3),
        arrows={(0, 1): [Fraction(2, 3)]},
        node_labels=("SU(3)_A", "SU(3)_B"),
    )
    labels = {node.label for node in theory.gauge_nodes}
    assert labels == {"SU(3)_A", "SU(3)_B"}
    field = theory.fields[0]
    assert "SU(3)_A" in field.gauge_reps
    assert "SU(3)_B" in field.gauge_reps


def test_default_node_labels_use_rank():
    theory = build_pure_quiver(ranks=(2, 5), arrows={(0, 1): [Fraction(1, 2)]})
    labels = [node.label for node in theory.gauge_nodes]
    assert labels == ["SU(2)_0", "SU(5)_1"]


def test_no_u1_globals_by_default():
    theory = build_pure_quiver(ranks=(3,), arrows={(0, 0): [Fraction(2, 3)]})
    assert theory.global_symmetries == ()


# ---------------------------------------------------------------------------
# Superpotential with rational coefficients
# ---------------------------------------------------------------------------

def test_superpotential_rational_coefficients():
    terms = (
        SuperpotentialTerm(
            factors=(("X01[0]", 1), ("X10[0]", 1)),
            coefficient=Fraction(1, 2),
        ),
        SuperpotentialTerm(
            factors=(("X01[0]", 1), ("X10[0]", 1)),
            coefficient=Fraction(-3, 4),
        ),
    )
    theory = build_pure_quiver(
        ranks=(3, 3),
        arrows={(0, 1): [Fraction(2, 3)], (1, 0): [Fraction(2, 3)]},
        superpotential=terms,
    )
    assert len(theory.superpotential_terms) == 2
    assert theory.superpotential_terms[0].coefficient == Fraction(1, 2)
    assert theory.superpotential_terms[1].coefficient == Fraction(-3, 4)


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

def test_build_raises_on_wrong_node_labels_length():
    with pytest.raises(ValueError, match="node_labels length"):
        build_pure_quiver(
            ranks=(3, 3),
            arrows={(0, 1): [Fraction(2, 3)]},
            node_labels=("A", "B", "C"),
        )


def test_build_raises_on_out_of_range_arrow():
    with pytest.raises(ValueError, match="out of range"):
        build_pure_quiver(
            ranks=(3, 3),
            arrows={(0, 5): [Fraction(2, 3)]},
        )


# ---------------------------------------------------------------------------
# arrow_names helper
# ---------------------------------------------------------------------------

def test_arrow_names_bifundamental():
    assert arrow_names(0, 1, 3) == ("X01[0]", "X01[1]", "X01[2]")


def test_arrow_names_adjoint():
    assert arrow_names(0, 0, 2) == ("Phi0[0]", "Phi0[1]")


def test_arrow_names_single():
    assert arrow_names(1, 2, 1) == ("X12[0]",)


# ---------------------------------------------------------------------------
# dp0_superpotential: ε_{abc} expansion
# ---------------------------------------------------------------------------

def test_dp0_superpotential_has_six_terms():
    w = dp0_superpotential(
        ("A0", "A1", "A2"),
        ("B0", "B1", "B2"),
        ("C0", "C1", "C2"),
    )
    assert len(w) == 6


def test_dp0_superpotential_coefficients_sum_to_zero():
    """ε has 3 positive and 3 negative terms."""
    w = dp0_superpotential(
        ("A0", "A1", "A2"),
        ("B0", "B1", "B2"),
        ("C0", "C1", "C2"),
    )
    assert sum(t.coefficient for t in w) == 0


def test_dp0_superpotential_all_unit_coefficients():
    w = dp0_superpotential(
        ("A0", "A1", "A2"),
        ("B0", "B1", "B2"),
        ("C0", "C1", "C2"),
    )
    for term in w:
        assert abs(term.coefficient) == 1


def test_dp0_superpotential_each_term_cubic():
    w = dp0_superpotential(
        ("A0", "A1", "A2"),
        ("B0", "B1", "B2"),
        ("C0", "C1", "C2"),
    )
    for term in w:
        assert len(term.field_names) == 3


def test_dp0_identity_permutation_positive():
    """ε_{012} = +1: term A0·B1·C2 has coefficient +1."""
    w = dp0_superpotential(
        ("A0", "A1", "A2"),
        ("B0", "B1", "B2"),
        ("C0", "C1", "C2"),
    )
    names_to_coeff = {term.field_names: term.coefficient for term in w}
    assert names_to_coeff[("A0", "B1", "C2")] == Fraction(1)


def test_dp0_transposition_negative():
    """ε_{021} = -1: term A0·B2·C1 has coefficient -1."""
    w = dp0_superpotential(
        ("A0", "A1", "A2"),
        ("B0", "B1", "B2"),
        ("C0", "C1", "C2"),
    )
    names_to_coeff = {term.field_names: term.coefficient for term in w}
    assert names_to_coeff[("A0", "B2", "C1")] == Fraction(-1)


def test_dp0_cyclic_positive():
    """ε_{120} = +1: term A1·B2·C0 has coefficient +1."""
    w = dp0_superpotential(
        ("A0", "A1", "A2"),
        ("B0", "B1", "B2"),
        ("C0", "C1", "C2"),
    )
    names_to_coeff = {term.field_names: term.coefficient for term in w}
    assert names_to_coeff[("A1", "B2", "C0")] == Fraction(1)


# ---------------------------------------------------------------------------
# dP_0 SU(3)^3 construction + anomaly verification
# ---------------------------------------------------------------------------

def _build_dp0_theory(N: int = 3, r_charge: Fraction = Fraction(2, 3)) -> Theory:
    """dP_0 toric phase: SU(N)^3, 3 bifundamentals per directed edge, W = ε·X·X·X."""
    r3 = [r_charge] * 3
    names_01 = arrow_names(0, 1, 3)
    names_12 = arrow_names(1, 2, 3)
    names_20 = arrow_names(2, 0, 3)
    w = dp0_superpotential(names_01, names_12, names_20)
    return build_pure_quiver(
        ranks=(N, N, N),
        arrows={(0, 1): r3, (1, 2): r3, (2, 0): r3},
        superpotential=w,
        u1_globals=(u1_r(),),
    )


def test_dp0_theory_field_count():
    assert len(_build_dp0_theory().fields) == 9  # 3 copies × 3 directed edges


def test_dp0_theory_all_fields_mult_one():
    assert all(f.multiplicity == 1 for f in _build_dp0_theory().fields)


def test_dp0_theory_superpotential_term_count():
    assert len(_build_dp0_theory().superpotential_terms) == 6


def test_dp0_cubic_gauge_anomaly_certified():
    result = gauge_anomaly_cancellation(_build_dp0_theory())
    assert result.status == Status.CERTIFIED, result.message


def test_dp0_mixed_gauge_r_anomaly_certified():
    result = gauge_global_mixed_anomaly_cancellation(_build_dp0_theory())
    assert result.status == Status.CERTIFIED, result.message


def test_dp0_mixed_anomaly_fails_wrong_r():
    result = gauge_global_mixed_anomaly_cancellation(
        _build_dp0_theory(r_charge=Fraction(1, 2))
    )
    assert result.status == Status.FAILED
