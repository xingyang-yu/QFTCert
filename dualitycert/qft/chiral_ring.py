"""F-term and chiral-ring consequence checks for SQCD-like claims."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from dualitycert.core.objects import CheckResult, DualityClaim, SuperpotentialTerm, Theory
from dualitycert.core.status import Status


Monomial = tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class SQCDFTermConsequences:
    """Supported magnetic SQCD F-term consequences inferred from encoded W."""

    has_dW_dM_q_qtilde: bool
    has_dW_dq_M_qtilde: bool
    has_dW_dqtilde_M_q: bool
    missing_fields: tuple[str, ...]
    f_terms: dict[str, list[str]]

    @property
    def has_meson_lifting_relation(self) -> bool:
        return self.has_dW_dM_q_qtilde and not self.missing_fields

    @property
    def has_flat_direction_mass_relations(self) -> bool:
        return (
            self.has_dW_dq_M_qtilde
            and self.has_dW_dqtilde_M_q
            and not self.missing_fields
        )


def f_term_relations(theory: Theory) -> dict[str, list[Monomial]]:
    """Extract monomial F-term relations from an encoded superpotential.

    For a monomial superpotential term, this returns the monomials appearing
    in dW/dPhi for each field Phi. It is a syntactic F-term extractor for the
    encoded W, not a Groebner-basis or ideal-equivalence engine.
    """

    relations: dict[str, list[Monomial]] = {}
    for term in theory.superpotential_terms:
        if term.coefficient == 0:
            continue
        for field_name, power in term.factors:
            if power < 1:
                continue
            derivative = _derivative_monomial(term, field_name)
            if derivative is not None:
                relations.setdefault(field_name, []).append(derivative)
    return relations


def sqcd_magnetic_f_term_consequences(claim: DualityClaim) -> SQCDFTermConsequences:
    """Infer the SQCD-specific F-term consequences needed by later checks."""

    field_map = claim.magnetic_theory.field_map()
    missing = tuple(name for name in ("M", "q", "qtilde") if name not in field_map)
    relations = f_term_relations(claim.magnetic_theory)
    target_q_qtilde = _monomial_key((("q", 1), ("qtilde", 1)))
    target_M_qtilde = _monomial_key((("M", 1), ("qtilde", 1)))
    target_M_q = _monomial_key((("M", 1), ("q", 1)))

    return SQCDFTermConsequences(
        has_dW_dM_q_qtilde=target_q_qtilde in relations.get("M", []),
        has_dW_dq_M_qtilde=target_M_qtilde in relations.get("q", []),
        has_dW_dqtilde_M_q=target_M_q in relations.get("qtilde", []),
        missing_fields=missing,
        f_terms={
            field_name: [_format_monomial(monomial) for monomial in monomials]
            for field_name, monomials in sorted(relations.items())
        },
    )


def sqcd_magnetic_meson_f_term_lifting_check(claim: DualityClaim) -> CheckResult:
    """Check that magnetic q qtilde is constrained by encoded F-terms.

    In SQCD Seiberg duality, the elementary singlet M maps to the electric
    meson Q Qtilde. The magnetic composite q qtilde should not remain as an
    additional independent meson generator; the encoded F-term relation dW/dM
    should contain q qtilde. This checks that consequence, not the literal
    presence of a particular superpotential string.
    """

    if claim.metadata.get("duality_profile") != "seiberg_sqcd":
        return CheckResult(
            status=Status.NOT_APPLICABLE,
            message="Magnetic meson F-term lifting checker is SQCD-specific.",
        )

    consequences = sqcd_magnetic_f_term_consequences(claim)
    details = {
        "required_consequence": "dW/dM contains q qtilde",
        "has_required_consequence": consequences.has_meson_lifting_relation,
        "missing_fields": list(consequences.missing_fields),
        "f_terms": consequences.f_terms,
        "not_implemented": [
            "full chiral-ring ideal comparison",
            "flavor-index rank conditions",
            "quantum chiral-ring constraints",
        ],
    }

    if consequences.missing_fields:
        return CheckResult(
            status=Status.FAILED,
            message=(
                "Cannot check magnetic meson lifting because required fields are "
                f"missing: {', '.join(consequences.missing_fields)}."
            ),
            details=details,
        )

    if not consequences.has_dW_dM_q_qtilde:
        return CheckResult(
            status=Status.FAILED,
            message=(
                "Magnetic composite q qtilde is not constrained by the encoded "
                "dW/dM F-term; it would remain as an extra mesonic chiral-ring "
                "generator in this supported SQCD check."
            ),
            details=details,
        )

    return CheckResult(
        status=Status.CERTIFIED,
        message="Encoded magnetic F-terms constrain q qtilde as required by the SQCD meson map.",
        details=details,
    )


def _derivative_monomial(
    term: SuperpotentialTerm,
    field_name: str,
) -> Monomial | None:
    derived = []
    hit = False
    for factor_name, power in term.factors:
        if factor_name == field_name and not hit:
            hit = True
            if power > 1:
                derived.append((factor_name, power - 1))
            continue
        derived.append((factor_name, power))
    if not hit:
        return None
    return _monomial_key(derived)


def _monomial_key(factors: Iterable[tuple[str, int]]) -> Monomial:
    powers: dict[str, int] = {}
    for field_name, power in factors:
        if power <= 0:
            continue
        powers[field_name] = powers.get(field_name, 0) + int(power)
    return tuple(sorted(powers.items()))


def _format_monomial(monomial: Monomial) -> str:
    if not monomial:
        return "1"
    pieces = []
    for field_name, power in monomial:
        pieces.append(field_name if power == 1 else f"{field_name}^{power}")
    return " ".join(pieces)
