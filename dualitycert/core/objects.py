"""Dataclass model for SQCD-like consistency certificates."""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Mapping, Sequence, Union

from dualitycert.core.status import Status


NumberLike = Union[int, float, str, Fraction]


def as_fraction(value: NumberLike) -> Fraction:
    """Normalize numeric input to exact rational arithmetic."""

    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value, 1)
    if isinstance(value, float):
        return Fraction(value).limit_denominator()
    return Fraction(value)


@dataclass(frozen=True)
class GaugeGroup:
    """A gauge group. The first prototype supports SU(N)."""

    kind: str
    N: int
    label: str | None = None

    def __post_init__(self) -> None:
        kind = self.kind.upper()
        if kind != "SU":
            raise ValueError(f"Unsupported gauge group kind: {self.kind}")
        if self.N < 2:
            raise ValueError("SU(N) requires N >= 2")
        object.__setattr__(self, "kind", kind)
        if self.label is None:
            object.__setattr__(self, "label", f"SU({self.N})")

    @property
    def dim_adjoint(self) -> int:
        return self.N * self.N - 1

    @property
    def display_name(self) -> str:
        return f"{self.kind}({self.N})"


@dataclass(frozen=True)
class GlobalSymmetry:
    """A global symmetry label."""

    kind: str
    label: str
    N: int | None = None

    def __post_init__(self) -> None:
        kind = self.kind.upper()
        if kind == "U(1)_R":
            kind = "U1_R"
        if kind == "U(1)":
            kind = "U1"
        if kind not in {"SU", "U1", "U1_R"}:
            raise ValueError(f"Unsupported global symmetry kind: {self.kind}")
        if kind == "SU":
            if self.N is None or self.N < 2:
                raise ValueError("Global SU(N) requires N >= 2")
        elif self.N is not None:
            raise ValueError("U(1) global symmetries should not set N")
        object.__setattr__(self, "kind", kind)

    @property
    def is_nonabelian(self) -> bool:
        return self.kind == "SU"

    @property
    def is_u1(self) -> bool:
        return self.kind in {"U1", "U1_R"}

    @property
    def is_r(self) -> bool:
        return self.kind == "U1_R"


@dataclass(frozen=True)
class Representation:
    """A supported representation of an SU(N) factor."""

    name: str

    def __post_init__(self) -> None:
        normalized = self.name.lower().replace("_", "-")
        aliases = {
            "fund": "fundamental",
            "f": "fundamental",
            "anti-fund": "antifundamental",
            "anti-fundamental": "antifundamental",
            "antifund": "antifundamental",
            "anti": "antifundamental",
            "adj": "adjoint",
            "1": "singlet",
            "trivial": "singlet",
        }
        normalized = aliases.get(normalized, normalized)
        if normalized not in {
            "fundamental",
            "antifundamental",
            "adjoint",
            "singlet",
        }:
            raise ValueError(f"Unsupported representation: {self.name}")
        object.__setattr__(self, "name", normalized)

    @property
    def is_singlet(self) -> bool:
        return self.name == "singlet"

    def conjugate(self) -> "Representation":
        if self.name == "fundamental":
            return Representation("antifundamental")
        if self.name == "antifundamental":
            return Representation("fundamental")
        return self


SINGLET = Representation("singlet")


@dataclass(frozen=True)
class Field:
    """A field in a 4d N=1 theory."""

    name: str
    field_type: str
    gauge_reps: Mapping[str, Representation] = field(default_factory=dict)
    global_reps: Mapping[str, Representation] = field(default_factory=dict)
    u1_charges: Mapping[str, NumberLike] = field(default_factory=dict)
    r_charge: NumberLike = Fraction(0, 1)
    multiplicity: int = 1

    def __post_init__(self) -> None:
        if self.multiplicity < 1:
            raise ValueError("Field multiplicity must be positive")
        object.__setattr__(
            self,
            "gauge_reps",
            {label: _coerce_rep(rep) for label, rep in self.gauge_reps.items()},
        )
        object.__setattr__(
            self,
            "global_reps",
            {label: _coerce_rep(rep) for label, rep in self.global_reps.items()},
        )
        object.__setattr__(
            self,
            "u1_charges",
            {label: as_fraction(charge) for label, charge in self.u1_charges.items()},
        )
        object.__setattr__(self, "r_charge", as_fraction(self.r_charge))

    @property
    def is_chiral(self) -> bool:
        return "chiral" in self.field_type.lower()

    def u1_charge(self, label: str, *, fermion: bool = True) -> Fraction:
        if label in self.u1_charges:
            return self.u1_charges[label]
        if _is_r_label(label):
            return self.r_charge - 1 if fermion else self.r_charge
        return Fraction(0, 1)

    def rep_for_global(self, label: str) -> Representation:
        return self.global_reps.get(label, SINGLET)

    def rep_for_node(self, node_label: str) -> Representation:
        return self.gauge_reps.get(node_label, SINGLET)


