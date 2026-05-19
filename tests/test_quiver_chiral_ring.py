"""Tests for quiver_chiral_ring step 1: Arrow/CyclicWord + extract + enumerate.

Phase 2a step 1 scope (design doc §14): no F-ideal saturation, no relation
matrix, no verdict yet. These tests pin the toy-quiver hand-checks from §11.1
and the multi-arrow expansion convention from §3.2.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from dualitycert.core.objects import Field, SuperpotentialTerm, Theory
from dualitycert.groups.su import adjoint, antifundamental, fundamental, su
from dualitycert.qft.quiver_chiral_ring import (
    Arrow,
    CyclicWord,
    PureQuiverShapeError,
    enumerate_cyclic_words,
    extract_arrows,
)


# ---------------------------------------------------------------------------
# Toy fixture (design doc §11.1)
# ---------------------------------------------------------------------------

NODE1_LABEL = "N1"
NODE2_LABEL = "N2"
TWO_THIRDS = Fraction(2, 3)


def _toy_theory(
    *,
    x_multiplicity: int = 1,
    y_multiplicity: int = 1,
    phi_multiplicity: int = 1,
    include_phi: bool = True,
    x_r_charge: Fraction = TWO_THIRDS,
    y_r_charge: Fraction = TWO_THIRDS,
    phi_r_charge: Fraction = TWO_THIRDS,
) -> Theory:
    """Build the §11.1 toy quiver: Phi (1->1), X (1->2), Y (2->1)."""

    n1 = su(3, label=NODE1_LABEL)
    n2 = su(3, label=NODE2_LABEL)

    fields = [
        Field(
            name="X",
            field_type="chiral multiplet",
            gauge_reps={NODE1_LABEL: antifundamental(), NODE2_LABEL: fundamental()},
            r_charge=x_r_charge,
            multiplicity=x_multiplicity,
        ),
        Field(
            name="Y",
            field_type="chiral multiplet",
            gauge_reps={NODE2_LABEL: antifundamental(), NODE1_LABEL: fundamental()},
            r_charge=y_r_charge,
            multiplicity=y_multiplicity,
        ),
    ]
    if include_phi:
        fields.append(
            Field(
                name="Phi",
                field_type="chiral multiplet",
                gauge_reps={NODE1_LABEL: adjoint()},
                r_charge=phi_r_charge,
                multiplicity=phi_multiplicity,
            )
        )
    return Theory(
        name="toy two-node pure quiver",
        gauge_nodes=(n1, n2),
        fields=tuple(fields),
        superpotential_terms=(
            SuperpotentialTerm(factors=(("Phi", 1), ("X", 1), ("Y", 1))),
        ),
    )


# ---------------------------------------------------------------------------
# extract_arrows
# ---------------------------------------------------------------------------

def test_extract_arrows_toy_quiver_basic():
    arrows = extract_arrows(_toy_theory())
    by_label = {a.label: a for a in arrows}
    assert set(by_label) == {"Phi", "X", "Y"}

    assert by_label["Phi"].source == NODE1_LABEL
    assert by_label["Phi"].target == NODE1_LABEL
    assert by_label["Phi"].is_loop

    assert by_label["X"].source == NODE1_LABEL
    assert by_label["X"].target == NODE2_LABEL

    assert by_label["Y"].source == NODE2_LABEL
    assert by_label["Y"].target == NODE1_LABEL

    assert all(a.r_charge == TWO_THIRDS for a in arrows)
    assert all(a.display_label == a.label for a in arrows)


def test_extract_arrows_multiplicity_one_uses_field_name():
    """Design doc §3.2: m=1 → machine label is Field.name (no [0] suffix)."""
    arrows = extract_arrows(_toy_theory(x_multiplicity=1))
    labels = {a.label for a in arrows}
    assert "X" in labels
    assert "X[0]" not in labels


def test_extract_arrows_multiplicity_two_expands_to_indexed_labels():
    """Design doc §3.2: m>1 → m arrows with labels f"{name}[{i}]", shared display_label."""
    arrows = extract_arrows(_toy_theory(x_multiplicity=2))
    x_copies = [a for a in arrows if a.display_label == "X"]
    assert len(x_copies) == 2
    assert {a.label for a in x_copies} == {"X[0]", "X[1]"}
    assert all(a.source == NODE1_LABEL and a.target == NODE2_LABEL for a in x_copies)
    assert all(a.r_charge == TWO_THIRDS for a in x_copies)
    assert all(a.display_label == "X" for a in x_copies)


def test_extract_arrows_multiplicity_three_three_distinct_arrows():
    arrows = extract_arrows(_toy_theory(x_multiplicity=3))
    x_copies = sorted(a.label for a in arrows if a.display_label == "X")
    assert x_copies == ["X[0]", "X[1]", "X[2]"]


def test_extract_arrows_rejects_gauge_singlet_field():
    """Pure-quiver fields must be arrows. Gauge singlets are NOT_APPLICABLE shape."""
    theory = Theory(
        name="toy + singlet",
        gauge_nodes=(su(3, label=NODE1_LABEL), su(3, label=NODE2_LABEL)),
        fields=(
            Field(
                name="X",
                field_type="chiral multiplet",
                gauge_reps={NODE1_LABEL: antifundamental(), NODE2_LABEL: fundamental()},
                r_charge=TWO_THIRDS,
            ),
            Field(
                name="S",
                field_type="chiral multiplet",
                gauge_reps={},
                r_charge=Fraction(1),
            ),
        ),
    )
    with pytest.raises(PureQuiverShapeError) as exc_info:
        extract_arrows(theory)
    assert exc_info.value.field_name == "S"


def test_extract_arrows_rejects_field_with_only_singlet_reps():
    """A gauge_reps dict that is non-empty but all-singlet still doesn't yield an arrow."""
    from dualitycert.core.objects import SINGLET

    theory = Theory(
        name="all-singlet field",
        gauge_nodes=(su(3, label=NODE1_LABEL), su(3, label=NODE2_LABEL)),
        fields=(
            Field(
                name="S",
                field_type="chiral multiplet",
                gauge_reps={NODE1_LABEL: SINGLET, NODE2_LABEL: SINGLET},
                r_charge=Fraction(1),
            ),
        ),
    )
    with pytest.raises(PureQuiverShapeError) as exc_info:
        extract_arrows(theory)
    assert exc_info.value.field_name == "S"


