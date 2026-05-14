"""Critic reports and repair prompts derived from certificates."""

from __future__ import annotations

from fractions import Fraction

from dualitycert.core.certificates import Certificate
from dualitycert.core.objects import DualityClaim


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
        lines.extend(f"- {hint}" for hint in hints)
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
        lines.extend(f"- {hint}" for hint in hints)
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
        ]
    )
    return "\n".join(lines)


def build_repair_hints(claim: DualityClaim, certificate: Certificate) -> list[str]:
    """Generate conservative, claim-specific repair hints."""

    params = dict(claim.metadata.get("parameters", {}))
    nc = params.get("Nc")
    nf = params.get("Nf")
    magnetic_rank = params.get("magnetic_rank", claim.magnetic_theory.gauge_group.N)
    expected_rank = params.get("expected_magnetic_rank")

    failed_text = "\n".join(result.message for result in certificate.failed_obligations)
    failed_names = {result.name for result in certificate.failed_obligations}

    hints: list[str] = []
    if expected_rank is not None and magnetic_rank != expected_rank:
        hints.append(
            f"For this seiberg_sqcd profile, magnetic.rank should be Nf - Nc = {expected_rank}; the current magnetic.rank is {magnetic_rank}."
        )

    if "unknown field M" in failed_text or "references unknown field M" in failed_text:
        hints.append(
            "The magnetic superpotential/operator map references M. Set magnetic.include_meson to true, or remove/repair terms that reference M."
        )

    if "R-charge" in failed_text:
        r_hints = _r_charge_hints(nc, nf)
        if r_hints:
            hints.append(r_hints)

    if "U(1)_B" in failed_text:
        baryon_hint = _baryon_charge_hint(nf, expected_rank)
        if baryon_hint:
            hints.append(baryon_hint)

    if "operator map Abelian charge matching" in failed_names:
        hints.append(
            "For operator-map failures, compare Q Qtilde <-> M, Q^Nc <-> q^Nmag, and Qtilde^Nc <-> qtilde^Nmag using U(1)_B and U(1)_R charges only; non-Abelian flavor matching remains NOT_IMPLEMENTED."
        )

    if "global anomaly matching" in failed_names and not hints:
        hints.append(
            "Inspect the proposed magnetic gauge rank, matter content, and U(1)/R-charge assignments; global anomaly matching failed under the stated symmetry map."
        )

    return _dedupe(hints)


def _r_charge_hints(nc: int | None, nf: int | None) -> str | None:
    if nc is None or nf is None:
        return "Check superfield R-charges so every superpotential term has total R-charge 2."
    rq = Fraction(nc, nf)
    rm = Fraction(2 * (nf - nc), nf)
    return (
        "For the default SQCD-like assignment, use "
        f"R(q)=R(qtilde)={_format_fraction(rq)} and "
        f"R(M)={_format_fraction(rm)}, so W = M q qtilde has R-charge 2."
    )


def _baryon_charge_hint(nf: int | None, expected_rank: int | None) -> str | None:
    if nf is None or expected_rank is None:
        return "Check U(1)_B charge assignments within the stated baryon-number convention."
    return (
        "In the default baryon-number convention, use "
        f"B(q)=1/(Nf-Nc)=1/{expected_rank} and "
        f"B(qtilde)=-1/(Nf-Nc)=-1/{expected_rank}. "
        "A global baryon-number rescaling is not by itself a failure, but the electric and magnetic sides must use one consistent convention."
    )


def _format_fraction(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    deduped = []
    for item in items:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped
