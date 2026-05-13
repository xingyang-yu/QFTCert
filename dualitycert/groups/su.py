"""SU(N) representation helpers."""

from __future__ import annotations

from fractions import Fraction

from dualitycert.core.objects import GaugeGroup, GlobalSymmetry, Representation


def su(N: int, *, label: str | None = None, global_symmetry: bool = False) -> GaugeGroup | GlobalSymmetry:
    if global_symmetry:
        if label is None:
            label = f"SU({N})"
        return GlobalSymmetry("SU", label=label, N=N)
    return GaugeGroup("SU", N=N, label=label)


def fundamental() -> Representation:
    return Representation("fundamental")


def antifundamental() -> Representation:
    return Representation("antifundamental")


def adjoint() -> Representation:
    return Representation("adjoint")


def singlet() -> Representation:
    return Representation("singlet")


def dimension(rep: Representation, group: GaugeGroup | GlobalSymmetry) -> int:
    if group.kind != "SU":
        raise ValueError("dimension is only implemented for SU(N) groups")
    if rep.name in {"fundamental", "antifundamental"}:
        return int(group.N)
    if rep.name == "adjoint":
        return int(group.N * group.N - 1)
    if rep.name == "singlet":
        return 1
    raise ValueError(f"Unsupported representation: {rep.name}")


def cubic_anomaly(rep: Representation, group: GaugeGroup | GlobalSymmetry) -> Fraction:
    if group.kind != "SU":
        raise ValueError("cubic_anomaly is only implemented for SU(N) groups")
    if rep.name == "fundamental":
        return Fraction(1, 1)
    if rep.name == "antifundamental":
        return Fraction(-1, 1)
    return Fraction(0, 1)


def dynkin_index(rep: Representation, group: GaugeGroup | GlobalSymmetry) -> Fraction:
    if group.kind != "SU":
        raise ValueError("dynkin_index is only implemented for SU(N) groups")
    if rep.name in {"fundamental", "antifundamental"}:
        return Fraction(1, 2)
    if rep.name == "adjoint":
        return Fraction(group.N, 1)
    return Fraction(0, 1)