def test_extract_arrows_rejects_unknown_node_label_in_gauge_reps():
    """A typo'd node label in gauge_reps is caught against theory.gauge_nodes."""
    theory = Theory(
        name="phantom node ref",
        gauge_nodes=(su(3, label=NODE1_LABEL), su(3, label=NODE2_LABEL)),
        fields=(
            Field(
                name="ghost",
                field_type="chiral multiplet",
                gauge_reps={NODE1_LABEL: antifundamental(), "TYPO": fundamental()},
                r_charge=TWO_THIRDS,
            ),
        ),
    )
    with pytest.raises(PureQuiverShapeError) as exc_info:
        extract_arrows(theory)
    assert exc_info.value.field_name == "ghost"
    assert "TYPO" in str(exc_info.value)


def test_extract_arrows_rejects_duplicate_field_name():
    """Two fields with the same machine label collide — must error, not silently merge."""
    theory = Theory(
        name="duplicate-name quiver",
        gauge_nodes=(su(3, label=NODE1_LABEL), su(3, label=NODE2_LABEL)),
        fields=(
            Field(
                name="X",
                field_type="chiral multiplet",
                gauge_reps={NODE1_LABEL: antifundamental(), NODE2_LABEL: fundamental()},
                r_charge=TWO_THIRDS,
            ),
            Field(
                name="X",
                field_type="chiral multiplet",
                gauge_reps={NODE2_LABEL: antifundamental(), NODE1_LABEL: fundamental()},
                r_charge=TWO_THIRDS,
            ),
        ),
    )
    with pytest.raises(PureQuiverShapeError) as exc_info:
        extract_arrows(theory)
    assert "collides" in str(exc_info.value)


