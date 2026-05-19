"""Theory-kind classification for QFTCert check dispatch.

Three disjoint kinds:
  pure_quiver           — K >= 1 gauge nodes, no non-Abelian flavor fundamentals
  flavored_single_gauge — K = 1, has SU(Nf) flavor fundamentals (SQCD / Kutasov)
  flavored_quiver       — K > 1 with non-Abelian flavor (not yet supported)
"""

from __future__ import annotations

from dualitycert.core.objects import CheckResult, DualityClaim, Theory
from dualitycert.core.status import Status

PURE_QUIVER = "pure_quiver"
FLAVORED_SINGLE_GAUGE = "flavored_single_gauge"
FLAVORED_QUIVER = "flavored_quiver"


def infer_theory_kind(theory: Theory) -> str:
    """Classify a single theory by its field content."""
    has_flavor = any(
        any(not rep.is_singlet for rep in f.global_reps.values())
        for f in theory.fields
    )
    if not has_flavor:
        return PURE_QUIVER
    if len(theory.gauge_nodes) == 1:
        return FLAVORED_SINGLE_GAUGE
    return FLAVORED_QUIVER


def infer_claim_theory_kind(claim: DualityClaim) -> str:
    """Classify a duality claim; metadata["theory_kind"] overrides field inference."""
    if "theory_kind" in claim.metadata:
        return claim.metadata["theory_kind"]
    el = infer_theory_kind(claim.electric_theory)
    mag = infer_theory_kind(claim.magnetic_theory)
    if el == FLAVORED_QUIVER or mag == FLAVORED_QUIVER:
        return FLAVORED_QUIVER
    if el == FLAVORED_SINGLE_GAUGE or mag == FLAVORED_SINGLE_GAUGE:
        return FLAVORED_SINGLE_GAUGE
    return PURE_QUIVER


def theory_kind_classification_check(claim: DualityClaim) -> CheckResult:
    """Validate theory kind and flag OUT_OF_SCOPE for flavored_quiver."""
    el = infer_theory_kind(claim.electric_theory)
    mag = infer_theory_kind(claim.magnetic_theory)
    inferred = (
        FLAVORED_QUIVER if (el == FLAVORED_QUIVER or mag == FLAVORED_QUIVER)
        else FLAVORED_SINGLE_GAUGE if (el == FLAVORED_SINGLE_GAUGE or mag == FLAVORED_SINGLE_GAUGE)
        else PURE_QUIVER
    )
    stated = claim.metadata.get("theory_kind")

    if stated is not None and stated != inferred:
        return CheckResult(
            status=Status.FAILED,
            message=(
                f"Metadata states theory_kind={stated!r} but field content implies {inferred!r}."
            ),
            details={"stated": stated, "inferred_from_fields": inferred},
        )

    effective = stated or inferred
    if effective == FLAVORED_QUIVER:
        return CheckResult(
            status=Status.NOT_APPLICABLE,
            message=(
                f"Theory kind {effective!r}: flavored quiver gauge theories are outside "
                "the current verifier scope. No physics obligations were run."
            ),
            details={"theory_kind": effective},
        )

    return CheckResult(
        status=Status.CERTIFIED,
        message=f"Theory kind {effective!r} is within verifier scope.",
        details={"theory_kind": effective},
    )
