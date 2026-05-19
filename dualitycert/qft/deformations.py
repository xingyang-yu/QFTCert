"""Deformation-flow consistency checks for SQCD-like claims."""

from __future__ import annotations

from dualitycert.core.objects import CheckResult, DualityClaim
from dualitycert.core.status import Status
from dualitycert.qft.chiral_ring import sqcd_magnetic_f_term_consequences


def sqcd_one_flavor_mass_deformation_check(claim: DualityClaim) -> CheckResult:
    """Check the rank arithmetic of one-flavor SQCD mass deformation.

    For Seiberg SQCD, adding a mass to one electric flavor flows

        SU(Nc) with Nf flavors -> SU(Nc) with Nf-1 flavors.

    On the magnetic side the corresponding linear meson term Higgses

        SU(Nf-Nc) -> SU(Nf-Nc-1) = SU((Nf-1)-Nc).

    This checker validates that the encoded F-terms can support the Higgsing
    response, then checks the rank arithmetic and records whether the lower
    endpoint is inside the current SU(N>=2) implementation.
    """

    if claim.metadata.get("duality_profile") != "seiberg_sqcd":
        return CheckResult(
            status=Status.NOT_APPLICABLE,
            message="One-flavor mass deformation checker is SQCD-specific.",
        )

    parameters = claim.metadata.get("parameters", {})
    try:
        nc = int(parameters["Nc"])
        nf = int(parameters["Nf"])
        magnetic_rank = int(parameters["magnetic_rank"])
    except (KeyError, TypeError, ValueError):
        return CheckResult(
            status=Status.UNKNOWN,
            message="SQCD metadata is missing Nc, Nf, or magnetic_rank.",
            details={"required": ["Nc", "Nf", "magnetic_rank"]},
        )

    electric_target = {"Nc": nc, "Nf": nf - 1}
    magnetic_target_rank_from_flow = magnetic_rank - 1
    expected_magnetic_target_rank = (nf - 1) - nc
    details = {
        "deformation": "one_flavor_mass",
        "electric_target": electric_target,
        "magnetic_target_rank_from_higgsing": magnetic_target_rank_from_flow,
        "expected_magnetic_target_rank": expected_magnetic_target_rank,
        "current_supported_endpoint": expected_magnetic_target_rank >= 2,
    }
    consequences = sqcd_magnetic_f_term_consequences(claim)
    details["required_f_term_consequence"] = {
        "meaning": "A linear electric mass m Q Qtilde maps to m M; dW/dM must contain q qtilde so q qtilde + m = 0 can trigger magnetic Higgsing.",
        "has_dW_dM_q_qtilde": consequences.has_dW_dM_q_qtilde,
        "missing_fields": list(consequences.missing_fields),
        "f_terms": consequences.f_terms,
    }

    if nf - 1 <= nc:
        return CheckResult(
            status=Status.NOT_APPLICABLE,
            message="One-flavor mass flow exits the supported Nf > Nc SQCD regime.",
            details=details,
        )

    if not consequences.has_meson_lifting_relation:
        return CheckResult(
            status=Status.FAILED,
            message=(
                "One-flavor mass deformation is not supported by the encoded "
                "magnetic F-terms: dW/dM does not contain q qtilde, so a "
                "linear m M deformation would not produce the expected "
                "q qtilde + m F-term for Higgsing."
            ),
            details=details,
        )

    if magnetic_target_rank_from_flow != expected_magnetic_target_rank:
        return CheckResult(
            status=Status.FAILED,
            message=(
                "One-flavor mass deformation rank flow is inconsistent: "
                f"magnetic Higgsing gives {magnetic_target_rank_from_flow}, "
                f"expected {expected_magnetic_target_rank}."
            ),
            details=details,
        )

    warnings = ()
    if expected_magnetic_target_rank < 2:
        warnings = (
            "The rank arithmetic matches, but the deformed endpoint has magnetic rank "
            "below the current SU(N>=2) implementation.",
        )
    return CheckResult(
        status=Status.CERTIFIED,
        message="One-flavor SQCD mass deformation rank flow is consistent.",
        details=details,
        warnings=warnings,
    )