def test_extract_arrows_rejects_multiplicity_expansion_colliding_with_literal_name():
    """Field X (mult=2) generates labels X[0], X[1]; a separate literal field 'X[0]' must error."""
    theory = Theory(
        name="expansion clash",
        gauge_nodes=(su(3, label=NODE1_LABEL), su(3, label=NODE2_LABEL)),
        fields=(
            Field(
                name="X",
                field_type="chiral multiplet",
                gauge_reps={NODE1_LABEL: antifundamental(), NODE2_LABEL: fundamental()},
                r_charge=TWO_THIRDS,
                multiplicity=2,
            ),
            Field(
                name="X[0]",
                field_type="chiral multiplet",
                gauge_reps={NODE2_LABEL: antifundamental(), NODE1_LABEL: fundamental()},
                r_charge=TWO_THIRDS,
            ),
        ),
    )
    with pytest.raises(PureQuiverShapeError) as exc_info:
        extract_arrows(theory)
    assert "collides" in str(exc_info.value)


def test_extract_arrows_rejects_double_fundamental():
    """A field with fundamental at TWO nodes is not a pure-quiver arrow."""
    theory = Theory(
        name="broken",
        gauge_nodes=(su(3, label=NODE1_LABEL), su(3, label=NODE2_LABEL)),
        fields=(
            Field(
                name="bad",
                field_type="chiral multiplet",
                gauge_reps={NODE1_LABEL: fundamental(), NODE2_LABEL: fundamental()},
                r_charge=TWO_THIRDS,
            ),
        ),
    )
    with pytest.raises(PureQuiverShapeError) as exc_info:
        extract_arrows(theory)
    assert exc_info.value.field_name == "bad"


def test_extract_arrows_rejects_adjoint_plus_fundamental():
    """A field carrying adjoint AND a fundamental is not a pure-quiver arrow."""
    theory = Theory(
        name="broken",
        gauge_nodes=(su(3, label=NODE1_LABEL), su(3, label=NODE2_LABEL)),
        fields=(
            Field(
                name="weird",
                field_type="chiral multiplet",
                gauge_reps={NODE1_LABEL: adjoint(), NODE2_LABEL: fundamental()},
                r_charge=TWO_THIRDS,
            ),
        ),
    )
    with pytest.raises(PureQuiverShapeError):
        extract_arrows(theory)


def test_extract_arrows_node_keys_match_gauge_node_labels():
    """source/target use the same string labels as Theory.gauge_nodes labels."""
    arrows = extract_arrows(_toy_theory())
    labels = {NODE1_LABEL, NODE2_LABEL}
    for a in arrows:
        assert a.source in labels
        assert a.target in labels


# ---------------------------------------------------------------------------
# enumerate_cyclic_words — toy quiver hand-checks (design doc §11.1)
# ---------------------------------------------------------------------------

def _enumerate_toy(max_length: int = 4):
    return enumerate_cyclic_words(extract_arrows(_toy_theory()), max_length)


def test_enumerate_cyclic_words_returns_block_per_length():
    words = _enumerate_toy(max_length=4)
    assert set(words.keys()) == {1, 2, 3, 4}


def test_enumerate_length_1_only_self_loop():
    """At length 1 only the adjoint self-loop Phi closes; X and Y don't."""
    words = _enumerate_toy(max_length=1)[1]
    assert len(words) == 1
    (w,) = words
    assert w.arrows == ("Phi",)
    assert w.length == 1
    assert w.r_charge == TWO_THIRDS


def test_enumerate_length_2_has_phi_phi_and_xy():
    words = _enumerate_toy(max_length=2)[2]
    arrow_tuples = {w.arrows for w in words}
    assert arrow_tuples == {("Phi", "Phi"), ("X", "Y")}
    for w in words:
        assert w.length == 2
        assert w.r_charge == Fraction(4, 3)


