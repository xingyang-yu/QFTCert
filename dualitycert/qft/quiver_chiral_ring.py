"""Bounded cyclic path-algebra primitives for pure_quiver theories.

Phase 2a step 1: arrow extraction + cyclic-word enumeration. No F-ideal
saturation, no relation matrix, no verdict logic yet — those land in
subsequent steps (see docs/phase2a_pure_quiver_chiral_ring.md §14).

Conventions (locked in design doc §2):
  - Path multiplication is left-to-right: AB means first A, then B; valid
    iff target(A) == source(B). source(AB) = source(A), target(AB) = target(B).
  - A cyclic word is an equivalence class of closed walks under cyclic
    rotation ONLY. Orientation is preserved (no reversal identification).
  - Canonical representative: lex-smallest rotation under the total order
    on arrow machine labels.
  - Multi-arrow expansion (§3.2): a Field with multiplicity m > 1 is
    expanded into m arrows with machine labels f"{Field.name}[{i}]"; with
    m == 1 the machine label is just Field.name. The Field.name is always
    stored on Arrow.display_label for diagnostics.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable, Iterator, Mapping

from dualitycert.core.objects import Field, Theory


class PureQuiverShapeError(ValueError):
    """Raised when a Field cannot be interpreted as a pure-quiver arrow.

    The bounded chiral-ring check converts this into a NOT_APPLICABLE
    verdict (see design doc §3.2 / §7); raising at the extraction layer
    keeps the error path uniform.
    """

    def __init__(self, field_name: str, reason: str) -> None:
        super().__init__(f"Field {field_name!r}: {reason}")
        self.field_name = field_name
        self.reason = reason


@dataclass(frozen=True)
class Arrow:
    """A directed arrow in a pure-quiver path algebra.

    `label` is the canonical machine identifier used for lex ordering,
    cyclic-word enumeration, and F-relation rows. `display_label` is the
    underlying Field.name (shared across multiplicity copies).
    """

    label: str
    display_label: str
    source: str
    target: str
    r_charge: Fraction

    @property
    def is_loop(self) -> bool:
        return self.source == self.target


@dataclass(frozen=True)
class CyclicWord:
    """A canonical representative of a closed-walk cyclic-rotation class.

    `arrows` is the lex-min rotation of the underlying closed walk's
    machine labels. `r_charge` is the sum of arrow R-charges (well-defined
    on the rotation class).

    Invariants enforced at construction so that external callers cannot
    fabricate ill-formed instances that would later collide with the
    enumerator's canonical-form set or break the `frozen=True` contract:
      - `arrows` is coerced to a `tuple` (a `list` would silently break
        `hash(CyclicWord)` and undermine `frozen=True`);
      - `length >= 1` (the path-algebra identity at a node is a separate
        object `e_v` and cannot be represented by an unmarked empty word);
      - `length == len(arrows)`;
      - `arrows` equals its own lex-min rotation (canonical form).
    """

    arrows: tuple[str, ...]
    length: int
    r_charge: Fraction | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "arrows", tuple(self.arrows))
        if self.length < 1:
            raise ValueError(
                f"CyclicWord length must be >= 1, got {self.length} "
                "(the empty word is not a valid single-trace operator)"
            )
        if self.length != len(self.arrows):
            raise ValueError(
                f"CyclicWord length {self.length} does not match arrows tuple "
                f"of size {len(self.arrows)}"
            )
        canonical = _canonical_rotation(self.arrows)
        if self.arrows != canonical:
            raise ValueError(
                f"CyclicWord arrows {self.arrows!r} is not its canonical "
                f"lex-min rotation; expected {canonical!r}"
            )


def extract_arrows(theory: Theory) -> tuple[Arrow, ...]:
    """Read a `Theory` and emit one `Arrow` per arrow copy.

    Recognised field shapes (gauge_reps, ignoring singlet entries):
      - exactly one adjoint at a gauge node v → self-loop at v;
      - exactly one antifundamental at gauge node s and exactly one
        fundamental at gauge node t (s != t) → arrow s → t.

    Every chiral field must match one of those shapes — gauge singlets,
    bilateral fundamentals, mixed adjoint+fundamental, etc. all raise
    `PureQuiverShapeError`. The bounded chiral-ring check converts these
    into a NOT_APPLICABLE verdict (design doc §3.2 / §7).

    Two further well-formedness invariants are enforced here:
      - every `gauge_reps` key must be the label of a node in
        `theory.gauge_nodes` (typos like a missing node are caught);
      - every emitted `Arrow.label` must be unique across the theory
        (otherwise two fields would silently collapse to the same
        cyclic-word generator).
    """

    valid_nodes = {node.label for node in theory.gauge_nodes}
    arrows: list[Arrow] = []
    seen_labels: set[str] = set()

    for field_obj in theory.fields:
        for node_label in field_obj.gauge_reps:
            if node_label not in valid_nodes:
                raise PureQuiverShapeError(
                    field_obj.name,
                    f"gauge_reps references unknown node {node_label!r} "
                    f"(theory nodes: {sorted(valid_nodes)})",
                )

        non_singlet = {
            node: rep
            for node, rep in field_obj.gauge_reps.items()
            if not rep.is_singlet
        }
        if not non_singlet:
            raise PureQuiverShapeError(
                field_obj.name,
                "gauge-singlet chiral field is not a pure-quiver arrow",
            )

        source, target = _infer_endpoints(field_obj, non_singlet)
        labels = _expand_multiplicity_labels(field_obj.name, field_obj.multiplicity)
        for label in labels:
            if label in seen_labels:
                raise PureQuiverShapeError(
                    field_obj.name,
                    f"machine label {label!r} collides with an arrow from "
                    "an earlier field (either two fields share a name, or "
                    "a multiplicity expansion clashes with a literal name)",
                )
            seen_labels.add(label)
            arrows.append(
                Arrow(
                    label=label,
                    display_label=field_obj.name,
                    source=source,
                    target=target,
                    r_charge=field_obj.r_charge,
                )
            )
    return tuple(arrows)


def enumerate_cyclic_words(
    arrows: Iterable[Arrow],
    max_length: int,
) -> Mapping[int, tuple[CyclicWord, ...]]:
    """Enumerate canonical cyclic words up to `max_length`.

    Returns a dict keyed by length ℓ ∈ 1..max_length. Each value is the
    tuple of distinct cyclic-rotation classes of closed walks of that
    length, each represented by its lex-min rotation and ordered by that
    rotation (so the result is deterministic).
    """

    if max_length < 1:
        raise ValueError(f"max_length must be >= 1, got {max_length}")

    arrow_list = tuple(arrows)
    seen_labels: set[str] = set()
    for arrow in arrow_list:
        if arrow.label in seen_labels:
            raise ValueError(
                f"duplicate arrow label {arrow.label!r} in input; "
                "cyclic-word enumeration requires globally unique labels "
                "(extract_arrows enforces this; if you constructed Arrows "
                "by hand, deduplicate at the source)"
            )
        seen_labels.add(arrow.label)

    by_source: dict[str, list[Arrow]] = defaultdict(list)
    for arrow in arrow_list:
        by_source[arrow.source].append(arrow)

    nodes = sorted({arrow.source for arrow in arrow_list} | {arrow.target for arrow in arrow_list})

    result: dict[int, tuple[CyclicWord, ...]] = {}
    for length in range(1, max_length + 1):
        seen: set[tuple[str, ...]] = set()
        words: list[CyclicWord] = []
        for start in nodes:
            for walk in _closed_walks(by_source, start, length):
                canonical_labels = _canonical_rotation(tuple(a.label for a in walk))
                if canonical_labels in seen:
                    continue
                seen.add(canonical_labels)
                r_total = sum((a.r_charge for a in walk), Fraction(0))
                words.append(
                    CyclicWord(
                        arrows=canonical_labels,
                        length=length,
                        r_charge=r_total,
                    )
                )
        words.sort(key=lambda w: w.arrows)
        result[length] = tuple(words)
    return result


def _infer_endpoints(
    field_obj: Field,
    non_singlet: Mapping[str, "object"],
) -> tuple[str, str]:
    adjoint_nodes = [n for n, rep in non_singlet.items() if rep.name == "adjoint"]
    fund_nodes = [n for n, rep in non_singlet.items() if rep.name == "fundamental"]
    antifund_nodes = [n for n, rep in non_singlet.items() if rep.name == "antifundamental"]

    if adjoint_nodes and not fund_nodes and not antifund_nodes:
        if len(adjoint_nodes) != 1:
            raise PureQuiverShapeError(
                field_obj.name,
                f"expected exactly one adjoint node, got {sorted(adjoint_nodes)}",
            )
        node = adjoint_nodes[0]
        return node, node

    if not adjoint_nodes and len(fund_nodes) == 1 and len(antifund_nodes) == 1:
        source = antifund_nodes[0]
        target = fund_nodes[0]
        if source == target:
            raise PureQuiverShapeError(
                field_obj.name,
                f"fundamental and antifundamental on same node {source!r}",
            )
        return source, target

    raise PureQuiverShapeError(
        field_obj.name,
        "gauge_reps not a pure-quiver arrow "
        f"(adjoint={sorted(adjoint_nodes)}, fund={sorted(fund_nodes)}, "
        f"antifund={sorted(antifund_nodes)})",
    )


def _expand_multiplicity_labels(field_name: str, multiplicity: int) -> tuple[str, ...]:
    if multiplicity < 1:
        raise ValueError(f"multiplicity must be >= 1, got {multiplicity}")
    if multiplicity == 1:
        return (field_name,)
    return tuple(f"{field_name}[{i}]" for i in range(multiplicity))


def _closed_walks(
    by_source: Mapping[str, list[Arrow]],
    start: str,
    length: int,
) -> Iterator[tuple[Arrow, ...]]:
    """Yield all closed walks of exactly `length` arrows starting at `start`."""

    if length < 1:
        return

    def walk(node: str, depth: int, path: tuple[Arrow, ...]) -> Iterator[tuple[Arrow, ...]]:
        if depth == length:
            if node == start:
                yield path
            return
        for arrow in by_source.get(node, ()):
            yield from walk(arrow.target, depth + 1, path + (arrow,))

    yield from walk(start, 0, ())


def _canonical_rotation(labels: tuple[str, ...]) -> tuple[str, ...]:
    best = labels
    n = len(labels)
    for i in range(1, n):
        rotated = labels[i:] + labels[:i]
        if rotated < best:
            best = rotated
    return best


__all__ = [
    "Arrow",
    "CyclicWord",
    "PureQuiverShapeError",
    "enumerate_cyclic_words",
    "extract_arrows",
]
