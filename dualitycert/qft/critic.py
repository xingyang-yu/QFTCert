"""Critic reports and inconsistency prompts derived from certificates.

Design principle: the verifier reports *which consistency conditions failed*
and *what numerical evidence shows the failure*. It does NOT report what the
correct answer would be for any duality-specific quantity (magnetic rank,
profile-specific R-charges, baryon convention, etc.). The agent reading the
output is responsible for physical reasoning about what to change.

The two emitters here (build_critic_report for humans, build_repair_prompt
for downstream tools) consume only ObligationResult.{name, description,
message, details}. Each failed obligation contributes:

  - name        e.g. "global anomaly matching"
  - description e.g. "Global 't Hooft anomaly tables must match under the
                symmetry map."  (the *universal* consistency principle)
  - message     diagnostic text with measured values
  - details     structured numerical evidence

If a check needs more universal-physics context than its current description
provides, the right fix is to expand that obligation's description, not to
add an answer-suggesting hint here.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from dualitycert.core.certificates import Certificate
from dualitycert.core.objects import DualityClaim
from dualitycert.core.obligations import ObligationResult


def build_critic_report(claim: DualityClaim, certificate: Certificate) -> str:
    """Build a human-readable critic report from a checked claim.

    Shows: failed obligations (with diagnostic detail), passed obligations,
    not-implemented obligations, assumptions, limitations.  No
    suggested-repair section: any "suggestion" would be answer leakage.
    """

    lines = [
        "# QFTCert Critic Report",
        "",
        f"Claim: {claim.name}",
        f"Outward status: {certificate.outward_status}",
        "",
        "This report lists the consistency conditions that were checked and "
        "which (if any) the claim fails to satisfy. It does not propose a "
        "correct answer; that is the proposer's responsibility. A PASS does "
        "not imply a proof of duality.",
        "",
    ]

    lines.extend(["## Failed Consistency Conditions", ""])
    if certificate.failed_obligations:
        for result in certificate.failed_obligations:
            lines.extend(_render_failure_block(result))
    else:
        lines.append("- None.")
        lines.append("")

    if certificate.passed_obligations:
        lines.extend(["## Passed Consistency Conditions", ""])
        lines.extend(f"- {result.name}" for result in certificate.passed_obligations)
        lines.append("")

    if certificate.not_implemented_obligations:
        lines.extend(["## Not-Implemented Consistency Conditions", ""])
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
    """Build the inconsistency report for a downstream repair step.

    Contains ONLY:
      - which consistency conditions failed (obligation name + description)
      - the diagnostic message with measured evidence
      - structured details (raw numerical data)
      - which obligations are NOT_IMPLEMENTED (so the proposer knows the scope)

    Does NOT contain:
      - suggested values
      - profile-specific formulas
      - any statement of the form "the correct X is Y"

    The proposer must reason from the diagnostic to a fix.
    """

    failed = certificate.failed_obligations
    lines = [
        f"Claim name: {claim.name}",
        f"Outward status: {certificate.outward_status}",
        "",
    ]

    if failed:
        lines.extend(["Failed consistency conditions:", ""])
        for index, result in enumerate(failed, start=1):
            lines.append(f"{index}. {result.name}")
            lines.append(f"   Condition: {result.description}")
            lines.append(f"   Diagnostic: {result.message}")
            evidence = _render_details_compact(result.details)
            if evidence:
                lines.append(f"   Evidence: {evidence}")
            lines.append("")
    else:
        lines.append("No implemented consistency condition failed.")
        lines.append("")

    if certificate.not_implemented_obligations:
        lines.append("Out-of-scope (not checked by this verifier):")
        lines.extend(
            f"- {result.name}"
            for result in certificate.not_implemented_obligations
        )
        lines.append("")

    if certificate.unknown_obligations:
        lines.append("Could not evaluate (missing data):")
        lines.extend(
            f"- {result.name}: {result.message}"
            for result in certificate.unknown_obligations
        )

    return "\n".join(lines).rstrip()


# ---------------------------------------------------------------------------
# Internal rendering helpers
# ---------------------------------------------------------------------------


def _render_failure_block(result: ObligationResult) -> list[str]:
    block = [
        f"### {result.name}",
        "",
        f"- Consistency condition: {result.description}",
        f"- Diagnostic: {result.message}",
    ]
    evidence = _render_details_compact(result.details)
    if evidence:
        block.append(f"- Evidence: {evidence}")
    block.append("")
    return block


def _render_details_compact(details: Mapping[str, Any]) -> str:
    """One-line JSON-ish rendering of measured evidence; '' if no data."""

    if not details:
        return ""
    try:
        return json.dumps(details, default=str, separators=(", ", ": "))
    except (TypeError, ValueError):
        return str(details)