def test_enumerate_length_3_collapses_phi_x_y_rotations():
    """{(Phi,X,Y), (X,Y,Phi), (Y,Phi,X)} are one cyclic class. Canonical = (Phi,X,Y)."""
    words = _enumerate_toy(max_length=3)[3]
    arrow_tuples = {w.arrows for w in words}
    assert arrow_tuples == {("Phi", "Phi", "Phi"), ("Phi", "X", "Y")}
    for w in words:
        assert w.length == 3
        assert w.r_charge == Fraction(2, 1)


def test_enumerate_length_4_three_classes():
    """Hand-checked: PhiPhiPhiPhi, {XYPhiPhi rotations}, {XYXY rotations}."""
    words = _enumerate_toy(max_length=4)[4]
    arrow_tuples = {w.arrows for w in words}
    assert arrow_tuples == {
        ("Phi", "Phi", "Phi", "Phi"),
        ("Phi", "Phi", "X", "Y"),
        ("X", "Y", "X", "Y"),
    }
    for w in words:
        assert w.length == 4
        assert w.r_charge == Fraction(8, 3)


def test_enumerate_canonical_is_lex_min_rotation():
    """The PhiXY class must canonicalise to (Phi, X, Y), not (X, Y, Phi) or (Y, Phi, X)."""
    words = _enumerate_toy(max_length=3)[3]
    phi_x_y = next(w for w in words if set(w.arrows) == {"Phi", "X", "Y"})
    assert phi_x_y.arrows == ("Phi", "X", "Y")


def test_enumerate_words_within_block_sorted_deterministically():
    """Words at each length come back sorted by their canonical tuple."""
    words = _enumerate_toy(max_length=4)
    for length, block in words.items():
        assert list(block) == sorted(block, key=lambda w: w.arrows)


def test_enumerate_rejects_max_length_zero():
    with pytest.raises(ValueError):
        enumerate_cyclic_words(extract_arrows(_toy_theory()), 0)


# ---------------------------------------------------------------------------
# Multi-arrow expansion in enumeration (design doc §3.2 + §11.1 multi-arrow note)
# ---------------------------------------------------------------------------

def test_enumerate_multi_arrow_x_treats_copies_independently():
    """X with multiplicity=2 → labels X[0], X[1] each form their own cyclic word with Y."""
    arrows = extract_arrows(_toy_theory(x_multiplicity=2))
    words = enumerate_cyclic_words(arrows, max_length=2)
    arrow_tuples = {w.arrows for w in words[2]}
    assert arrow_tuples == {
        ("Phi", "Phi"),
        ("X[0]", "Y"),
        ("X[1]", "Y"),
    }


def test_enumerate_multi_arrow_y_multiplicity_two():
    """Symmetric test: Y multiplicity=2 doubles the XY-class count."""
    arrows = extract_arrows(_toy_theory(y_multiplicity=2))
    words = enumerate_cyclic_words(arrows, max_length=2)
    arrow_tuples = {w.arrows for w in words[2]}
    assert arrow_tuples == {
        ("Phi", "Phi"),
        ("X", "Y[0]"),
        ("X", "Y[1]"),
    }


def test_enumerate_multi_arrow_both_x_and_y_multiplicity_two():
    """Both X and Y mult=2 ⇒ 4 distinct length-2 XY-style classes."""
    arrows = extract_arrows(
        _toy_theory(x_multiplicity=2, y_multiplicity=2, include_phi=False)
    )
    words = enumerate_cyclic_words(arrows, max_length=2)
    arrow_tuples = {w.arrows for w in words[2]}
    assert arrow_tuples == {
        ("X[0]", "Y[0]"),
        ("X[0]", "Y[1]"),
        ("X[1]", "Y[0]"),
        ("X[1]", "Y[1]"),
    }


# ---------------------------------------------------------------------------
# Disconnected / no-loop edge cases
# ---------------------------------------------------------------------------

