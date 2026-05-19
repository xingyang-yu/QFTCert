"""Gauge and global anomaly checkers."""

from __future__ import annotations

from fractions import Fraction
from itertools import combinations_with_replacement
from typing import Iterable

from dualitycert.core.objects import (
    CheckResult,
    Field,
    GaugeGroup,
    GlobalSymmetry,
    Representation,
    SINGLET,
    SymmetryMap,
    Theory,
)
from dualitycert.core.status import Status
from dualitycert.groups.su import cubic_anomaly, dimension, dynkin_index


AnomalyKey = tuple[str, ...]
AnomalyTable = dict[AnomalyKey, Fraction]


def gauge_anomaly_cancellation(theory: Theory) -> CheckResult:
    """Check cancellation of the SU(N)^3 gauge anomaly for each gauge node."""

    groups = _nonabelian_factors(theory)
    node_results: dict[str, dict] = {}
    failures: list[str] = []

    for node in theory.gauge_nodes:
        total = Fraction(0, 1)
        contributions: dict[str, Fraction] = {}
        for field in theory.fields:
            if not field.is_chiral:
                continue
            contribution = (
                cubic_anomaly(field.rep_for_node(node.label), node)
                * _spectator_dimension(field, groups, exclude_label=node.label)
            )
            contributions[field.name] = contribution
            total += contribution
        node_results[node.label] = {"total": total, "field_contributions": contributions}
        if total != 0:
            failures.append(f"{node.display_name} cubic gauge anomaly is {total}")

    if failures:
        return CheckResult(
            status=Status.FAILED,
            message="Gauge anomaly cancellation failed: " + "; ".join(failures),
            details=node_results,
        )
    node_names = ", ".join(node.display_name for node in theory.gauge_nodes)
    return CheckResult(
        status=Status.CERTIFIED,
        message=f"Cubic gauge anomaly cancels for all nodes ({node_names}).",
        details=node_results,
    )


def gauge_global_mixed_anomaly_cancellation(theory: Theory) -> CheckResult:
    """Check SU(gauge_i)^2 U(1) anomaly cancellation for each gauge node and U(1).

    A continuous U(1) global symmetry is a valid symmetry of the quantum gauge
    theory only if it has no mixed anomaly with the dynamical gauge group. For
    an R-symmetry this includes the adjoint gaugino contribution with R=1.
    """

    u1_globals = theory.u1_globals()
    if not u1_globals:
        return CheckResult(
            status=Status.NOT_APPLICABLE,
            message="Theory has no represented U(1) global symmetries.",
        )

    groups = _nonabelian_factors(theory)
    node_results: dict[str, dict] = {}
    failures: list[str] = []

    for node in theory.gauge_nodes:
        totals: dict[str, Fraction] = {}
        field_contributions: dict[str, dict[str, Fraction]] = {}

        for symmetry in u1_globals:
            total = Fraction(0, 1)
            per_field: dict[str, Fraction] = {}
            for field in theory.fields:
                if not field.is_chiral:
                    continue
                contribution = (
                    dynkin_index(field.rep_for_node(node.label), node)
                    * field.u1_charge(symmetry.label, fermion=True)
                    * _spectator_dimension(field, groups, exclude_label=node.label)
                )
                per_field[field.name] = contribution
                total += contribution
            if symmetry.is_r:
                per_field["gaugino"] = dynkin_index(
                    Representation("adjoint"),
                    node,
                )
                total += per_field["gaugino"]
            totals[symmetry.label] = total
            field_contributions[symmetry.label] = per_field
            if total != 0:
                failures.append(f"{node.display_name}^2 {symmetry.label}={total}")

        node_results[node.label] = {
            "totals": totals,
            "field_contributions": field_contributions,
        }

    if failures:
        return CheckResult(
            status=Status.FAILED,
            message="Mixed gauge-global anomaly cancellation failed: "
            + "; ".join(failures),
            details=node_results,
        )
    return CheckResult(
        status=Status.CERTIFIED,
        message="All represented SU(gauge)^2 U(1) mixed anomalies cancel.",
        details=node_results,
    )