@dataclass(frozen=True)
class SuperpotentialTerm:
    """A monomial term in a holomorphic superpotential."""

    factors: tuple[tuple[str, int], ...]
    coefficient: NumberLike = Fraction(1, 1)
    label: str | None = None

    def __post_init__(self) -> None:
        normalized: list[tuple[str, int]] = []
        for field_name, power in self.factors:
            if power < 1:
                raise ValueError("Superpotential powers must be positive")
            normalized.append((field_name, int(power)))
        object.__setattr__(self, "factors", tuple(normalized))
        object.__setattr__(self, "coefficient", as_fraction(self.coefficient))

    @property
    def field_names(self) -> tuple[str, ...]:
        names: list[str] = []
        for field_name, power in self.factors:
            names.extend([field_name] * power)
        return tuple(names)

    @property
    def display_name(self) -> str:
        if self.label:
            return self.label
        pieces = []
        for field_name, power in self.factors:
            pieces.append(field_name if power == 1 else f"{field_name}^{power}")
        return " ".join(pieces)


@dataclass(frozen=True)
class Theory:
    """A 4d N=1 theory with a quiver gauge group (K >= 1 nodes)."""

    name: str
    gauge_nodes: tuple[GaugeGroup, ...]
    fields: tuple[Field, ...] = ()
    superpotential_terms: tuple[SuperpotentialTerm, ...] = ()
    global_symmetries: tuple[GlobalSymmetry, ...] = ()

    def field_map(self) -> dict[str, Field]:
        return {field.name: field for field in self.fields}

    def global_symmetry_map(self) -> dict[str, GlobalSymmetry]:
        return {sym.label: sym for sym in self.global_symmetries}

    def nonabelian_globals(self) -> tuple[GlobalSymmetry, ...]:
        return tuple(sym for sym in self.global_symmetries if sym.is_nonabelian)

    def u1_globals(self) -> tuple[GlobalSymmetry, ...]:
        return tuple(sym for sym in self.global_symmetries if sym.is_u1)


@dataclass(frozen=True)
class SymmetryMap:
    """Map electric global symmetry labels to magnetic labels."""

    electric_to_magnetic: Mapping[str, str] = field(default_factory=dict)

    def magnetic_label(self, electric_label: str) -> str:
        return self.electric_to_magnetic.get(electric_label, electric_label)

    def electric_label(self, magnetic_label: str) -> str:
        for electric, magnetic in self.electric_to_magnetic.items():
            if magnetic == magnetic_label:
                return electric
        return magnetic_label


@dataclass(frozen=True)
class DualityClaim:
    """A proposed duality relation to be checked by obligations."""

    name: str
    electric_theory: Theory
    magnetic_theory: Theory
    symmetry_map: SymmetryMap = field(default_factory=SymmetryMap)
    operator_map: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CheckResult:
    """Result returned by a checker."""

    status: Status
    message: str
    details: Mapping[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return self.status == Status.CERTIFIED


def _coerce_rep(rep: Representation | str) -> Representation:
    if isinstance(rep, Representation):
        return rep
    return Representation(rep)


def _is_r_label(label: str) -> bool:
    normalized = label.upper()
    return normalized in {"U(1)_R", "U1_R"} or normalized.endswith("_R")


def freeze_fields(fields: Sequence[Field]) -> tuple[Field, ...]:
    return tuple(fields)
