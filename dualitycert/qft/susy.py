"""4d N=1 supersymmetry-specific consistency checkers."""

from __future__ import annotations

from fractions import Fraction

from dualitycert.core.objects import CheckResult, Field, Representation, SuperpotentialTerm, Theory
from dualitycert.core.status import Status


def superpotential_invariance(theory: Theory) -> CheckResult:
    """Check gauge, nonabelian-global, and non-R U(1) invariance of W."""

    failures: list[str] = []
    details: dict[str, dict] = {}
    field_map = theory.field_map()

    for term in theory.superpotential_terms:
        term_details: dict[str, object] = {}
        expanded_fields = _expanded_fields(term, field_map)
        if isinstance(expanded_fields, str):
            failures.append(expanded_fields)
            details[term.display_name] = {"error": expanded_fields}
            continue

        gauge_reps = [field.gauge_rep for field in expanded_fields]
        gauge_ok = _contains_singlet(gauge_reps)
        term_details["gauge_singlet"] = gauge_ok
        if not gauge_ok:
            failures.append(f"{term.display_name} is not a gauge singlet")

        nonabelian_results: dict[str, bool] = {}
        for symmetry in theory.nonabelian_globals():
            reps = [field.rep_for_global(symmetry.label) for field in expanded_fields]
            ok = _contains_singlet(reps)
            nonabelian_results[symmetry.label] = ok
            if not ok:
                failures.append(
                    f"{term.display_name} is not singlet under {symmetry.label}"
                )
        term_details["nonabelian_global_singlets"] = nonabelian_results

        u1_totals: dict[str, Fraction] = {}
        for symmetry in theory.u1_globals():
            if symmetry.is_r:
                continue
            total = sum(
                field.u1_charge(symmetry.label, fermion=False)
                for field in expanded_fields
            )
            u1_totals[symmetry.label] = total
            if total != 0:
                failures.append(
                    f"{term.display_name} has nonzero {symmetry.label} charge {total}"
                )
        term_details["u1_charge_totals"] = u1_totals
        details[term.display_name] = term_details

    if failures:
        return CheckResult(
            status=Status.FAILED,
            message="Superpotential invariance failed: " + "; ".join(failures),
            details=details,
        )
    return CheckResult(
        status=Status.CERTIFIED,
        message="Superpotential terms are invariant under supported symmetries.",
        details=details,
    )


def superpotential_R_charge_equals_2(theory: Theory) -> CheckResult:
    """Check that each superpotential monomial has superfield R-charge 2."""

    failures: list[str] = []
    details: dict[str, Fraction | str] = {}
    field_map = theory.field_map()

    for term in theory.superpotential_terms:
        expanded_fields = _expanded_fields(term, field_map)
        if isinstance(expanded_fields, str):
            failures.append(expanded_fields)
            details[term.display_name] = expanded_fields
            continue
        total = sum(field.r_charge for field in expanded_fields)
        details[term.display_name] = total
        if total != 2:
            failures.append(f"{term.display_name} has R-charge {total}, expected 2")

    if failures:
        return CheckResult(
            status=Status.FAILED,
            message="Superpotential R-charge check failed: " + "; ".join(failures),
            details={"r_charge_totals": details},
        )
    return CheckResult(
        status=Status.CERTIFIED,
        message="Superpotential terms have R-charge 2.",
        details={"r_charge_totals": details},
    )


def superpotential_consistency(theory: Theory) -> CheckResult:
    """Run all implemented superpotential checks as one obligation."""

    invariance = superpotential_invariance(theory)
    r_charge = superpotential_R_charge_equals_2(theory)
    if invariance.status == Status.CERTIFIED and r_charge.status == Status.CERTIFIED:
        return CheckResult(
            status=Status.CERTIFIED,
            message="Superpotential passed invariance and R-charge checks.",
            details={"invariance": invariance.details, "r_charge": r_charge.details},
            warnings=invariance.warnings + r_charge.warnings,
        )
    messages = [
        result.message
        for result in (invariance, r_charge)
        if result.status == Status.FAILED
    ]
    return CheckResult(
        status=Status.FAILED,
        message="; ".join(messages),
        details={"invariance": invariance.details, "r_charge": r_charge.details},
        warnings=invariance.warnings + r_charge.warnings,
    )


def _expanded_fields(
    term: SuperpotentialTerm,
    field_map: dict[str, Field],
) -> list[Field] | str:
    fields: list[Field] = []
    for field_name, power in term.factors:
        field = field_map.get(field_name)
        if field is None:
            return f"{term.display_name} references unknown field {field_name}"
        fields.extend([field] * power)
    return fields


def _contains_singlet(reps: list[Representation]) -> bool:
    nontrivial = [rep.name for rep in reps if not rep.is_singlet]
    if not nontrivial:
        return True
    if len(nontrivial) == 2:
        if sorted(nontrivial) == ["antifundamental", "fundamental"]:
            return True
        if nontrivial[0] == nontrivial[1] == "adjoint":
            return True
    return False
