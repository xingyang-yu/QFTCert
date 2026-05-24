from dualitycert.core.status import Status
from dualitycert.qft.dualities import build_seiberg_sqcd_claim, evaluate_claim
from dualitycert.qft.susy import superpotential_R_charge_equals_2


def test_correct_sqcd_like_seiberg_example_passes_implemented_checks():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5)

    certificate = evaluate_claim(claim)

    assert certificate.overall_status == Status.CERTIFIED
    assert not certificate.failed_obligations
    assert any(
        result.name == "operator map Abelian charge matching"
        for result in certificate.passed_obligations
    )
    assert any(
        result.name == "operator map non-Abelian flavor matching"
        for result in certificate.passed_obligations
    )
    assert {result.name for result in certificate.not_implemented_obligations} == {
        "index matching",
        "deformation checks",
    }


def test_wrong_magnetic_gauge_group_fails_global_anomaly_matching():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5, magnetic_color_rank=3)

    certificate = evaluate_claim(claim)

    assert certificate.overall_status == Status.FAILED
    assert any(result.name == "global anomaly matching" for result in certificate.failed_obligations)


def test_wrong_r_charge_assignment_fails_superpotential_r_charge():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5, magnetic_meson_r_charge=1)

    result = superpotential_R_charge_equals_2(claim.magnetic_theory)

    assert result.status == Status.FAILED
    assert "R-charge" in result.message


def test_missing_meson_produces_clear_failed_obligation():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5, include_meson=False)

    certificate = evaluate_claim(claim)

    assert certificate.overall_status == Status.FAILED
    failed_messages = "\n".join(result.message for result in certificate.failed_obligations)
    assert "unknown field M" in failed_messages
