"""Certificate assembly and rendering."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Iterable, Mapping

from dualitycert.core.obligations import ObligationResult
from dualitycert.core.status import Status


DEFAULT_ASSUMPTIONS = (
    "Only implemented exact consistency checks are reported as passing.",
    "Chiral multiplet fermions have R-charge R_superfield - 1.",
    "SU(N)^3 anomaly normalization uses A(fundamental)=+1 and A(antifundamental)=-1.",
    "SU(N)^2 U(1) normalization uses T(fundamental)=T(antifundamental)=1/2.",
)

DEFAULT_LIMITATIONS = (
    "This is not a proof of duality.",
    "Operator-map checks cover Abelian charges and standard SQCD flavor labels; general tensor-product decomposition, index matching, and general deformation checks are not implemented.",
    "Only a narrow SQCD F-term meson-lifting consequence is implemented; general chiral-ring, moduli-space, conformal-manifold, generalized-symmetry, and protected-quantity checks are metadata scaffolds unless explicit comparable data is encoded.",
    "Central charges are computed from the encoded R-symmetry; full a-maximization and accidental-symmetry handling are not implemented.",
    "The superpotential invariant checker is SQCD-like, not a general invariant-theory engine.",
)

DEFAULT_CONVENTIONS = {
    "fermions": "left-handed Weyl",
    "chiral_multiplet_fermion_R_charge": "R_superfield - 1",
    "SU_N_cubic_anomaly": "A(fundamental)=+1, A(antifundamental)=-1",
    "SU_N_squared_U1_dynkin_index": "T(fundamental)=T(antifundamental)=1/2",
    "baryon_number": "B(Q)=1/Nc on the electric side; the magnetic baryon normalization is taken from the claim and the verifier does not assume a specific dual-rank formula",
}

OUTWARD_PASSED = "PASSED_IMPLEMENTED_OBLIGATIONS"
OUTWARD_FAILED = "FAILED_IMPLEMENTED_OBLIGATIONS"
OUTWARD_NONE = "NO_IMPLEMENTED_OBLIGATIONS"
OUTWARD_PARTIAL = "PARTIAL_WITH_NOT_IMPLEMENTED_OBLIGATIONS"
OUTWARD_OUT_OF_SCOPE = "OUT_OF_SCOPE"


@dataclass(frozen=True)
class Certificate:
    claim_name: str
    overall_status: Status
    obligation_results: tuple[ObligationResult, ...] = ()
    passed_obligations: tuple[ObligationResult, ...] = ()
    failed_obligations: tuple[ObligationResult, ...] = ()
    not_implemented_obligations: tuple[ObligationResult, ...] = ()
    unknown_obligations: tuple[ObligationResult, ...] = ()
    not_applicable_obligations: tuple[ObligationResult, ...] = ()
    warnings: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = DEFAULT_ASSUMPTIONS
    limitations: tuple[str, ...] = DEFAULT_LIMITATIONS
    conventions: Mapping[str, Any] = field(default_factory=lambda: dict(DEFAULT_CONVENTIONS))
    duality_profile: str | None = None
    theory_kind: str | None = None
    parameters: Mapping[str, Any] = field(default_factory=dict)
    detailed_tables: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_results(
        cls,
        claim_name: str,
        results: Iterable[ObligationResult],
        *,
        assumptions: tuple[str, ...] = DEFAULT_ASSUMPTIONS,
        limitations: tuple[str, ...] = DEFAULT_LIMITATIONS,
        conventions: Mapping[str, Any] | None = None,
        duality_profile: str | None = None,
        theory_kind: str | None = None,
        parameters: Mapping[str, Any] | None = None,
    ) -> "Certificate":
        result_tuple = tuple(results)
        passed = tuple(result for result in result_tuple if result.status == Status.CERTIFIED)
        failed = tuple(result for result in result_tuple if result.status == Status.FAILED)
        not_implemented = tuple(
            result for result in result_tuple if result.status == Status.NOT_IMPLEMENTED
        )
        unknown = tuple(result for result in result_tuple if result.status == Status.UNKNOWN)
        not_applicable = tuple(
            result for result in result_tuple if result.status == Status.NOT_APPLICABLE
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
        elif unknown:
            overall = Status.UNKNOWN
        else:
            overall = Status.NOT_IMPLEMENTED if not_implemented else Status.NOT_APPLICABLE

        return cls(
            claim_name=claim_name,
            overall_status=overall,
            obligation_results=result_tuple,
            passed_obligations=passed,
            failed_obligations=failed,
            not_implemented_obligations=not_implemented,
            unknown_obligations=unknown,
            not_applicable_obligations=not_applicable,
            warnings=tuple(warnings),
            assumptions=assumptions,
            limitations=limitations,
            conventions=dict(conventions or DEFAULT_CONVENTIONS),
            duality_profile=duality_profile,
            theory_kind=theory_kind,
            parameters=dict(parameters or {}),
            detailed_tables=detailed_tables,
        )

    @property
    def outward_status(self) -> str:
        from dualitycert.core.theory_kind import FLAVORED_QUIVER
        if self.theory_kind == FLAVORED_QUIVER:
            return OUTWARD_OUT_OF_SCOPE
        if self.failed_obligations:
            return OUTWARD_FAILED
        if self.passed_obligations and self.not_implemented_obligations:
            return OUTWARD_PARTIAL
        if self.passed_obligations:
            return OUTWARD_PASSED
        return OUTWARD_NONE

    def all_obligation_results(self) -> tuple[ObligationResult, ...]:
        if self.obligation_results:
            return self.obligation_results
        return (
            self.passed_obligations
            + self.failed_obligations
            + self.not_implemented_obligations
            + self.unknown_obligations
            + self.not_applicable_obligations
        )

    def to_dict(self) -> dict[str, Any]:
        obligations = [
            _obligation_result_to_dict(result)
            for result in self.all_obligation_results()
        ]
        return {
            "claim_id": _slugify(self.claim_name),
            "claim_name": self.claim_name,
            "duality_profile": self.duality_profile,
            "theory_kind": self.theory_kind,
            "parameters": _json_safe(self.parameters),
            "outward_status": self.outward_status,
            "internal_status": self.overall_status.value,
            "assumptions": list(self.assumptions),
            "conventions": _json_safe(self.conventions),
            "limitations": list(self.limitations),
            "generated_obligations": obligations,
            "passed_obligations": [
                _obligation_result_to_dict(result)
                for result in self.passed_obligations
            ],
            "failed_obligations": [
                _obligation_result_to_dict(result)
                for result in self.failed_obligations
            ],
            "not_implemented_obligations": [
                _obligation_result_to_dict(result)
                for result in self.not_implemented_obligations
            ],
            "unknown_obligations": [
                _obligation_result_to_dict(result)
                for result in self.unknown_obligations
            ],
            "not_applicable_obligations": [
                _obligation_result_to_dict(result)
                for result in self.not_applicable_obligations
            ],
            "warnings": list(self.warnings),
            "failures": [
                _obligation_result_to_dict(result)
                for result in self.failed_obligations
            ],
            "detailed_tables": _json_safe(self.detailed_tables),
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    def render_text(self) -> str:
        from dualitycert.core.theory_kind import FLAVORED_QUIVER
        lines = [
            f"Certificate for: {self.claim_name}",
            f"Outward status: {self.outward_status}",
            f"Internal status enum: {self.overall_status.value}",
            "",
        ]
        if self.theory_kind == FLAVORED_QUIVER:
            lines += [
                "OUT OF SCOPE: the claim's theory kind (flavored_quiver) is outside the",
                "current verifier scope. No physics obligations were run.",
                "This is NOT a physics failure — the verifier cannot assess this claim type.",
            ]
        else:
            lines += [
                "Meaning: this is a consistency certificate under stated assumptions.",
                "It is not a proof of duality or IR equivalence.",
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
        if self.unknown_obligations:
            lines.extend(["", "Unknown / missing-data obligations (UNKNOWN):"])
            lines.extend(
                f"  - {result.name}: {result.message}"
                for result in self.unknown_obligations
            )
        if self.not_applicable_obligations:
            lines.extend(["", "Not applicable obligations (NOT_APPLICABLE):"])
            lines.extend(
                f"  - {result.name}: {result.message}"
                for result in self.not_applicable_obligations
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


def _obligation_result_to_dict(result: ObligationResult) -> dict[str, Any]:
    return {
        "name": result.name,
        "description": result.description,
        "status": result.status.value,
        "checker_name": result.checker_name,
        "message": result.message,
        "details": _json_safe(result.details),
        "warnings": list(result.warnings),
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, Status):
        return value.value
    if isinstance(value, Fraction):
        return _format_fraction(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _slugify(value: str) -> str:
    pieces = []
    for char in value.lower():
        if char.isalnum():
            pieces.append(char)
        elif pieces and pieces[-1] != "_":
            pieces.append("_")
    return "".join(pieces).strip("_")
