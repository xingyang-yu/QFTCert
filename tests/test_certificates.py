import json

from dualitycert.core.status import Status
from dualitycert.qft.dualities import build_seiberg_sqcd_claim, evaluate_claim


def test_certificate_rendering_includes_limits_and_not_implemented_checks():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5)

    certificate = evaluate_claim(claim)
    text = certificate.render_text()

    assert certificate.overall_status == Status.CERTIFIED
    assert "not a proof of duality" in text
    assert "Outward status: PARTIAL_WITH_NOT_IMPLEMENTED_OBLIGATIONS" in text
    assert "operator map Abelian charge matching" in text
    assert "operator map non-Abelian flavor matching" in text
    assert "NOT_IMPLEMENTED" in text


def test_certificate_to_dict_has_stable_ai_tool_keys():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5)

    certificate = evaluate_claim(claim)
    data = certificate.to_dict()

    assert {
        "claim_id",
        "claim_name",
        "duality_profile",
        "theory_kind",
        "parameters",
        "outward_status",
        "internal_status",
        "assumptions",
        "conventions",
        "limitations",
        "generated_obligations",
        "passed_obligations",
        "failed_obligations",
        "not_implemented_obligations",
        "warnings",
        "failures",
        "detailed_tables",
    }.issubset(data)
    assert data["duality_profile"] == "seiberg_sqcd"
    assert data["theory_kind"] == "flavored_single_gauge"
    assert data["outward_status"] == "PARTIAL_WITH_NOT_IMPLEMENTED_OBLIGATIONS"
    assert any(
        item["status"] == "NOT_IMPLEMENTED"
        for item in data["not_implemented_obligations"]
    )
    json.dumps(data)


def test_failed_claim_has_failed_outward_status_in_json():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5, magnetic_color_rank=3)

    certificate = evaluate_claim(claim)
    data = json.loads(certificate.to_json())

    assert data["outward_status"] == "FAILED_IMPLEMENTED_OBLIGATIONS"
    assert data["failed_obligations"]