def global_tHooft_anomaly_table(theory: Theory) -> AnomalyTable:
    """Compute a global 't Hooft anomaly table for supported symmetries."""

    table: AnomalyTable = {}
    nonabelian_globals = theory.nonabelian_globals()
    u1_globals = theory.u1_globals()
    groups = _nonabelian_factors(theory)

    for symmetry in nonabelian_globals:
        key = ("su_cubic", symmetry.label)
        table[key] = sum(
            _su_cubic_contribution(field, symmetry, groups)
            for field in theory.fields
            if field.is_chiral
        )

        for u1_symmetry in u1_globals:
            key = ("su_su_u1", symmetry.label, u1_symmetry.label)
            table[key] = sum(
                _su_su_u1_contribution(field, symmetry, u1_symmetry.label, groups)
                for field in theory.fields
                if field.is_chiral
            )

    u1_labels = tuple(sym.label for sym in u1_globals)
    for labels in combinations_with_replacement(u1_labels, 3):
        key = _u1_cubic_key(labels)
        table[key] = sum(
            _u1_cubic_contribution(field, labels, groups)
            for field in theory.fields
            if field.is_chiral
        )
        table[key] += _gaugino_u1_cubic_contribution(theory.gauge_nodes, labels)

    for label in u1_labels:
        key = ("gravity_u1", label)
        table[key] = sum(
            _gravity_u1_contribution(field, label, groups)
            for field in theory.fields
            if field.is_chiral
        )
        table[key] += _gaugino_gravity_u1_contribution(theory.gauge_nodes, label)

    return table


def compare_anomaly_tables(
    electric: Theory,
    magnetic: Theory,
    symmetry_map: SymmetryMap,
) -> CheckResult:
    """Compare global anomaly tables under an electric-to-magnetic map."""

    electric_table = global_tHooft_anomaly_table(electric)
    magnetic_table = global_tHooft_anomaly_table(magnetic)

    expected_magnetic_keys = {
        _map_key_to_magnetic(key, symmetry_map) for key in electric_table
    }
    mismatches = []
    for electric_key, electric_value in sorted(electric_table.items(), key=lambda item: item[0]):
        magnetic_key = _map_key_to_magnetic(electric_key, symmetry_map)
        magnetic_value = magnetic_table.get(magnetic_key, Fraction(0, 1))
        if electric_value != magnetic_value:
            mismatches.append(
                {
                    "key": _format_key(electric_key),
                    "magnetic_key": _format_key(magnetic_key),
                    "electric": electric_value,
                    "magnetic": magnetic_value,
                }
            )

    unexpected = []
    for magnetic_key, magnetic_value in sorted(magnetic_table.items(), key=lambda item: item[0]):
        if magnetic_key not in expected_magnetic_keys and magnetic_value != 0:
            unexpected.append(
                {
                    "magnetic_key": _format_key(magnetic_key),
                    "magnetic": magnetic_value,
                }
            )

    status = Status.CERTIFIED if not mismatches and not unexpected else Status.FAILED
    if status == Status.CERTIFIED:
        message = "Global 't Hooft anomaly tables match under the symmetry map."
    else:
        message = (
            "Global 't Hooft anomaly tables do not match "
            f"({len(mismatches)} mismatches, {len(unexpected)} unexpected entries)."
        )

    return CheckResult(
        status=status,
        message=message,
        details={
            "electric_table": {_format_key(key): value for key, value in electric_table.items()},
            "magnetic_table": {_format_key(key): value for key, value in magnetic_table.items()},
            "mismatches": mismatches,
            "unexpected_magnetic_entries": unexpected,
        },
    )


