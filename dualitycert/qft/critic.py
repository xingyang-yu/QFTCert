"""Critic reports and repair prompts derived from certificates."""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Mapping

from dualitycert.core.certificates import Certificate
from dualitycert.core.objects import DualityClaim


@dataclass(frozen=True)
class RepairHint:
    """A structured repair suggestion.

    `type` is a stable machine-readable key (e.g. "magnetic_rank_mismatch")
    that downstream consumers (tests, LLM repair agents) can match on without
    parsing the human-readable prose. `path` and `suggested_value` describe a
    minimal JSON edit when one applies. `human_text` is the same prose that
    `build_critic_report` and `build_repair_prompt` render to users/LLMs.
    """

    type: str
    human_text: str
    path: str | None = None
    suggested_value: Any = None
    details: Mapping[str, Any] = field(default_factory=dict)


def repair_hint_texts(hints: list[RepairHint]) -> list[str]:
    """Extract the human-readable prose from a list of structured hints."""

    return [hint.human_text for hint in hints]


def build_critic_report(claim: DualityClaim, certificate: Certificate) -> str:
    """Build a human-readable critic report from a checked claim."""

    lines = [
        "# QFTCert Critic Report",
        "",
        f"Claim: {claim.name}",
        f"Outward status: {certificate.outward_status}",
        "",
        "This report is generated from implemented consistency checks. It is not a proof of duality or IR equivalence.",
        "",
    ]
    if certificate.failed_obligations:
        lines.append("## Failed Implemented Obligations")
        lines.append("")
        for result in certificate.failed_obligations:
            lines.extend(
                [
                    f"- {result.name}",
                    f"  - Checker: {result.checker_name or 'unknown'}",
                    f"  - Message: {result.message}",
                ]
            )
        lines.append("")
    else:
        lines.extend(
            [
                "## Failed Implemented Obligations",
                "",
                "- None.",
                "",
            ]
        )

    lines.extend(["## Repair Hints", ""])
    hints = build_repair_hints(claim, certificate)
    if hints:
        lines.extend(f"- {hint.human_text}" for hint in hints)
    else:
        lines.append("- No implemented obligation failed. Do not read this as a proof; inspect NOT_IMPLEMENTED obligations before making stronger claims.")
    lines.append("")

    if certificate.passed_obligations:
        lines.extend(["## Passed Implemented Obligations", ""])
        lines.extend(f"- {result.name}" for result in certificate.passed_obligations)
        lines.append("")

    if certificate.not_implemented_obligations:
        lines.extend(["## Not Implemented Obligations", ""])
        for result in certificate.not_implemented_obligations:
            lines.append(f"- {result.name}: {result.message}")
        lines.append("")

    if certificate.unknown_obligations:
        lines.extend(["## Unknown / Missing-Data Obligations", ""])
        for result in certificate.unknown_obligations:
            lines.append(f"- {result.name}: {result.message}")
        lines.append("")

    lines.extend(["## Assumptions", ""])
    lines.extend(f"- {assumption}" for assumption in certificate.assumptions)
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {limitation}" for limitation in certificate.limitations)

    return "\n".join(lines)


def build_repair_prompt(claim: DualityClaim, certificate: Certificate) -> str:
    """Build a concise prompt for an LLM or human repair step."""

    hints = build_repair_hints(claim, certificate)
    failed = certificate.failed_obligations
    lines = [
        "You are repairing a QFTCert JSON claim.",
        "Use the stated conventions. Do not change unrelated fields.",
        "Return only corrected JSON, with no prose outside the JSON object.",
        "",
        f"Claim name: {claim.name}",
        f"Outward status: {certificate.outward_status}",
        "",
    ]

    if failed:
        lines.extend(["Failed implemented obligations:", ""])
        for index, result in enumerate(failed, start=1):
            lines.append(f"{index}. {result.name}")
            lines.append(f"   Message: {result.message}")
        lines.append("")
    else:
        lines.extend(
            [
                "No implemented obligation failed.",
                "If you revise the claim, preserve the stated conventions and do not infer a proof of duality.",
                "",
            ]
        )

    lines.extend(["Suggested minimal edits / checks:", ""])
    if hints:
        lines.extend(f"- {hint.human_text}" for hint in hints)
    else:
        lines.append("- No minimal repair is suggested because no implemented obligation failed.")

    lines.extend(
        [
            "",
            "Known unimplemented obligations to keep explicit:",
            *[
                f"- {result.name}"
                for result in certificate.not_implemented_obligations
            ],
            "",
            "Unknown or missing-data obligations to keep explicit:",
            *[
                f"- {result.name}"
                for result in certificate.unknown_obligations
            ],
        ]
    )
    return "\n".join(lines)


