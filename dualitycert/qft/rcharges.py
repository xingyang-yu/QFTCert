"""R-symmetry observables and unitarity-bound checks."""

from __future__ import annotations

from fractions import Fraction
from typing import Iterable

from dualitycert.core.objects import CheckResult, DualityClaim, Field, SINGLET, Theory
from dualitycert.core.status import Status
from dualitycert.groups.su import dimension


UNITARITY_R_BOUND = Fraction(2, 3)


def central_charge_matching(claim: DualityClaim) -> CheckResult:
    """Compare Tr R, Tr R^3, and a,c from the encoded R-symmetry.

    The formulas are the standard 4d N=1 SCFT anomaly formulas

        a = 3/32 (3 Tr R^3 - Tr R),
        c = 1/32 (9 Tr R^3 - 5 Tr R).

    This validates a stated R-symmetry; it does not perform full
    a-maximization or detect accidental symmetries.
    """

    if not _has_r_symmetry(claim.electric_theory) or not _has_r_symmetry(
        claim.magnetic_theory
    ):
        return CheckResult(
            status=Status.UNKNOWN,
            message="No encoded U(1)_R symmetry is available for central-charge checks.",
            details={"implemented": ["Tr R", "Tr R^3", "a", "c"]},
        )

    electric = r_symmetry_observables(claim.electric_theory)
    magnetic = r_symmetry_observables(claim.magnetic_theory)
    mismatches = [
        key for key in ("TrR", "TrR3", "a", "c") if electric[key] != magnetic[key]
    ]
    details = {
        "electric": electric,
        "magnetic": magnetic,
        "not_implemented": [
            "full a-maximization over trial mixings",
            "automatic accidental-symmetry handling",
            "automatic decoupled-free-field repair",
        ],
    }
    if mismatches:
        return CheckResult(
            status=Status.FAILED,
            message="Encoded R-symmetry observables do not match: "
            + ", ".join(mismatches),
            details=details,
        )
    return CheckResult(
        status=Status.CERTIFIED,
        message="Encoded R-symmetry Tr R, Tr R^3, a, and c match.",
        details=details,
        warnings=(
            "This validates the encoded R-symmetry data; it does not run full a-maximization.",
        ),
    )


def operator_unitarity_bound_check(claim: DualityClaim) -> CheckResult:
    """Check R >= 2/3 for encoded gauge-invariant chiral operators.

    The bound is applied only to gauge-invariant chiral operators represented
    by metadata or, for SQCD claims, to the standard meson and baryon maps. It
    assumes the encoded R is the superconformal R-charge.
    """

    operators = _encoded_operators(claim)
    if not operators:
        return CheckResult(
            status=Status.UNKNOWN,
            message="No gauge-invariant chiral operator R-charge data is encoded.",
            details={"bound": UNITARITY_R_BOUND},
        )

    failures: list[str] = []
    details: dict[str, dict[str, Fraction]] = {}
    for name, r_charge in operators:
        delta = Fraction(3, 2) * r_charge
        details[name] = {"R": r_charge, "Delta": delta}
        if r_charge < UNITARITY_R_BOUND:
            failures.append(f"{name} has R={r_charge} < 2/3")

    if failures:
        return CheckResult(
            status=Status.FAILED,
            message="Chiral-operator unitarity bound failed: " + "; ".join(failures),
            details=details,
        )
    return CheckResult(
        status=Status.CERTIFIED,
        message="Encoded gauge-invariant chiral operators satisfy R >= 2/3.",
        details=details,
        warnings=(
            "Unitarity is checked only for encoded/default SQCD gauge-invariant operators.",
        ),
    )


def r_symmetry_observables(theory: Theory) -> dict[str, Fraction]:
    """Compute Tr R, Tr R^3, a, and c from left-handed Weyl fermions."""

    gaugino_dim = sum(node.dim_adjoint for node in theory.gauge_nodes)
    tr_r = Fraction(gaugino_dim, 1)
    tr_r3 = Fraction(gaugino_dim, 1)
    nonabelian_globals = theory.nonabelian_globals()

    for field in theory.fields:
        if not field.is_chiral:
            continue
        r_fermion = field.r_charge - 1
        multiplicity = field.multiplicity
        for node in theory.gauge_nodes:
            multiplicity *= dimension(field.rep_for_node(node.label), node)
        for symmetry in nonabelian_globals:
            multiplicity *= dimension(field.rep_for_global(symmetry.label), symmetry)
        tr_r += multiplicity * r_fermion
        tr_r3 += multiplicity * r_fermion**3

    return {
        "TrR": tr_r,
        "TrR3": tr_r3,
        "a": Fraction(3, 32) * (3 * tr_r3 - tr_r),
        "c": Fraction(1, 32) * (9 * tr_r3 - 5 * tr_r),
    }


def _has_r_symmetry(theory: Theory) -> bool:
    return any(sym.is_r for sym in theory.u1_globals())


def _encoded_operators(claim: DualityClaim) -> tuple[tuple[str, Fraction], ...]:
    metadata_operators = claim.metadata.get("operators", ())
    parsed = []
    for item in metadata_operators:
        name = item.get("name")
        r_charge = item.get("R")
        if name is not None and r_charge is not None:
            parsed.append((str(name), Fraction(r_charge)))
    if parsed:
        return tuple(parsed)

    if claim.metadata.get("duality_profile") != "seiberg_sqcd":
        return ()

    parameters = claim.metadata.get("parameters", {})
    nc = parameters.get("Nc")
    if nc is None:
        return ()
    electric_fields = claim.electric_theory.field_map()
    magnetic_fields = claim.magnetic_theory.field_map()
    magnetic_rank = claim.magnetic_theory.gauge_nodes[0].N
    standard_maps = (
        ("meson electric Q Qtilde", (("Q", 1), ("Qtilde", 1)), electric_fields),
        ("meson magnetic M", (("M", 1),), magnetic_fields),
        ("baryon electric Q^Nc", (("Q", int(nc)),), electric_fields),
        ("baryon magnetic q^Nmag", (("q", magnetic_rank),), magnetic_fields),
        ("antibaryon electric Qtilde^Nc", (("Qtilde", int(nc)),), electric_fields),
        (
            "antibaryon magnetic qtilde^Nmag",
            (("qtilde", magnetic_rank),),
            magnetic_fields,
        ),
    )
    operators = []
    for name, factors, fields in standard_maps:
        r_charge = _operator_r_charge(factors, fields)
        if r_charge is not None:
            operators.append((name, r_charge))
    return tuple(operators)


def _operator_r_charge(
    factors: Iterable[tuple[str, int]],
    fields: dict[str, Field],
) -> Fraction | None:
    total = Fraction(0, 1)
    for field_name, power in factors:
        field = fields.get(field_name)
        if field is None:
            return None
        total += power * field.r_charge
    return total
