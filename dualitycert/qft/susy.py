"""4d N=1 supersymmetry-specific consistency checkers."""

from __future__ import annotations

from fractions import Fraction

from dualitycert.core.objects import CheckResult, Field, Representation, SINGLET, SuperpotentialTerm, Theory
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

        gauge_ok = True
        for node in theory.gauge_nodes:
            node_reps = [field.rep_for_node(node.label) for field in expanded_fields]
            if not _contains_singlet(node_reps):
                gauge_ok = False
                failures.append(
                    f"{term.display_name} is not a gauge singlet under {node.label}"
                )
        term_details["gauge_singlet"] = gauge_ok

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
    # Tr(X^n) for n >= 2: pure adjoint trace is gauge invariant
    if all(r == "adjoint" for r in nontrivial) and len(nontrivial) >= 2:
        return True
    # q Y^n qtilde for n >= 0: one fundamental + zero-or-more adjoints + one antifundamental
    funds = [r for r in nontrivial if r == "fundamental"]
    antifunds = [r for r in nontrivial if r == "antifundamental"]
    adjs = [r for r in nontrivial if r == "adjoint"]
    if len(funds) == 1 and len(antifunds) == 1 and len(adjs) == len(nontrivial) - 2:
        return True
    return False