def _nonabelian_factors(theory: Theory) -> dict[str, GaugeGroup | GlobalSymmetry]:
    factors: dict[str, GaugeGroup | GlobalSymmetry] = {}
    for node in theory.gauge_nodes:
        factors[node.label] = node
    for symmetry in theory.nonabelian_globals():
        factors[symmetry.label] = symmetry
    return factors


def _rep_for_factor(field: Field, label: str) -> Representation:
    if label in field.gauge_reps:
        return field.gauge_reps[label]
    return field.rep_for_global(label)


def _spectator_dimension(
    field: Field,
    groups: dict[str, GaugeGroup | GlobalSymmetry],
    *,
    exclude_label: str | None = None,
) -> int:
    total = field.multiplicity
    for label, group in groups.items():
        if label == exclude_label:
            continue
        total *= dimension(_rep_for_factor(field, label), group)
    return total


def _su_cubic_contribution(
    field: Field,
    symmetry: GlobalSymmetry,
    groups: dict[str, GaugeGroup | GlobalSymmetry],
) -> Fraction:
    rep = field.rep_for_global(symmetry.label)
    return (
        cubic_anomaly(rep, symmetry)
        * _spectator_dimension(field, groups, exclude_label=symmetry.label)
    )


def _su_su_u1_contribution(
    field: Field,
    symmetry: GlobalSymmetry,
    u1_label: str,
    groups: dict[str, GaugeGroup | GlobalSymmetry],
) -> Fraction:
    rep = field.rep_for_global(symmetry.label)
    return (
        dynkin_index(rep, symmetry)
        * field.u1_charge(u1_label, fermion=True)
        * _spectator_dimension(field, groups, exclude_label=symmetry.label)
    )


def _u1_cubic_contribution(
    field: Field,
    labels: tuple[str, str, str],
    groups: dict[str, GaugeGroup | GlobalSymmetry],
) -> Fraction:
    charge_product = Fraction(1, 1)
    for label in labels:
        charge_product *= field.u1_charge(label, fermion=True)
    return charge_product * _spectator_dimension(field, groups)


def _gravity_u1_contribution(
    field: Field,
    label: str,
    groups: dict[str, GaugeGroup | GlobalSymmetry],
) -> Fraction:
    return field.u1_charge(label, fermion=True) * _spectator_dimension(field, groups)


def _gaugino_u1_cubic_contribution(
    gauge_nodes: tuple[GaugeGroup, ...],
    labels: tuple[str, str, str],
) -> Fraction:
    if all(_is_r_label(label) for label in labels):
        return Fraction(sum(node.dim_adjoint for node in gauge_nodes), 1)
    return Fraction(0, 1)


def _gaugino_gravity_u1_contribution(gauge_nodes: tuple[GaugeGroup, ...], label: str) -> Fraction:
    if _is_r_label(label):
        return Fraction(sum(node.dim_adjoint for node in gauge_nodes), 1)
    return Fraction(0, 1)


def _u1_cubic_key(labels: Iterable[str]) -> AnomalyKey:
    return ("u1_cubic", *tuple(sorted(labels)))


def _map_key_to_magnetic(key: AnomalyKey, symmetry_map: SymmetryMap) -> AnomalyKey:
    tag = key[0]
    if tag == "u1_cubic":
        return _u1_cubic_key(symmetry_map.magnetic_label(label) for label in key[1:])
    return (tag, *tuple(symmetry_map.magnetic_label(label) for label in key[1:]))


def _format_key(key: AnomalyKey) -> str:
    tag = key[0]
    if tag == "su_cubic":
        return f"{key[1]}^3"
    if tag == "su_su_u1":
        return f"{key[1]}^2 {key[2]}"
    if tag == "u1_cubic":
        return " ".join(key[1:])
    if tag == "gravity_u1":
        return f"gravity^2 {key[1]}"
    return " ".join(key)


def _is_r_label(label: str) -> bool:
    normalized = label.upper()
    return normalized in {"U(1)_R", "U1_R"} or normalized.endswith("_R")
