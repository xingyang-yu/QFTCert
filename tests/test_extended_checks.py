from dataclasses import replace

from dualitycert.core.status import Status
from dualitycert.qft.chiral_ring import sqcd_magnetic_meson_f_term_lifting_check
from dualitycert.qft.anomalies import gauge_global_mixed_anomaly_cancellation
from dualitycert.qft.deformations import (
    sqcd_mesonic_flat_direction_flow_check,
    sqcd_one_flavor_mass_deformation_check,
)
from dualitycert.qft.dualities import build_seiberg_sqcd_claim, evaluate_claim
from dualitycert.qft.rcharges import (
    central_charge_matching,
    operator_unitarity_bound_check,
)
from dualitycert.qft.scaffolds import chiral_ring_metadata_check


def test_gauge_global_mixed_anomalies_cancel_for_correct_sqcd():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5)

    electric = gauge_global_mixed_anomaly_cancellation(claim.electric_theory)
    magnetic = gauge_global_mixed_anomaly_cancellation(claim.magnetic_theory)

    assert electric.status == Status.CERTIFIED
    assert magnetic.status == Status.CERTIFIED
    # electric = SU(3), magnetic = SU(2) for Nc=3, Nf=5
    assert electric.details["SU(3)"]["totals"]["U(1)_R"] == 0
    assert magnetic.details["SU(2)"]["totals"]["U(1)_R"] == 0


def test_wrong_magnetic_rank_fails_mixed_gauge_r_anomaly():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5, magnetic_color_rank=3)

    result = gauge_global_mixed_anomaly_cancellation(claim.magnetic_theory)

    assert result.status == Status.FAILED
    # wrong rank = SU(3) on magnetic side
    assert result.details["SU(3)"]["totals"]["U(1)_R"] == 1


def test_encoded_r_symmetry_central_charges_match_for_correct_sqcd():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5)

    result = central_charge_matching(claim)

    assert result.status == Status.CERTIFIED
    assert result.details["electric"]["a"] == result.details["magnetic"]["a"]
    assert result.details["electric"]["c"] == result.details["magnetic"]["c"]


def test_encoded_r_symmetry_central_charges_fail_for_wrong_rank():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5, magnetic_color_rank=3)

    result = central_charge_matching(claim)

    assert result.status == Status.FAILED
    assert "TrR" in result.message


def test_operator_unitarity_bound_can_fail_from_encoded_metadata():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5)
    claim = replace(
        claim,
        metadata={
            **dict(claim.metadata),
            "operators": [{"name": "test_operator", "R": "1/2"}],
        },
    )

    result = operator_unitarity_bound_check(claim)

    assert result.status == Status.FAILED
    assert "test_operator" in result.message


def test_sqcd_mass_deformation_rank_flow_passes_and_fails():
    correct = build_seiberg_sqcd_claim(Nc=3, Nf=5)
    wrong_rank = build_seiberg_sqcd_claim(Nc=3, Nf=5, magnetic_color_rank=3)

    correct_result = sqcd_one_flavor_mass_deformation_check(correct)
    wrong_result = sqcd_one_flavor_mass_deformation_check(wrong_rank)

    assert correct_result.status == Status.CERTIFIED
    assert wrong_result.status == Status.FAILED
    assert "expected 1" in wrong_result.message


def test_sqcd_magnetic_meson_f_term_lifting_passes_for_standard_w():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5)

    result = sqcd_magnetic_meson_f_term_lifting_check(claim)

    assert result.status == Status.CERTIFIED
    assert result.details["has_required_consequence"] is True
    assert result.details["f_terms"]["M"] == ["q qtilde"]


def test_correct_rank_with_trivial_magnetic_superpotential_fails_f_term_checks():
    claim = build_seiberg_sqcd_claim(
        Nc=4,
        Nf=7,
        include_magnetic_superpotential=False,
    )

    certificate = evaluate_claim(claim)
    failed_names = {result.name for result in certificate.failed_obligations}

    assert certificate.overall_status == Status.FAILED
    assert "SQCD magnetic meson F-term lifting" in failed_names
    assert "SQCD one-flavor mass deformation" in failed_names
    assert "SQCD mesonic flat-direction flow" in failed_names
    assert any(
        "q qtilde is not constrained"
        in result.message
        for result in certificate.failed_obligations
    )


def test_sqcd_mesonic_flat_direction_flow_passes_and_fails():
    correct = build_seiberg_sqcd_claim(Nc=3, Nf=5)
    wrong_rank = build_seiberg_sqcd_claim(Nc=3, Nf=5, magnetic_color_rank=3)

    correct_result = sqcd_mesonic_flat_direction_flow_check(correct)
    wrong_result = sqcd_mesonic_flat_direction_flow_check(wrong_rank)

    assert correct_result.status == Status.CERTIFIED
    assert correct_result.details["flows"][0]["electric_target"] == {
        "gauge_rank": 2,
        "flavors": 4,
    }
    assert wrong_result.status == Status.FAILED
    assert "magnetic rank 3" in wrong_result.message


def test_metadata_scaffold_reports_unknown_when_data_missing():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5)

    result = chiral_ring_metadata_check(claim)

    assert result.status == Status.UNKNOWN
    assert "No chiral-ring metadata" in result.message


def test_metadata_scaffold_compares_encoded_data():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5)
    passing = replace(
        claim,
        metadata={
            **dict(claim.metadata),
            "chiral_ring": {
                "generators": {
                    "electric": ["M", "B", "Btilde"],
                    "magnetic": ["M", "B", "Btilde"],
                }
            },
        },
    )
    failing = replace(
        claim,
        metadata={
            **dict(claim.metadata),
            "chiral_ring": {
                "generators": {
                    "electric": ["M", "B", "Btilde"],
                    "magnetic": ["M"],
                }
            },
        },
    )

    assert chiral_ring_metadata_check(passing).status == Status.CERTIFIED
    assert chiral_ring_metadata_check(failing).status == Status.FAILED


def test_certificate_json_exposes_unknown_obligations():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5)

    data = evaluate_claim(claim).to_dict()

    assert data["unknown_obligations"]
    assert any(item["status"] == "UNKNOWN" for item in data["unknown_obligations"])