def build_repair_hints(claim: DualityClaim, certificate: Certificate) -> list[RepairHint]:
    """Generate conservative, claim-specific repair hints as structured objects.

    Each hint carries a stable `type` key and, when applicable, a JSON `path`
    plus `suggested_value` describing a minimal edit. The `human_text` field
    is the same prose previously returned as a bare string, so existing
    renderers (critic report, repair prompt) preserve their output.
    """

    params = dict(claim.metadata.get("parameters", {}))
    nc = params.get("Nc")
    nf = params.get("Nf")
    magnetic_rank = params.get("magnetic_rank", claim.magnetic_theory.gauge_group.N)
    expected_rank = params.get("expected_magnetic_rank")

    failed_text = "\n".join(result.message for result in certificate.failed_obligations)
    failed_names = {result.name for result in certificate.failed_obligations}

    hints: list[RepairHint] = []
    if expected_rank is not None and magnetic_rank != expected_rank:
        hints.append(
            RepairHint(
                type="magnetic_rank_mismatch",
                human_text=(
                    f"For this seiberg_sqcd profile, magnetic.rank should be "
                    f"Nf - Nc = {expected_rank}; the current magnetic.rank is "
                    f"{magnetic_rank}."
                ),
                path="magnetic.rank",
                suggested_value=int(expected_rank),
                details={"current": magnetic_rank, "expected_formula": "Nf - Nc"},
            )
        )

    if "unknown field M" in failed_text or "references unknown field M" in failed_text:
        hints.append(
            RepairHint(
                type="missing_meson",
                human_text=(
                    "The magnetic superpotential/operator map references M. "
                    "Set magnetic.include_meson to true, or remove/repair terms "
                    "that reference M."
                ),
                path="magnetic.include_meson",
                suggested_value=True,
            )
        )

    if "R-charge" in failed_text:
        hints.append(_r_charge_hint(nc, nf))

    if "U(1)_B" in failed_text:
        hints.append(_baryon_charge_hint(nf, expected_rank))

    if "operator map Abelian charge matching" in failed_names:
        hints.append(
            RepairHint(
                type="operator_map_abelian_mismatch",
                human_text=(
                    "For operator-map failures, compare Q Qtilde <-> M, "
                    "Q^Nc <-> q^Nmag, and Qtilde^Nc <-> qtilde^Nmag using "
                    "U(1)_B, U(1)_R, and the supported SQCD flavor-label convention."
                ),
            )
        )

    if "operator map non-Abelian flavor matching" in failed_names:
        hints.append(
            RepairHint(
                type="operator_map_flavor_label_mismatch",
                human_text=(
                    "For SQCD flavor-label failures, check that baryons use "
                    "the epsilon-tensor equivalence "
                    "Lambda^k F ~= Lambda^(N-k) anti-F and that Nmag equals "
                    "Nf - Nc."
                ),
            )
        )

    if "SQCD magnetic meson F-term lifting" in failed_names:
        hints.append(
            RepairHint(
                type="magnetic_meson_f_term_lifting",
                human_text=(
                    "Check the encoded magnetic F-terms: dW/dM should contain "
                    "q qtilde so the magnetic composite q qtilde is constrained "
                    "rather than an extra mesonic chiral-ring generator."
                ),
            )
        )

    if "SQCD one-flavor mass deformation" in failed_names:
        hints.append(
            RepairHint(
                type="sqcd_one_flavor_mass_deformation",
                human_text=(
                    "For one-flavor mass deformation, the encoded magnetic "
                    "F-terms should allow a linear m M deformation to produce "
                    "q qtilde + m = 0 and the expected magnetic Higgsing."
                ),
            )
        )

    if "SQCD mesonic flat-direction flow" in failed_names:
        hints.append(
            RepairHint(
                type="sqcd_mesonic_flat_direction",
                human_text=(
                    "For mesonic flat-direction flow, check that the encoded "
                    "magnetic F-terms give q and qtilde masses along a rank-M "
                    "background and that the rank arithmetic remains consistent."
                ),
            )
        )

    if "global anomaly matching" in failed_names and not hints:
        hints.append(
            RepairHint(
                type="global_anomaly_matching",
                human_text=(
                    "Inspect the proposed magnetic gauge rank, matter content, "
                    "and U(1)/R-charge assignments; global anomaly matching "
                    "failed under the stated symmetry map."
                ),
            )
        )

    return _dedupe_hints(hints)


def _r_charge_hint(nc: int | None, nf: int | None) -> RepairHint:
    if nc is None or nf is None:
        return RepairHint(
            type="r_charge_generic",
            human_text=(
                "Check superfield R-charges so every superpotential term has "
                "total R-charge 2."
            ),
        )
    rq = Fraction(nc, nf)
    rm = Fraction(2 * (nf - nc), nf)
    return RepairHint(
        type="r_charge_formula",
        human_text=(
            "For the default SQCD-like assignment, use "
            f"R(q)=R(qtilde)={_format_fraction(rq)} and "
            f"R(M)={_format_fraction(rm)}, so W = M q qtilde has R-charge 2."
        ),
        suggested_value={
            "magnetic.quark_R_override": _format_fraction(rq),
            "magnetic.meson_R_override": _format_fraction(rm),
        },
        details={"R_quark_formula": "Nc/Nf", "R_meson_formula": "2(Nf-Nc)/Nf"},
    )


def _baryon_charge_hint(
    nf: int | None,
    expected_rank: int | None,
) -> RepairHint:
    if nf is None or expected_rank is None:
        return RepairHint(
            type="baryon_charge_generic",
            human_text=(
                "Check U(1)_B charge assignments within the stated "
                "baryon-number convention."
            ),
        )
    return RepairHint(
        type="baryon_charge_convention",
        human_text=(
            "In the default baryon-number convention, use "
            f"B(q)=1/(Nf-Nc)=1/{expected_rank} and "
            f"B(qtilde)=-1/(Nf-Nc)=-1/{expected_rank}. "
            "A global baryon-number rescaling is not by itself a failure, but "
            "the electric and magnetic sides must use one consistent convention."
        ),
        suggested_value={
            "magnetic.charges.q_B_override": f"1/{expected_rank}",
            "magnetic.charges.qtilde_B_override": f"-1/{expected_rank}",
        },
    )


def _format_fraction(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def _dedupe_hints(hints: list[RepairHint]) -> list[RepairHint]:
    seen: set[tuple[str, str]] = set()
    deduped: list[RepairHint] = []
    for hint in hints:
        key = (hint.type, hint.human_text)
        if key not in seen:
            seen.add(key)
            deduped.append(hint)
    return deduped
