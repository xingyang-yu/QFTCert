"""Tests for theory-kind classification and OUT_OF_SCOPE dispatch (Phase 1.6)."""

from __future__ import annotations

from fractions import Fraction

import pytest

from dualitycert.core.certificates import OUTWARD_OUT_OF_SCOPE
from dualitycert.core.objects import (
    DualityClaim,
    Field,
    SymmetryMap,
    Theory,
)
from dualitycert.core.theory_kind import (
    FLAVORED_QUIVER,
    FLAVORED_SINGLE_GAUGE,
    PURE_QUIVER,
    infer_claim_theory_kind,
    infer_theory_kind,
)
from dualitycert.groups.su import antifundamental, fundamental, su
from dualitycert.groups.u1 import u1, u1_r
from dualitycert.qft.dualities import build_seiberg_sqcd_claim, evaluate_claim
from dualitycert.qft.kutasov import build_kutasov_claim


# ---------------------------------------------------------------------------
# infer_theory_kind: single-theory classification
# ---------------------------------------------------------------------------

def _pure_quiver_theory() -> Theory:
    """Two SU(2) nodes with one bifundamental — no global_reps."""
    node1 = su(2, label="SU(2)_1")
    node2 = su(2, label="SU(2)_2")
    return Theory(
        name="Pure 2-node quiver",
        gauge_nodes=(node1, node2),
        fields=(
            Field(
                name="X12",
                field_type="chiral multiplet",
                gauge_reps={
                    node1.label: fundamental(),
                    node2.label: antifundamental(),
                },
                r_charge=Fraction(1, 2),
            ),
        ),
    )


def _flavored_single_gauge_theory() -> Theory:
    """SU(3) with flavor fundamentals — K=1."""
    node = su(3)
    flavor = su(5, label="SU(5)_F", global_symmetry=True)
    return Theory(
        name="Flavored SU(3)",
        gauge_nodes=(node,),
        global_symmetries=(flavor,),
        fields=(
            Field(
                name="Q",
                field_type="chiral multiplet",
                gauge_reps={node.label: fundamental()},
                global_reps={"SU(5)_F": fundamental()},
                r_charge=Fraction(2, 5),
            ),
        ),
    )


def _flavored_quiver_theory() -> Theory:
    """Two SU(2) nodes with a bifundamental AND a flavored fundamental."""
    node1 = su(2, label="SU(2)_1")
    node2 = su(2, label="SU(2)_2")
    flavor = su(3, label="SU(3)_F", global_symmetry=True)
    return Theory(
        name="Flavored 2-node quiver",
        gauge_nodes=(node1, node2),
        global_symmetries=(flavor,),
        fields=(
            Field(
                name="X12",
                field_type="chiral multiplet",
                gauge_reps={
                    node1.label: fundamental(),
                    node2.label: antifundamental(),
                },
                r_charge=Fraction(1, 2),
            ),
            Field(
                name="Q1",
                field_type="chiral multiplet",
                gauge_reps={node1.label: fundamental()},
                global_reps={"SU(3)_F": fundamental()},
                r_charge=Fraction(1, 3),
            ),
        ),
    )


def test_pure_quiver_has_no_flavor():
    assert infer_theory_kind(_pure_quiver_theory()) == PURE_QUIVER


def test_flavored_single_gauge_classified_correctly():
    assert infer_theory_kind(_flavored_single_gauge_theory()) == FLAVORED_SINGLE_GAUGE


def test_flavored_quiver_classified_correctly():
    assert infer_theory_kind(_flavored_quiver_theory()) == FLAVORED_QUIVER


def test_single_node_no_flavor_is_pure_quiver():
    node = su(3)
    theory = Theory(
        name="Pure SU(3)",
        gauge_nodes=(node,),
        fields=(
            Field(
                name="X",
                field_type="chiral multiplet",
                gauge_reps={node.label: "adjoint"},
                r_charge=Fraction(2, 3),
            ),
        ),
    )
    assert infer_theory_kind(theory) == PURE_QUIVER


# ---------------------------------------------------------------------------
# infer_claim_theory_kind
# ---------------------------------------------------------------------------

def test_sqcd_claim_is_flavored_single_gauge():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5)
    assert infer_claim_theory_kind(claim) == FLAVORED_SINGLE_GAUGE


def test_kutasov_claim_is_flavored_single_gauge():
    claim = build_kutasov_claim(Nc=3, Nf=5, k=2)
    assert infer_claim_theory_kind(claim) == FLAVORED_SINGLE_GAUGE


def _make_flavored_quiver_claim() -> DualityClaim:
    el = _flavored_quiver_theory()
    mag = _pure_quiver_theory()
    return DualityClaim(
        name="Test flavored quiver claim",
        electric_theory=el,
        magnetic_theory=mag,
    )


def test_flavored_quiver_claim_inferred():
    claim = _make_flavored_quiver_claim()
    assert infer_claim_theory_kind(claim) == FLAVORED_QUIVER


def test_metadata_override_respected():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5)
    from dataclasses import replace
    claim = replace(claim, metadata={**dict(claim.metadata), "theory_kind": PURE_QUIVER})
    assert infer_claim_theory_kind(claim) == PURE_QUIVER


# ---------------------------------------------------------------------------
# theory_kind_classification_check (via evaluate_claim)
# ---------------------------------------------------------------------------

def test_sqcd_classification_check_passes():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5)
    cert = evaluate_claim(claim)
    classification = next(
        r for r in cert.obligation_results if r.name == "theory kind classification"
    )
    assert classification.status.value == "CERTIFIED"
    assert classification.details["theory_kind"] == FLAVORED_SINGLE_GAUGE


def test_flavored_quiver_claim_is_out_of_scope():
    claim = _make_flavored_quiver_claim()
    cert = evaluate_claim(claim)
    assert cert.outward_status == OUTWARD_OUT_OF_SCOPE


def test_flavored_quiver_has_no_failed_obligations():
    claim = _make_flavored_quiver_claim()
    cert = evaluate_claim(claim)
    assert not cert.failed_obligations


def test_flavored_quiver_only_runs_classification_check():
    claim = _make_flavored_quiver_claim()
    cert = evaluate_claim(claim)
    names = {r.name for r in cert.obligation_results}
    assert names == {"theory kind classification"}


def test_metadata_kind_disagreement_fails_classification():
    from dataclasses import replace
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5)
    claim = replace(
        claim,
        metadata={**dict(claim.metadata), "theory_kind": PURE_QUIVER},
    )
    cert = evaluate_claim(claim)
    classification = next(
        r for r in cert.obligation_results if r.name == "theory kind classification"
    )
    assert classification.status.value == "FAILED"
    assert "pure_quiver" in classification.message


# ---------------------------------------------------------------------------
# duality_profile in Certificate
# ---------------------------------------------------------------------------

def test_sqcd_certificate_has_duality_profile():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5)
    cert = evaluate_claim(claim)
    assert cert.duality_profile == "seiberg_sqcd"


def test_kutasov_certificate_has_duality_profile():
    claim = build_kutasov_claim(Nc=3, Nf=5, k=2)
    cert = evaluate_claim(claim)
    assert cert.duality_profile == "kutasov"


def test_certificate_to_dict_has_duality_profile_and_theory_kind():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5)
    data = evaluate_claim(claim).to_dict()
    assert "duality_profile" in data
    assert "theory_kind" in data
    assert "claim_type" not in data
    assert data["duality_profile"] == "seiberg_sqcd"
    assert data["theory_kind"] == FLAVORED_SINGLE_GAUGE
