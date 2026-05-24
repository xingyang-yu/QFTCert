"""Tests for Kutasov-Schwimmer duality support.

Design principle (same as test_round_trip.py): the verifier reports which
consistency conditions fail and what numerical evidence shows the failure.
Physics knowledge (correct magnetic rank is kNf-Nc) lives in the test, not
in the framework.

Coverage:
  1. Builder: correct R-charges, field content, superpotential structure.
  2. Verifier: passing claim passes; broken claim fails at anomaly matching.
  3. Round-trip: a deterministic agent that knows kNf-Nc can repair the claim.
  4. Registry dispatch: SQCD-only checks absent; Kutasov-specific check present.
  5. JSON loader: duality_profile=kutasov round-trips through build_claim_from_data.
  6. Superpotential checker: Tr(X^n) and M_j q Y^n qtilde are recognized as
     gauge invariant (tests the susy.py _contains_singlet extension).
"""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

import pytest

from dualitycert.core.certificates import OUTWARD_FAILED, OUTWARD_PASSED, OUTWARD_PARTIAL
from dualitycert.qft.claims import build_claim_from_data
from dualitycert.qft.dualities import evaluate_claim
from dualitycert.qft.kutasov import build_kutasov_claim


REPO_ROOT = Path(__file__).resolve().parents[1]
PASSING_STATUSES = {OUTWARD_PASSED, OUTWARD_PARTIAL}


def _load_claim_data(filename: str) -> dict:
    return json.loads((REPO_ROOT / "claims" / filename).read_text())


# ---------------------------------------------------------------------------
# Builder: field content and R-charges
# ---------------------------------------------------------------------------

def test_builder_electric_fields_nc3_nf5_k2():
    claim = build_kutasov_claim(Nc=3, Nf=5, k=2)
    el = claim.electric_theory.field_map()
    assert set(el) == {"Q", "Qtilde", "X"}
    # R(X) = 2/(k+1) = 2/3
    assert el["X"].r_charge == Fraction(2, 3)
    # R_el = 1 - 2*Nc/(Nf*(k+1)) = 1 - 6/15 = 3/5
    assert el["Q"].r_charge == Fraction(3, 5)
    assert el["Qtilde"].r_charge == Fraction(3, 5)


def test_builder_magnetic_fields_nc3_nf5_k2():
    claim = build_kutasov_claim(Nc=3, Nf=5, k=2)
    mag = claim.magnetic_theory.field_map()
    # q, qtilde, Y, M0, M1
    assert set(mag) == {"q", "qtilde", "Y", "M0", "M1"}
    assert mag["Y"].r_charge == Fraction(2, 3)
    # R_mag = 1 - 2*7/(5*3) = 1 - 14/15 = 1/15
    assert mag["q"].r_charge == Fraction(1, 15)
    # R(M0) = 2*R_el = 6/5
    assert mag["M0"].r_charge == Fraction(6, 5)
    # R(M1) = 2*R_el + R_X = 6/5 + 2/3 = 28/15
    assert mag["M1"].r_charge == Fraction(28, 15)


def test_builder_magnetic_rank():
    claim = build_kutasov_claim(Nc=3, Nf=5, k=2)
    assert claim.magnetic_theory.gauge_nodes[0].N == 7  # kNf - Nc = 10 - 3


def test_builder_magnetic_superpotential_terms_k2():
    claim = build_kutasov_claim(Nc=3, Nf=5, k=2)
    term_labels = {t.label for t in claim.magnetic_theory.superpotential_terms}
    assert "Tr(Y^3)" in term_labels
    # j=0: M0 q Y^1 qtilde
    assert "M0 q Y^1 qtilde" in term_labels
    # j=1: M1 q qtilde (Y^0 term)
    assert "M1 q qtilde" in term_labels


def test_builder_electric_superpotential_k2():
    claim = build_kutasov_claim(Nc=3, Nf=5, k=2)
    terms = claim.electric_theory.superpotential_terms
    assert len(terms) == 1
    assert terms[0].label == "Tr(X^3)"