def test_enumerate_no_closed_walks_when_only_one_directed_edge():
    """Single arrow X (1->2) alone has no closed walks: every length returns ()."""
    theory = Theory(
        name="one-way",
        gauge_nodes=(su(3, label=NODE1_LABEL), su(3, label=NODE2_LABEL)),
        fields=(
            Field(
                name="X",
                field_type="chiral multiplet",
                gauge_reps={NODE1_LABEL: antifundamental(), NODE2_LABEL: fundamental()},
                r_charge=TWO_THIRDS,
            ),
        ),
    )
    arrows = extract_arrows(theory)
    words = enumerate_cyclic_words(arrows, max_length=4)
    assert all(block == () for block in words.values())


def test_enumerate_rejects_duplicate_arrow_label_input():
    """enumerate_cyclic_words is a public API; hand-built Arrows with duplicate
    labels must be rejected at the entry point, not silently merged downstream."""
    a1 = Arrow(label="X", display_label="X", source=NODE1_LABEL, target=NODE2_LABEL,
               r_charge=TWO_THIRDS)
    a2 = Arrow(label="X", display_label="X", source=NODE2_LABEL, target=NODE1_LABEL,
               r_charge=TWO_THIRDS)
    with pytest.raises(ValueError) as exc_info:
        enumerate_cyclic_words((a1, a2), max_length=2)
    assert "duplicate" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# CyclicWord invariants
# ---------------------------------------------------------------------------

def test_cyclic_word_rejects_length_arrows_mismatch():
    with pytest.raises(ValueError):
        CyclicWord(arrows=("X", "Y"), length=3, r_charge=Fraction(4, 3))


def test_cyclic_word_rejects_non_canonical_rotation():
    """(X, Y, Phi) is not lex-min — (Phi, X, Y) is. Must reject the non-canonical form."""
    with pytest.raises(ValueError) as exc_info:
        CyclicWord(arrows=("X", "Y", "Phi"), length=3, r_charge=Fraction(2))
    assert "canonical" in str(exc_info.value).lower()


def test_cyclic_word_accepts_canonical_form():
    """Construction with the canonical lex-min rotation must succeed."""
    w = CyclicWord(arrows=("Phi", "X", "Y"), length=3, r_charge=Fraction(2))
    assert w.arrows == ("Phi", "X", "Y")
    assert w.length == 3


def test_cyclic_word_rejects_length_zero():
    """The empty word doesn't correspond to a single-trace operator and is rejected."""
    with pytest.raises(ValueError) as exc_info:
        CyclicWord(arrows=(), length=0, r_charge=Fraction(0))
    assert ">= 1" in str(exc_info.value)


def test_cyclic_word_coerces_list_arrows_to_tuple():
    """Accept list input but store as tuple so frozen=True / hashability hold."""
    w = CyclicWord(arrows=["Phi"], length=1, r_charge=TWO_THIRDS)
    assert isinstance(w.arrows, tuple)
    assert w.arrows == ("Phi",)
    # Must be hashable now — would raise TypeError if arrows were still a list.
    assert hash(w) == hash(CyclicWord(arrows=("Phi",), length=1, r_charge=TWO_THIRDS))


def test_enumerate_pure_adjoint_loop_powers():
    """Single self-loop Phi: at each length ℓ there's exactly one class (Phi^ℓ)."""
    theory = Theory(
        name="single adjoint",
        gauge_nodes=(su(3, label=NODE1_LABEL),),
        fields=(
            Field(
                name="Phi",
                field_type="chiral multiplet",
                gauge_reps={NODE1_LABEL: adjoint()},
                r_charge=TWO_THIRDS,
            ),
        ),
    )
    arrows = extract_arrows(theory)
    words = enumerate_cyclic_words(arrows, max_length=4)
    for length, block in words.items():
        assert len(block) == 1
        (w,) = block
        assert w.arrows == tuple(["Phi"] * length)
        assert w.r_charge == TWO_THIRDS * length
