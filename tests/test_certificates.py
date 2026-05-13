from dualitycert.core.status import Status
from dualitycert.qft.dualities import build_seiberg_sqcd_claim, evaluate_claim


def test_certificate_rendering_includes_limits_and_not_implemented_checks():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5)

    certificate = evaluate_claim(claim)
    text = certificate.render_text()

    assert certificate.overall_status == Status.CERTIFIED
    assert "not a proof of duality" in text
    assert "CERTIFIED only means" in text
    assert "operator map consistency" in text
    assert "NOT_IMPLEMENTED" in text
