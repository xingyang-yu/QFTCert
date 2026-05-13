"""Certificate assembly and rendering."""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Iterable, Mapping

from dualitycert.core.obligations import ObligationResult
from dualitycert.core.status import Status


DEFAULT_ASSUMPTIONS = (
    "Only implemented exact consistency checks are certified.",
    "Chiral multiplet fermions have R-charge R_superfield - 1.",
    "SU(N)^3 anomaly normalization uses A(fundamental)=+1 and A(antifundamental)=-1.",
    "SU(N)^2 U(1) normalization uses T(fundamental)=T(antifundamental)=1/2.",
)

DEFAULT_LIMITATIONS = (
    "This is not a proof of duality.",
    "Operator maps, index matching, and deformation checks are recorded but not implemented.",
    "The superpotential invariant checker is SQCD-like, not a general invariant-theory engine.",
)


@dataclass(frozen=True)
class Certificate:
    claim_name: str
    overall_status: Status
    passed_obligations: tuple[ObligationResult, ...] = ()
    failed_obligations: tuple[ObligationResult, ...] = ()
    not_implemented_obligations: tuple[ObligationResult, ...] = ()
    warnings: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = DEFAULT_ASSUMPTIONS
    limitations: tuple[str, ...] = DEFAULT_LIMITATIONS
    detailed_tables: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_results(
        cls,
        claim_name: str,
        results: Iterable[ObligationResult],
        *,
        assumptions: tuple[str, ...] = DEFAULT_ASSUMPTIONS,
        limitations: tuple[str, ...] = DEFAULT_LIMITATIONS,
    ) -> "Certificate":
        result_tuple = tuple(results)
        passed = tuple(result for result in result_tuple if result.status == Status.CERTIFIED)
        failed = tuple(result for result in result_tuple if result.status == Status.FAILED)
        not_implemented = tuple(
            result for result in result_tuple if result.status == Status.NOT_IMPLEMENTED
        )
        warnings: list[str] = []
        detailed_tables: dict[str, Any] = {}
        for result in result_tuple:
            warnings.extend(result.warnings)
            if result.details:
                detailed_tables[result.name] = result.details

        if failed:
            overall = Status.FAILED
        elif passed:
            overall = Status.CERTIFIED
        else:
            overall = Status.NOT_IMPLEMENTED

        return cls(
            claim_name=claim_name,
            overall_status=overall,
            passed_obligations=passed,
            failed_obligations=failed,
            not_implemented_obligations=not_implemented,
            warnings=tuple(warnings),
            assumptions=assumptions,
            limitations=limitations,
            detailed_tables=detailed_tables,
        )

    def render_text(self) -> str:
        lines = [
            f"Certificate for: {self.claim_name}",
            f"Overall status: {self.overall_status.value}",
            "",
            "Meaning: CERTIFIED only means the implemented exact checks passed.",
        ]
        if self.passed_obligations:
            lines.extend(["", "Passed obligations:"])
            lines.extend(
                f"  - {result.name}: {result.message}"
                for result in self.passed_obligations
            )
        if self.failed_obligations:
            lines.extend(["", "Failed obligations:"])
            lines.extend(
                f"  - {result.name}: {result.message}"
                for result in self.failed_obligations
            )
        if self.not_implemented_obligations:
            lines.extend(["", "Not implemented obligations (NOT_IMPLEMENTED):"])
            lines.extend(
                f"  - {result.name}: {result.message}"
                for result in self.not_implemented_obligations
            )
        if self.warnings:
            lines.extend(["", "Warnings:"])
            lines.extend(f"  - {warning}" for warning in self.warnings)
        lines.extend(["", "Assumptions:"])
        lines.extend(f"  - {assumption}" for assumption in self.assumptions)
        lines.extend(["", "Limitations:"])
        lines.extend(f"  - {limitation}" for limitation in self.limitations)

        anomaly_details = self.detailed_tables.get("global anomaly matching")
        if anomaly_details and "mismatches" in anomaly_details:
            mismatches = anomaly_details["mismatches"]
            if mismatches:
                lines.extend(["", "Anomaly mismatches:"])
                for mismatch in mismatches:
                    lines.append(
                        "  - "
                        f"{mismatch['key']}: electric={_format_value(mismatch['electric'])}, "
                        f"magnetic={_format_value(mismatch['magnetic'])}"
                    )

        return "\n".join(lines)

    def __str__(self) -> str:
        return self.render_text()


def _format_value(value: Any) -> str:
    if isinstance(value, Fraction):
        return _format_fraction(value)
    return str(value)


def _format_fraction(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"