def test_builder_operator_map_contains_meson_tower():
    claim = build_kutasov_claim(Nc=3, Nf=5, k=2)
    op = claim.operator_map
    assert op["Qtilde Q"] == "M0"
    assert op["Qtilde X Q"] == "M1"
    # Bare baryon maps are not included: correct Kutasov baryons are X-dressed.
    assert "Q^3" not in op


# ---------------------------------------------------------------------------
# Verifier: passing fixture
# ---------------------------------------------------------------------------

def test_correct_kutasov_claim_passes():
    claim = build_kutasov_claim(Nc=3, Nf=5, k=2)
    cert = evaluate_claim(claim)
    assert cert.outward_status in PASSING_STATUSES, (
        f"Expected passing status, got {cert.outward_status}. "
        f"Failures: {[r.name for r in cert.failed_obligations]}"
    )


def test_correct_kutasov_no_failed_obligations():
    claim = build_kutasov_claim(Nc=3, Nf=5, k=2)
    cert = evaluate_claim(claim)
    assert not cert.failed_obligations, (
        f"Unexpected failures: {[r.name for r in cert.failed_obligations]}"
    )


# ---------------------------------------------------------------------------
# Verifier: broken fixture (wrong magnetic rank)
# ---------------------------------------------------------------------------

def test_wrong_rank_kutasov_fails():
    claim = build_kutasov_claim(Nc=3, Nf=5, k=2, magnetic_color_rank=4)
    cert = evaluate_claim(claim)
    assert cert.outward_status == OUTWARD_FAILED


def test_wrong_rank_kutasov_fails_anomaly_matching():
    claim = build_kutasov_claim(Nc=3, Nf=5, k=2, magnetic_color_rank=4)
    cert = evaluate_claim(claim)
    failed_names = {r.name for r in cert.failed_obligations}
    assert "global anomaly matching" in failed_names


# ---------------------------------------------------------------------------
# Round-trip: deterministic agent repairs wrong rank
# ---------------------------------------------------------------------------

def test_round_trip_wrong_rank_with_kutasov_knowledge():
    """Agent that knows Kutasov rank = kNf-Nc can repair a wrong-rank claim."""
    data = _load_claim_data("kutasov_wrong_magnetic_rank_k2.json")
    claim = build_claim_from_data(data)
    cert = evaluate_claim(claim)

    assert cert.outward_status == OUTWARD_FAILED

    # Physics knowledge lives HERE: magnetic rank = kNf - Nc
    repaired = json.loads(json.dumps(data))
    Nc = data["parameters"]["Nc"]
    Nf = data["parameters"]["Nf"]
    k = data["parameters"]["k"]
    repaired.setdefault("magnetic", {})["rank"] = k * Nf - Nc

    repaired_cert = evaluate_claim(build_claim_from_data(repaired))
    assert repaired_cert.outward_status in PASSING_STATUSES
    assert not repaired_cert.failed_obligations


# ---------------------------------------------------------------------------
# Registry dispatch: SQCD-only checks absent for Kutasov
# ---------------------------------------------------------------------------

def test_sqcd_only_checks_not_in_kutasov_obligations():
    claim = build_kutasov_claim(Nc=3, Nf=5, k=2)
    cert = evaluate_claim(claim)
    obligation_names = {r.name for r in cert.obligation_results}
    sqcd_only = {
        "SQCD magnetic meson F-term lifting",
        "SQCD one-flavor mass deformation",
        "SQCD mesonic flat-direction flow",
        "operator map non-Abelian flavor matching",
    }
    for name in sqcd_only:
        assert name not in obligation_names, (
            f"SQCD-only check {name!r} should not run on Kutasov claims"
        )


def test_kutasov_specific_check_present_in_obligations():
    claim = build_kutasov_claim(Nc=3, Nf=5, k=2)
    cert = evaluate_claim(claim)
    obligation_names = {r.name for r in cert.obligation_results}
    assert "Kutasov meson tower completeness" in obligation_names


def test_kutasov_check_not_in_sqcd_obligations():
    from dualitycert.qft.dualities import build_seiberg_sqcd_claim
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5)
    cert = evaluate_claim(claim)
    obligation_names = {r.name for r in cert.obligation_results}
    assert "Kutasov meson tower completeness" not in obligation_names