def sqcd_mesonic_flat_direction_flow_check(claim: DualityClaim) -> CheckResult:
    """Check mesonic flat-direction rank flow for SQCD-like claims.

    On a mesonic branch with B=Btilde=0 and rank(M)=k, the electric theory
    flows schematically as

        SU(Nc), Nf flavors -> SU(Nc-k), Nf-k flavors.

    The magnetic F-terms from the encoded superpotential should make k
    magnetic flavors massive along a rank-k M background, leaving SU(Nf-Nc)
    with Nf-k flavors, which has the expected rank

        (Nf-k) - (Nc-k) = Nf - Nc.

    This is an arithmetic/field-content check of the encoded SQCD profile. It
    is not a proof of moduli-space equivalence.
    """

    if claim.metadata.get("duality_profile") != "seiberg_sqcd":
        return CheckResult(
            status=Status.NOT_APPLICABLE,
            message="Mesonic flat-direction flow checker is SQCD-specific.",
        )

    parameters = claim.metadata.get("parameters", {})
    try:
        nc = int(parameters["Nc"])
        nf = int(parameters["Nf"])
        magnetic_rank = int(parameters["magnetic_rank"])
    except (KeyError, TypeError, ValueError):
        return CheckResult(
            status=Status.UNKNOWN,
            message="SQCD metadata is missing Nc, Nf, or magnetic_rank.",
            details={"required": ["Nc", "Nf", "magnetic_rank"]},
        )

    requested = claim.metadata.get("flat_direction_ranks")
    if requested is None:
        rank_values = tuple(range(1, nc - 1))
    else:
        rank_values = tuple(int(value) for value in requested)

    if not rank_values:
        return CheckResult(
            status=Status.NOT_APPLICABLE,
            message=(
                "No mesonic flat-direction ranks remain inside the current "
                "SU(N>=2) endpoint implementation."
            ),
            details={"supported_rank_values": []},
        )

    flows = []
    failures: list[str] = []
    unsupported: list[int] = []
    for rank_m in rank_values:
        if rank_m < 1 or rank_m >= nc:
            failures.append(f"rank(M)={rank_m} is outside 1 <= k < Nc")
            continue
        electric_target_rank = nc - rank_m
        electric_target_flavors = nf - rank_m
        expected_magnetic_rank = electric_target_flavors - electric_target_rank
        supported_endpoint = electric_target_rank >= 2
        if not supported_endpoint:
            unsupported.append(rank_m)
        rank_matches = magnetic_rank == expected_magnetic_rank
        flows.append(
            {
                "rank_M": rank_m,
                "electric_target": {
                    "gauge_rank": electric_target_rank,
                    "flavors": electric_target_flavors,
                },
                "magnetic_target": {
                    "gauge_rank": magnetic_rank,
                    "flavors": nf - rank_m,
                },
                "expected_magnetic_rank": expected_magnetic_rank,
                "rank_matches": rank_matches,
                "current_supported_endpoint": supported_endpoint,
            }
        )
        if not rank_matches:
            failures.append(
                f"rank(M)={rank_m}: magnetic rank {magnetic_rank} does not equal "
                f"(Nf-k)-(Nc-k)={expected_magnetic_rank}"
            )

    details = {
        "flows": flows,
        "unsupported_endpoint_rank_values": unsupported,
        "not_implemented": [
            "full moduli-space isomorphism",
            "explicit F-term elimination along the branch",
            "confinement/instanton effects near boundary cases",
        ],
    }
    consequences = sqcd_magnetic_f_term_consequences(claim)
    details["required_f_term_consequence"] = {
        "meaning": "A rank-k M background should give q,qtilde a mass through dW/dq and dW/dqtilde terms involving M.",
        "has_dW_dq_M_qtilde": consequences.has_dW_dq_M_qtilde,
        "has_dW_dqtilde_M_q": consequences.has_dW_dqtilde_M_q,
        "missing_fields": list(consequences.missing_fields),
        "f_terms": consequences.f_terms,
    }

    if not consequences.has_flat_direction_mass_relations:
        failures.append(
            "encoded magnetic F-terms do not contain both dW/dq ~ M qtilde "
            "and dW/dqtilde ~ M q, so the expected magnetic flavor masses "
            "along the mesonic branch are not supported"
        )

    if failures:
        return CheckResult(
            status=Status.FAILED,
            message="SQCD mesonic flat-direction flow failed: " + "; ".join(failures),
            details=details,
        )

    warnings = ()
    if unsupported:
        warnings = (
            "Some rank(M) values exit the current SU(N>=2) endpoint implementation; "
            "their arithmetic is recorded but not recursively checked.",
        )
    return CheckResult(
        status=Status.CERTIFIED,
        message="SQCD mesonic flat-direction rank flow is consistent.",
        details=details,
        warnings=warnings,
    )
