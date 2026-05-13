"""Minimal operator-map consistency checks for SQCD-like claims."""

from __future__ import annotations

from fractions import Fraction
from typing import Iterable

from dualitycert.core.objects import CheckResult, DualityClaim, Field
from dualitycert.core.status import Status


BARYON_LABEL = "U(1)_B"
R_LABEL = "U(1)_R"


def minimal_operator_map_abelian_charges(claim: DualityClaim) -> CheckResult:
    """Check U(1)_B and U(1)_R charges of standard SQCD operator maps.

    Implemented maps:

    - meson: Q Qtilde <-> M
    - baryon: Q^Nc <-> q^Nmag
    - antibaryon: Qtilde^Nc <-> qtilde^Nmag

    Non-Abelian flavor representation matching is intentionally not checked
    here; it remains a separate NOT_IMPLEMENTED obligation.
    """

    parameters = claim.metadata.get("parameters", {})
    nc = parameters.get("Nc")
    if nc is None:
        return CheckResult(
            status=Status.NOT_IMPLEMENTED,
            message="Minimal operator-map checker requires SQCD metadata with Nc.",
            details={"implemented": ["U(1)_B", "U(1)_R"]},
        )

    electric_fields = claim.electric_theory.field_map()
    magnetic_fields = claim.magnetic_theory.field_map()
    magnetic_rank = claim.magnetic_theory.gauge_group.N

    maps = (
        _OperatorMap("meson", (("Q", 1), ("Qtilde", 1)), (("M", 1),)),
        _OperatorMap("baryon", (("Q", int(nc)),), (("q", magnetic_rank),)),
        _OperatorMap(
            "antibaryon",
            (("Qtilde", int(nc)),),
            (("qtilde", magnetic_rank),),
        ),
    )

    failures: list[str] = []
    details: dict[str, dict] = {}
    for operator_map in maps:
        electric_charges = _operator_charges(
            operator_map.electric_factors,
            electric_fields,
        )
        magnetic_charges = _operator_charges(
            operator_map.magnetic_factors,
            magnetic_fields,
        )
        details[operator_map.name] = {
            "electric_operator": _format_factors(operator_map.electric_factors),
            "magnetic_operator": _format_factors(operator_map.magnetic_factors),
            "electric": electric_charges,
            "magnetic": magnetic_charges,
        }
        if "error" in electric_charges:
            failures.append(f"{operator_map.name}: {electric_charges['error']}")
            continue
        if "error" in magnetic_charges:
            failures.append(f"{operator_map.name}: {magnetic_charges['error']}")
            continue
        for label in (BARYON_LABEL, R_LABEL):
            if electric_charges[label] != magnetic_charges[label]:
                failures.append(
                    f"{operator_map.name} has mismatched {label}: "
                    f"electric={electric_charges[label]}, magnetic={magnetic_charges[label]}"
                )

    details["implemented_quantum_numbers"] = [BARYON_LABEL, R_LABEL]
    details["not_implemented"] = [
        "non-Abelian flavor representation matching",
        "chiral-ring relations",
        "operator normalization",
    ]

    if failures:
        return CheckResult(
            status=Status.FAILED,
            message="Minimal Abelian operator-map check failed: " + "; ".join(failures),
            details=details,
        )
    return CheckResult(
        status=Status.CERTIFIED,
        message="Standard SQCD operator maps match U(1)_B and U(1)_R charges.",
        details=details,
    )


class _OperatorMap:
    def __init__(
        self,
        name: str,
        electric_factors: tuple[tuple[str, int], ...],
        magnetic_factors: tuple[tuple[str, int], ...],
    ) -> None:
        self.name = name
        self.electric_factors = electric_factors
        self.magnetic_factors = magnetic_factors


def _operator_charges(
    factors: Iterable[tuple[str, int]],
    fields: dict[str, Field],
) -> dict[str, Fraction | str]:
    charges = {BARYON_LABEL: Fraction(0, 1), R_LABEL: Fraction(0, 1)}
    for field_name, power in factors:
        field = fields.get(field_name)
        if field is None:
            return {"error": f"operator references unknown field {field_name}"}
        charges[BARYON_LABEL] += power * field.u1_charge(BARYON_LABEL, fermion=False)
        charges[R_LABEL] += power * field.r_charge
    return charges


def _format_factors(factors: Iterable[tuple[str, int]]) -> str:
    pieces = []
    for field_name, power in factors:
        pieces.append(field_name if power == 1 else f"{field_name}^{power}")
    return " ".join(pieces)