# ---------------------------------------------------------------------------
# JSON loader
# ---------------------------------------------------------------------------

def test_json_loader_kutasov_passing_fixture():
    data = _load_claim_data("kutasov_Nc3_Nf5_k2.json")
    claim = build_claim_from_data(data)
    assert claim.metadata.get("duality_profile") == "kutasov"
    assert claim.magnetic_theory.gauge_nodes[0].N == 7
    cert = evaluate_claim(claim)
    assert cert.outward_status in PASSING_STATUSES


def test_json_loader_kutasov_wrong_rank_fixture():
    data = _load_claim_data("kutasov_wrong_magnetic_rank_k2.json")
    claim = build_claim_from_data(data)
    assert claim.magnetic_theory.gauge_nodes[0].N == 4
    cert = evaluate_claim(claim)
    assert cert.outward_status == OUTWARD_FAILED


# ---------------------------------------------------------------------------
# Superpotential gauge invariance (tests _contains_singlet extension)
# ---------------------------------------------------------------------------

def test_electric_superpotential_tr_x3_is_gauge_invariant():
    """Tr(X^3) must pass the gauge-invariance check (3 adjoints)."""
    from dualitycert.qft.susy import superpotential_invariance
    claim = build_kutasov_claim(Nc=3, Nf=5, k=2)
    result = superpotential_invariance(claim.electric_theory)
    assert result.passed, f"Electric W=Tr(X^3) failed invariance: {result.message}"


def test_magnetic_superpotential_all_terms_gauge_invariant():
    """All magnetic superpotential terms must pass gauge invariance."""
    from dualitycert.qft.susy import superpotential_invariance
    claim = build_kutasov_claim(Nc=3, Nf=5, k=2)
    result = superpotential_invariance(claim.magnetic_theory)
    assert result.passed, f"Magnetic W failed invariance: {result.message}"


def test_electric_superpotential_r_charge_2():
    """Tr(X^3) must have R-charge 2."""
    from dualitycert.qft.susy import superpotential_R_charge_equals_2
    claim = build_kutasov_claim(Nc=3, Nf=5, k=2)
    result = superpotential_R_charge_equals_2(claim.electric_theory)
    assert result.passed, f"Electric W R-charge check failed: {result.message}"


def test_magnetic_superpotential_r_charge_2():
    """All magnetic W terms must have R-charge 2."""
    from dualitycert.qft.susy import superpotential_R_charge_equals_2
    claim = build_kutasov_claim(Nc=3, Nf=5, k=2)
    result = superpotential_R_charge_equals_2(claim.magnetic_theory)
    assert result.passed, f"Magnetic W R-charge check failed: {result.message}"


# ---------------------------------------------------------------------------
# k=1 edge case (Kutasov with cubic electric superpotential and one meson)
# ---------------------------------------------------------------------------

def test_kutasov_k1_passes():
    """k=1: SU(Nc) + adj X, W=Tr(X^2). Magnetic rank = Nf-Nc."""
    # Nc=3, Nf=5, k=1: Nm = 1*5 - 3 = 2. Must be >= 2, exactly on boundary.
    claim = build_kutasov_claim(Nc=3, Nf=5, k=1)
    assert claim.magnetic_theory.gauge_nodes[0].N == 2
    mag = claim.magnetic_theory.field_map()
    assert "M0" in mag
    assert "M1" not in mag
    cert = evaluate_claim(claim)
    assert cert.outward_status in PASSING_STATUSES


def test_kutasov_k3_passes():
    """k=3: meson tower M0, M1, M2 and W_el = Tr(X^4)."""
    # Nc=2, Nf=5, k=3: Nm = 3*5 - 2 = 13
    claim = build_kutasov_claim(Nc=2, Nf=5, k=3)
    assert claim.magnetic_theory.gauge_nodes[0].N == 13
    mag = claim.magnetic_theory.field_map()
    assert set(mag) >= {"M0", "M1", "M2"}
    cert = evaluate_claim(claim)
    assert cert.outward_status in PASSING_STATUSES
