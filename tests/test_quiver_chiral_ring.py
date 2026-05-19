"""Tests for quiver_chiral_ring steps 1-4.

Step 1: Arrow/CyclicWord + extract + enumerate.
Step 2: cyclic_derivative of the superpotential.
Step 3: validate_w_terms, RelationMatrix, build_relation_matrix,
        quotient_dimensions.
Step 4: bounded_chiral_ring_consistency_check (verdict + registry).

These tests pin the toy-quiver hand-checks from §11.1, the multi-arrow
expansion convention from §3.2, the cyclic-derivative definition from §2,
the two-sided context multiplication of §5.2, W-term well-formedness (P5
from §4) at the build_relation_matrix entry point, and the §7 verdict
semantics including the §11.3 failure fixtures.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from dualitycert.core.objects import Field, SuperpotentialTerm, Theory
from dualitycert.groups.su import adjoint, antifundamental, fundamental, su
from dualitycert.core.objects import DualityClaim
from dualitycert.core.obligations import ObligationResult
from dualitycert.core.status import Status
from dualitycert.qft.quiver_chiral_ring import (
    Arrow,
    CyclicWord,
    PureQuiverShapeError,
    RelationMatrix,
    WTermShapeError,
    bounded_chiral_ring_consistency_check,
    build_relation_matrix,
    cyclic_derivative,
    enumerate_cyclic_words,
    extract_arrows,
    quotient_dimensions,
    validate_w_terms,
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


# ---------------------------------------------------------------------------
# cyclic_derivative — toy quiver hand-checks (design doc §11.1)
# ---------------------------------------------------------------------------

def _toy_arrows_by_label() -> dict[str, Arrow]:
    return {a.label: a for a in extract_arrows(_toy_theory())}


def test_cyclic_derivative_d_phi_w_equals_xy():
    """W = Tr(Phi X Y) ⇒ ∂_Phi W = X·Y."""
    arrows = _toy_arrows_by_label()
    theory = _toy_theory()
    result = cyclic_derivative(theory.superpotential_terms, arrows["Phi"])
    assert result == {("X", "Y"): Fraction(1)}


def test_cyclic_derivative_d_x_w_equals_y_phi():
    """W = Tr(Phi X Y) ⇒ ∂_X W = Y·Phi."""
    arrows = _toy_arrows_by_label()
    theory = _toy_theory()
    result = cyclic_derivative(theory.superpotential_terms, arrows["X"])
    assert result == {("Y", "Phi"): Fraction(1)}


def test_cyclic_derivative_d_y_w_equals_phi_x():
    """W = Tr(Phi X Y) ⇒ ∂_Y W = Phi·X."""
    arrows = _toy_arrows_by_label()
    theory = _toy_theory()
    result = cyclic_derivative(theory.superpotential_terms, arrows["Y"])
    assert result == {("Phi", "X"): Fraction(1)}


def test_cyclic_derivative_open_path_endpoints_match_spec():
    """∂_X W is a path from target(X) to source(X) (design doc §2)."""
    arrows = _toy_arrows_by_label()
    # X: source = N1, target = N2. ∂_X W should be a path N2 → N1.
    # The toy result is (Y, Phi). Y goes N2 → N1; Phi goes N1 → N1.
    # Concatenation source(Y) = N2 = target(X), target(Phi) = N1 = source(X). ✓
    result = cyclic_derivative(_toy_theory().superpotential_terms, arrows["X"])
    (path,) = result.keys()
    assert path == ("Y", "Phi")
    assert arrows[path[0]].source == arrows["X"].target
    assert arrows[path[-1]].target == arrows["X"].source


# ---------------------------------------------------------------------------
# cyclic_derivative — edge cases and properties
# ---------------------------------------------------------------------------

def test_cyclic_derivative_empty_w_returns_empty():
    arrows = _toy_arrows_by_label()
    assert cyclic_derivative((), arrows["Phi"]) == {}


def test_cyclic_derivative_arrow_absent_from_w():
    """If the arrow doesn't appear in any W term, the result is empty."""
    theory = _toy_theory()
    other = Arrow(label="Z", display_label="Z", source=NODE1_LABEL,
                  target=NODE1_LABEL, r_charge=TWO_THIRDS)
    assert cyclic_derivative(theory.superpotential_terms, other) == {}


def test_cyclic_derivative_respects_term_coefficient():
    """Coefficient on the W term flows through to the derivative."""
    arrows = _toy_arrows_by_label()
    W = (SuperpotentialTerm(
        factors=(("Phi", 1), ("X", 1), ("Y", 1)),
        coefficient=Fraction(7, 3),
    ),)
    assert cyclic_derivative(W, arrows["Phi"]) == {("X", "Y"): Fraction(7, 3)}


def test_cyclic_derivative_tr_phi_cubed_accumulates_to_same_path():
    """W = Tr(Phi^3): all three Phi positions produce the SAME open path
    (Phi, Phi) since the rotation just shifts indistinguishable letters.
    The derivative must therefore have coefficient 3, not three distinct
    entries of coefficient 1. Pins the `result.get(path, 0) + c` accumulation
    branch within a single term."""
    theory = Theory(
        name="phi-cubed",
        gauge_nodes=(su(3, label=NODE1_LABEL),),
        fields=(
            Field(name="Phi", field_type="chiral multiplet",
                  gauge_reps={NODE1_LABEL: adjoint()}, r_charge=Fraction(2, 3)),
        ),
        superpotential_terms=(SuperpotentialTerm(factors=(("Phi", 3),)),),
    )
    arrows = {a.label: a for a in extract_arrows(theory)}
    result = cyclic_derivative(theory.superpotential_terms, arrows["Phi"])
    assert result == {("Phi", "Phi"): Fraction(3)}


def test_cyclic_derivative_multiple_occurrences_sum_independently():
    """W = Phi·Phi·X has two Phi positions; ∂_Phi sums both rotations."""
    n1 = su(3, label=NODE1_LABEL)
    n2 = su(3, label=NODE2_LABEL)
    fields = (
        Field(name="Phi", field_type="chiral multiplet",
              gauge_reps={NODE1_LABEL: adjoint()}, r_charge=TWO_THIRDS),
        Field(name="X", field_type="chiral multiplet",
              gauge_reps={NODE1_LABEL: antifundamental(), NODE2_LABEL: fundamental()},
              r_charge=TWO_THIRDS),
        Field(name="Xback", field_type="chiral multiplet",
              gauge_reps={NODE2_LABEL: antifundamental(), NODE1_LABEL: fundamental()},
              r_charge=TWO_THIRDS),
    )
    # Note: W = Tr(Phi·Phi·X·Xback) closes: 1→1→1→2→1
    W = (SuperpotentialTerm(factors=(("Phi", 2), ("X", 1), ("Xback", 1))),)
    theory = Theory(name="phi-phi-X-Xback", gauge_nodes=(n1, n2), fields=fields,
                    superpotential_terms=W)
    arrows = {a.label: a for a in extract_arrows(theory)}
    # Positions of Phi in flat factors: 0 and 1.
    # i=0: open_path = (Phi, X, Xback)
    # i=1: open_path = (X, Xback, Phi)
    expected = {
        ("Phi", "X", "Xback"): Fraction(1),
        ("X", "Xback", "Phi"): Fraction(1),
    }
    assert cyclic_derivative(W, arrows["Phi"]) == expected


def test_cyclic_derivative_cancellation_drops_zero_entries():
    """+1·Tr(Phi X Y) - 1·Tr(Phi X Y) gives ∂_Phi = 0, returned as empty dict."""
    arrows = _toy_arrows_by_label()
    W = (
        SuperpotentialTerm(factors=(("Phi", 1), ("X", 1), ("Y", 1)),
                           coefficient=Fraction(1)),
        SuperpotentialTerm(factors=(("Phi", 1), ("X", 1), ("Y", 1)),
                           coefficient=Fraction(-1)),
    )
    assert cyclic_derivative(W, arrows["Phi"]) == {}


def test_cyclic_derivative_multiple_terms_accumulate_into_same_path():
    """Two distinct terms whose ∂_Phi share a path → coefficients add."""
    arrows = _toy_arrows_by_label()
    W = (
        SuperpotentialTerm(factors=(("Phi", 1), ("X", 1), ("Y", 1)),
                           coefficient=Fraction(2)),
        SuperpotentialTerm(factors=(("Phi", 1), ("X", 1), ("Y", 1)),
                           coefficient=Fraction(3)),
    )
    assert cyclic_derivative(W, arrows["Phi"]) == {("X", "Y"): Fraction(5)}


# ---------------------------------------------------------------------------
# cyclic_derivative on dP_0 (design doc §11.1 lookahead, exercises multi-arrow)
# ---------------------------------------------------------------------------

def test_cyclic_derivative_on_dp0_pure_quiver_builder():
    """dP_0 W = ε_{abc} X01[a] X12[b] X20[c]. ∂_{X01[0]} W picks the (a=0)
    permutations: (0,1,2) and (0,2,1) with signs +1 and -1.

    Resulting open path (length 2, target=node 1 → source=node 0):
        +1 · (X12[1], X20[2])
        -1 · (X12[2], X20[1])
    """
    from fractions import Fraction
    from dualitycert.qft.pure_quiver_builder import (
        arrow_names,
        build_pure_quiver,
        dp0_superpotential,
    )

    r = Fraction(2, 3)
    names_01 = arrow_names(0, 1, 3)
    names_12 = arrow_names(1, 2, 3)
    names_20 = arrow_names(2, 0, 3)
    theory = build_pure_quiver(
        ranks=(3, 3, 3),
        arrows={
            (0, 1): [r, r, r],
            (1, 2): [r, r, r],
            (2, 0): [r, r, r],
        },
        superpotential=dp0_superpotential(names_01, names_12, names_20),
    )
    arrows_by_label = {a.label: a for a in extract_arrows(theory)}
    x01_0 = arrows_by_label["X01[0]"]
    result = cyclic_derivative(theory.superpotential_terms, x01_0)
    assert result == {
        ("X12[1]", "X20[2]"): Fraction(1),
        ("X12[2]", "X20[1]"): Fraction(-1),
    }


def test_cyclic_derivative_endpoint_check_for_dp0():
    """For each X01[a], the open path runs from target=node 1 to source=node 0."""
    from fractions import Fraction
    from dualitycert.qft.pure_quiver_builder import (
        arrow_names,
        build_pure_quiver,
        dp0_superpotential,
    )

    r = Fraction(2, 3)
    names_01 = arrow_names(0, 1, 3)
    names_12 = arrow_names(1, 2, 3)
    names_20 = arrow_names(2, 0, 3)
    theory = build_pure_quiver(
        ranks=(3, 3, 3),
        arrows={(0, 1): [r] * 3, (1, 2): [r] * 3, (2, 0): [r] * 3},
        superpotential=dp0_superpotential(names_01, names_12, names_20),
    )
    arrows_by_label = {a.label: a for a in extract_arrows(theory)}
    x01_0 = arrows_by_label["X01[0]"]
    result = cyclic_derivative(theory.superpotential_terms, x01_0)
    for path in result:
        first = arrows_by_label[path[0]]
        last = arrows_by_label[path[-1]]
        assert first.source == x01_0.target  # path starts at target(X01[0])
        assert last.target == x01_0.source   # path ends at source(X01[0])


# ===========================================================================
# Step 3: validate_w_terms (P5)
# ===========================================================================

def test_validate_w_terms_accepts_toy_w():
    """The toy fixture W = Tr(Phi X Y) is a closed monomial walk and validates."""
    theory = _toy_theory()
    validate_w_terms(extract_arrows(theory), theory.superpotential_terms)


def test_validate_w_terms_rejects_unknown_factor_label():
    arrows = extract_arrows(_toy_theory())
    bogus = (SuperpotentialTerm(factors=(("Phi", 1), ("MISSING", 1), ("Y", 1))),)
    with pytest.raises(WTermShapeError) as exc_info:
        validate_w_terms(arrows, bogus)
    assert "MISSING" in str(exc_info.value)


def test_validate_w_terms_rejects_non_composable_term():
    """W = X * Phi: X ends at N2 but Phi starts at N1, so not composable."""
    arrows = extract_arrows(_toy_theory())
    bogus = (SuperpotentialTerm(factors=(("X", 1), ("Phi", 1))),)
    with pytest.raises(WTermShapeError) as exc_info:
        validate_w_terms(arrows, bogus)
    assert "compose" in str(exc_info.value) or "source" in str(exc_info.value)


def test_validate_w_terms_rejects_non_closed_term():
    """W = X alone is composable trivially but not closed: target(X) != source(X)."""
    arrows = extract_arrows(_toy_theory())
    bogus = (SuperpotentialTerm(factors=(("X", 1),)),)
    with pytest.raises(WTermShapeError):
        validate_w_terms(arrows, bogus)


def test_validate_w_terms_rejects_empty_term():
    """A term with no factors is shape-invalid."""
    # SuperpotentialTerm itself accepts factors=() — guard at validate level.
    bogus = (SuperpotentialTerm(factors=()),)
    with pytest.raises(WTermShapeError):
        validate_w_terms(extract_arrows(_toy_theory()), bogus)


def test_build_relation_matrix_runs_validate_defensively():
    """build_relation_matrix must call validate_w_terms before doing work."""
    arrows = extract_arrows(_toy_theory())
    bogus = (SuperpotentialTerm(factors=(("Phi", 1), ("X", 1), ("MISSING", 1))),)
    with pytest.raises(WTermShapeError):
        build_relation_matrix(arrows, bogus, max_length=3)


# ===========================================================================
# Step 3: build_relation_matrix — toy hand-checks (design doc §5.2 / §11.1)
# ===========================================================================

def _toy_relation_matrices(max_length=4, r_graded=True):
    theory = _toy_theory()
    arrows = extract_arrows(theory)
    return build_relation_matrix(arrows, theory.superpotential_terms,
                                 max_length=max_length, r_graded=r_graded)


def test_build_relation_matrix_toy_l1_no_relations():
    """Length 1: basis {Phi}, no generators of length <= 1 ⇒ 0 rows."""
    mats = _toy_relation_matrices(max_length=4, r_graded=True)
    m1 = mats[(1, Fraction(2, 3))]
    assert m1.num_rows == 0
    assert m1.num_cols == 1
    assert m1.column_basis == (("Phi",),)
    assert m1.rank == 0
    assert m1.quotient_dimension == 1


def test_build_relation_matrix_toy_l2_kills_xy():
    """Length 2: basis {PhiPhi, XY}. Only g_Phi has length-0 (empty) context
    from N1 to N1 (Phi is a self-loop), giving one row: 0*PhiPhi + 1*XY = 0."""
    mats = _toy_relation_matrices(max_length=4, r_graded=True)
    m2 = mats[(2, Fraction(4, 3))]
    assert m2.column_basis == (("Phi", "Phi"), ("X", "Y"))
    assert m2.num_rows == 1
    assert m2.rows == ((Fraction(0), Fraction(1)),)
    assert m2.rank == 1
    assert m2.quotient_dimension == 1  # PhiPhi survives


def test_build_relation_matrix_toy_l3_three_redundant_rows_kill_phixy():
    """Length 3: basis {Phi^3, PhiXY}. All three generators (g_Phi context Phi,
    g_X context X, g_Y context Y) contribute one row each, all proportional
    to PhiXY = 0. Rank 1, dim Q = 1 (Phi^3 survives)."""
    mats = _toy_relation_matrices(max_length=4, r_graded=True)
    m3 = mats[(3, Fraction(2))]
    assert m3.column_basis == (("Phi", "Phi", "Phi"), ("Phi", "X", "Y"))
    assert m3.num_rows == 3
    for row in m3.rows:
        assert row == (Fraction(0), Fraction(1))
    assert m3.rank == 1
    assert m3.quotient_dimension == 1


def test_build_relation_matrix_toy_l4_partial_redundancy():
    """Length 4: basis {Phi^4, PhiPhiXY, XYXY}. Four generators (g_Phi has
    2 contexts of length 2: PhiPhi, XY; g_X has 1 context of length 2: PhiX;
    g_Y has 1 context of length 2: YPhi). Three of the four rows land on
    PhiPhiXY (duplicates), one on XYXY. Rank 2, dim Q = 1."""
    mats = _toy_relation_matrices(max_length=4, r_graded=True)
    m4 = mats[(4, Fraction(8, 3))]
    assert m4.column_basis == (
        ("Phi", "Phi", "Phi", "Phi"),
        ("Phi", "Phi", "X", "Y"),
        ("X", "Y", "X", "Y"),
    )
    assert m4.num_rows == 4
    # Three rows must be (0, 1, 0); one must be (0, 0, 1). Order not pinned.
    sorted_rows = sorted(m4.rows)
    assert sorted_rows == sorted([
        (Fraction(0), Fraction(1), Fraction(0)),
        (Fraction(0), Fraction(1), Fraction(0)),
        (Fraction(0), Fraction(1), Fraction(0)),
        (Fraction(0), Fraction(0), Fraction(1)),
    ])
    assert m4.rank == 2
    assert m4.quotient_dimension == 1


def test_quotient_dimensions_toy_only_adjoint_power_survives_each_block():
    """End-to-end: at every length 1..4 only the pure adjoint cyclic word
    Phi^ℓ survives the F-ideal quotient (every cyclic word containing both
    X and Y has either XY, YPhi, or PhiX as a contiguous substring, all of
    which are killed by the F-relations)."""
    dims = quotient_dimensions(
        extract_arrows(_toy_theory()),
        _toy_theory().superpotential_terms,
        max_length=4,
    )
    assert dims == {
        (1, Fraction(2, 3)): 1,
        (2, Fraction(4, 3)): 1,
        (3, Fraction(2, 1)): 1,
        (4, Fraction(8, 3)): 1,
    }


def test_quotient_dimensions_toy_length_only_matches_r_graded():
    """For the toy every cyclic word at length ℓ has R = 2ℓ/3, so the
    r_graded blocks coincide with the length-only blocks 1:1."""
    arrows = extract_arrows(_toy_theory())
    W = _toy_theory().superpotential_terms
    r_dims = quotient_dimensions(arrows, W, max_length=4, r_graded=True)
    l_dims = quotient_dimensions(arrows, W, max_length=4, r_graded=False)
    assert {length for length, _ in r_dims} == {length for length, _ in l_dims}
    # Same per-length total
    for length in range(1, 5):
        r_total = sum(v for (l, _), v in r_dims.items() if l == length)
        l_total = sum(v for (l, _), v in l_dims.items() if l == length)
        assert r_total == l_total


def test_build_relation_matrix_block_key_shape_depends_on_r_graded():
    """r_graded=True ⇒ blocks (length, Fraction); r_graded=False ⇒ (length, None)."""
    arrows = extract_arrows(_toy_theory())
    W = _toy_theory().superpotential_terms
    r_mats = build_relation_matrix(arrows, W, max_length=2, r_graded=True)
    l_mats = build_relation_matrix(arrows, W, max_length=2, r_graded=False)
    assert all(isinstance(k[1], Fraction) for k in r_mats)
    assert all(k[1] is None for k in l_mats)


# ===========================================================================
# Step 3: empty W and ablation
# ===========================================================================

def test_build_relation_matrix_with_empty_w_returns_all_basis():
    """No superpotential ⇒ zero relations ⇒ quotient = full basis."""
    theory = Theory(
        name="toy no W",
        gauge_nodes=_toy_theory().gauge_nodes,
        fields=_toy_theory().fields,
        superpotential_terms=(),
    )
    arrows = extract_arrows(theory)
    dims = quotient_dimensions(arrows, (), max_length=3)
    # Expected: each block dim equals the basis size from step 1.
    # Length 1: {Phi} → 1
    # Length 2: {PhiPhi, XY} → 2
    # Length 3: {Phi^3, PhiXY} → 2
    assert sum(dims.values()) == 1 + 2 + 2


def test_build_relation_matrix_drops_w_term_that_lifts_phixy():
    """W = Tr(Phi^3) (only) leaves XY untouched at length 2. Basis {PhiPhi, XY}.
    The only generator is g_Phi = ∂_Phi Tr(Phi^3) = 3*Phi*Phi (length 2, loop
    at N1). With empty context this kills PhiPhi (coeff 3), not XY. dim Q = 1."""
    theory = _toy_theory()
    # Override W to Tr(Phi^3)
    W = (SuperpotentialTerm(factors=(("Phi", 3),)),)
    arrows = extract_arrows(theory)
    mats = build_relation_matrix(arrows, W, max_length=2, r_graded=True)
    m2 = mats[(2, Fraction(4, 3))]
    assert m2.column_basis == (("Phi", "Phi"), ("X", "Y"))
    assert m2.num_rows == 1
    assert m2.rows == ((Fraction(3), Fraction(0)),)  # kills PhiPhi, not XY
    assert m2.quotient_dimension == 1


# ===========================================================================
# Step 3: RelationMatrix rank (Fraction Gaussian elim)
# ===========================================================================

def test_relation_matrix_rank_independent_rows():
    m = RelationMatrix(
        block=(2, Fraction(4, 3)),
        column_basis=(("a",), ("b",)),
        rows=(
            (Fraction(1), Fraction(0)),
            (Fraction(0), Fraction(1)),
        ),
    )
    assert m.rank == 2
    assert m.quotient_dimension == 0


def test_relation_matrix_rank_duplicate_rows():
    m = RelationMatrix(
        block=(2, None),
        column_basis=(("a",), ("b",)),
        rows=(
            (Fraction(1), Fraction(2)),
            (Fraction(2), Fraction(4)),  # multiple of the first
            (Fraction(3), Fraction(6)),
        ),
    )
    assert m.rank == 1
    assert m.quotient_dimension == 1


def test_relation_matrix_rank_zero_rows():
    m = RelationMatrix(
        block=(1, None),
        column_basis=(("a",),),
        rows=(),
    )
    assert m.rank == 0
    assert m.quotient_dimension == 1


def test_relation_matrix_rank_with_fractions():
    """Rank computation handles non-integer pivots exactly."""
    m = RelationMatrix(
        block=(2, None),
        column_basis=(("a",), ("b",), ("c",)),
        rows=(
            (Fraction(1, 3), Fraction(2, 5), Fraction(0)),
            (Fraction(2, 3), Fraction(4, 5), Fraction(0)),  # 2x the first
            (Fraction(0), Fraction(0), Fraction(7, 11)),
        ),
    )
    assert m.rank == 2
    assert m.quotient_dimension == 1


def test_relation_matrix_rejects_row_width_mismatch():
    """Row length must equal column_basis length — drop guarantees rank()."""
    with pytest.raises(ValueError) as exc_info:
        RelationMatrix(
            block=(2, None),
            column_basis=(("a",), ("b",)),
            rows=((Fraction(1), Fraction(0), Fraction(0)),),  # 3 entries, basis is 2 cols
        )
    assert "length" in str(exc_info.value).lower()


def test_relation_matrix_coerces_lists_to_tuples():
    """List inputs accepted but stored as tuples so frozen=True / hash() hold."""
    m = RelationMatrix(
        block=(1, None),
        column_basis=[("a",), ("b",)],
        rows=[[Fraction(1), Fraction(0)], [Fraction(0), Fraction(1)]],
    )
    assert isinstance(m.column_basis, tuple)
    assert isinstance(m.rows, tuple)
    assert all(isinstance(row, tuple) for row in m.rows)
    # Hashable now (would raise TypeError if lists slipped through).
    assert hash(m) == hash(RelationMatrix(
        block=(1, None),
        column_basis=(("a",), ("b",)),
        rows=((Fraction(1), Fraction(0)), (Fraction(0), Fraction(1))),
    ))


def test_relation_matrix_coerces_nested_lists_in_column_basis():
    """The inner cyclic-word tuples must also be coerced — otherwise
    column_basis=[["a"]] keeps an inner list and hash(m) still raises."""
    m = RelationMatrix(
        block=(1, None),
        column_basis=[["a"], ["b"]],  # both layers are lists
        rows=[[Fraction(1), Fraction(0)]],
    )
    assert all(isinstance(col, tuple) for col in m.column_basis)
    # Must not raise — would TypeError if any inner list slipped through.
    hash(m)


# ===========================================================================
# Step 3 regression: mass term (n=0 generator dispatch)
# ===========================================================================

def test_build_relation_matrix_mass_term_kills_phi_at_all_lengths():
    """W = Tr(Phi) with R(Phi)=2 is a legitimate adjoint mass term.
    ∂_Phi W = identity at the node (a length-0 generator). The F-relation
    says e_v = 0, which kills every cyclic word at that node at every
    positive length. Without the n=0 dispatch fix the build crashed with
    RuntimeError because it tried to emit rows in a non-existent length-0
    cyclic-word block."""
    node = NODE1_LABEL
    theory = Theory(
        name="massive Phi",
        gauge_nodes=(su(3, label=node),),
        fields=(
            Field(name="Phi", field_type="chiral multiplet",
                  gauge_reps={node: adjoint()}, r_charge=Fraction(2)),
        ),
        superpotential_terms=(SuperpotentialTerm(factors=(("Phi", 1),)),),
    )
    arrows = extract_arrows(theory)
    dims = quotient_dimensions(arrows, theory.superpotential_terms, max_length=3)
    # Every block (1, R=2), (2, R=4), (3, R=6) must be killed completely.
    assert set(dims.keys()) == {(1, Fraction(2)), (2, Fraction(4)), (3, Fraction(6))}
    assert all(value == 0 for value in dims.values())


def test_build_relation_matrix_mass_term_length_only_also_kills():
    """Length-only mode behaves the same on the mass-term fixture."""
    node = NODE1_LABEL
    theory = Theory(
        name="massive Phi",
        gauge_nodes=(su(3, label=node),),
        fields=(
            Field(name="Phi", field_type="chiral multiplet",
                  gauge_reps={node: adjoint()}, r_charge=Fraction(2)),
        ),
        superpotential_terms=(SuperpotentialTerm(factors=(("Phi", 1),)),),
    )
    arrows = extract_arrows(theory)
    dims = quotient_dimensions(arrows, theory.superpotential_terms,
                               max_length=3, r_graded=False)
    assert dims == {(1, None): 0, (2, None): 0, (3, None): 0}


# ===========================================================================
# Step 3 defensive: r_graded R-homogeneity guard (P3 belt-and-suspenders)
# ===========================================================================

def test_build_relation_matrix_r_graded_rejects_p3_violating_w():
    """If two W terms have different total R-charges they share an arrow
    derivative (here ∂_X) → row_dict mixes cyclic words at different
    R-charges. With r_graded=True the defensive guard must surface this
    as a clear P3-violation error instead of silently mis-bucketing rows."""
    n1 = su(3, label=NODE1_LABEL)
    n2 = su(3, label=NODE2_LABEL)
    fields = (
        Field(name="X", field_type="chiral multiplet",
              gauge_reps={NODE1_LABEL: antifundamental(), NODE2_LABEL: fundamental()},
              r_charge=Fraction(2, 3)),
        Field(name="Y", field_type="chiral multiplet",
              gauge_reps={NODE2_LABEL: antifundamental(), NODE1_LABEL: fundamental()},
              r_charge=Fraction(2, 3)),
        Field(name="Phi", field_type="chiral multiplet",
              gauge_reps={NODE1_LABEL: adjoint()}, r_charge=Fraction(2, 3)),
        Field(name="Psi", field_type="chiral multiplet",
              gauge_reps={NODE1_LABEL: adjoint()}, r_charge=Fraction(1)),
    )
    W = (
        SuperpotentialTerm(factors=(("Phi", 1), ("X", 1), ("Y", 1))),  # R = 2
        SuperpotentialTerm(factors=(("Psi", 1), ("X", 1), ("Y", 1))),  # R = 7/3 (P3 violated)
    )
    theory = Theory(name="P3 violator", gauge_nodes=(n1, n2), fields=fields,
                    superpotential_terms=W)
    arrows = extract_arrows(theory)
    with pytest.raises(ValueError) as exc_info:
        build_relation_matrix(arrows, W, max_length=3, r_graded=True)
    assert "P3" in str(exc_info.value) or "R-charge" in str(exc_info.value)


def test_build_relation_matrix_length_only_accepts_p3_violating_w():
    """The same P3-violating W must run cleanly in length-only mode — the
    guard fires only for r_graded=True."""
    n1 = su(3, label=NODE1_LABEL)
    n2 = su(3, label=NODE2_LABEL)
    fields = (
        Field(name="X", field_type="chiral multiplet",
              gauge_reps={NODE1_LABEL: antifundamental(), NODE2_LABEL: fundamental()},
              r_charge=Fraction(2, 3)),
        Field(name="Y", field_type="chiral multiplet",
              gauge_reps={NODE2_LABEL: antifundamental(), NODE1_LABEL: fundamental()},
              r_charge=Fraction(2, 3)),
        Field(name="Phi", field_type="chiral multiplet",
              gauge_reps={NODE1_LABEL: adjoint()}, r_charge=Fraction(2, 3)),
        Field(name="Psi", field_type="chiral multiplet",
              gauge_reps={NODE1_LABEL: adjoint()}, r_charge=Fraction(1)),
    )
    W = (
        SuperpotentialTerm(factors=(("Phi", 1), ("X", 1), ("Y", 1))),
        SuperpotentialTerm(factors=(("Psi", 1), ("X", 1), ("Y", 1))),
    )
    arrows = extract_arrows(Theory(name="P3v", gauge_nodes=(n1, n2),
                                   fields=fields, superpotential_terms=W))
    # Should not raise.
    matrices = build_relation_matrix(arrows, W, max_length=3, r_graded=False)
    assert all(k[1] is None for k in matrices)


# ===========================================================================
# Step 4: bounded_chiral_ring_consistency_check (verdict)
# ===========================================================================

def _wrap_claim(electric, magnetic, *, max_length=4, require_r_graded=True,
                profile="toy"):
    return DualityClaim(
        name="test claim",
        electric_theory=electric,
        magnetic_theory=magnetic,
        metadata={
            "duality_profile": profile,
            "theory_kind": "pure_quiver",
            "bounded_chiral_ring": {
                "max_length": max_length,
                "require_r_graded": require_r_graded,
            },
        },
    )


def _certified_prior_anomalies() -> dict:
    """Mimic the prior_results dict from evaluate_claim with all four
    upstream anomaly obligations CERTIFIED."""
    return {
        key: ObligationResult(
            name=key, description="upstream", status=Status.CERTIFIED, message="ok",
        )
        for key in (
            "electric_gauge_anomaly",
            "magnetic_gauge_anomaly",
            "electric_gauge_global_mixed_anomaly",
            "magnetic_gauge_global_mixed_anomaly",
        )
    }


# --- §11.2 self-equivalence ------------------------------------------------

def test_bounded_chiral_ring_dp0_self_equivalence_r_graded_certified():
    """dP_0 SU(3)^3 cyclic quiver is ABJ-free (memory: 3-node SU(3)^3 fixture
    introduced in step 0 is the R-graded fixture). Self-equivalence under
    r_graded=True with CERTIFIED upstream anomalies must produce CERTIFIED.
    Only length-3 closed walks exist on dP_0 within L=4."""
    from dualitycert.groups.u1 import u1_r
    from dualitycert.qft.pure_quiver_builder import (
        arrow_names, build_pure_quiver, dp0_superpotential,
    )

    r = Fraction(2, 3)
    n01 = arrow_names(0, 1, 3)
    n12 = arrow_names(1, 2, 3)
    n20 = arrow_names(2, 0, 3)
    dp0 = build_pure_quiver(
        ranks=(3, 3, 3),
        arrows={(0, 1): [r]*3, (1, 2): [r]*3, (2, 0): [r]*3},
        superpotential=dp0_superpotential(n01, n12, n20),
        u1_globals=(u1_r(),),
    )
    claim = _wrap_claim(dp0, dp0, max_length=4, require_r_graded=True, profile="dp0_self")
    res = bounded_chiral_ring_consistency_check(claim, _certified_prior_anomalies())
    assert res.status == Status.CERTIFIED
    assert "PASSED_BOUNDED_CHIRAL_RING_CONSISTENCY" in res.message
    assert res.details["r_graded"] is True
    assert len(res.details["failed_blocks"]) == 0
    assert len(res.details["tested_blocks"]) >= 1
    # Must always carry the dim-only PASS limitations forward.
    assert "two-sided F-ideal generated only up to length L" in res.details["limitations"]


def test_bounded_chiral_ring_toy_self_equivalence_length_only_certified():
    """The toy fixture is NOT ABJ-free (memory note). Use require_r_graded=False
    so the comparison runs in length-only mode and self-equivalence still
    certifies."""
    claim = _wrap_claim(_toy_theory(), _toy_theory(),
                        max_length=4, require_r_graded=False, profile="toy_self")
    res = bounded_chiral_ring_consistency_check(claim, {})
    assert res.status == Status.CERTIFIED
    assert res.details["r_graded"] is False
    assert len(res.details["failed_blocks"]) == 0
    # Length-only warning must be present.
    assert any("length-only" in w for w in res.warnings)


# --- §11.3 failure fixture 2: drop Phi from magnetic ------------------------

def test_bounded_chiral_ring_drops_phi_magnetic_fails():
    """Magnetic side without Phi has no length-1 cyclic word, so the (1, 2/3)
    block disagrees with electric. FAILED with the smallest failing block
    surfaced in the message."""
    n1 = su(3, label=NODE1_LABEL)
    n2 = su(3, label=NODE2_LABEL)
    magnetic_no_phi = Theory(
        name="magnetic without Phi",
        gauge_nodes=(n1, n2),
        fields=(
            Field(name="X", field_type="chiral multiplet",
                  gauge_reps={NODE1_LABEL: antifundamental(), NODE2_LABEL: fundamental()},
                  r_charge=Fraction(2, 3)),
            Field(name="Y", field_type="chiral multiplet",
                  gauge_reps={NODE2_LABEL: antifundamental(), NODE1_LABEL: fundamental()},
                  r_charge=Fraction(2, 3)),
        ),
        superpotential_terms=(),  # no superpotential, since Phi is gone
    )
    claim = _wrap_claim(_toy_theory(), magnetic_no_phi,
                        max_length=4, require_r_graded=False, profile="drop_phi")
    res = bounded_chiral_ring_consistency_check(claim, {})
    assert res.status == Status.FAILED
    assert "FAILED_AT_BLOCK" in res.message
    # Length-1 must be among failed blocks (electric has Phi, magnetic has nothing).
    failed_lengths = {b["length"] for b in res.details["failed_blocks"]}
    assert 1 in failed_lengths
    # Sample operators must be populated for failed blocks.
    assert res.details["sample_operators"]


# --- §11.3 failure fixture 1: wrong R-charge on magnetic side --------------

def test_bounded_chiral_ring_wrong_r_charge_magnetic_p3_fails():
    """Magnetic side has R(Y) = 1/2 instead of 2/3 ⇒ W term R-charge = 11/6,
    not 2 ⇒ P3 fails ⇒ NOT_APPLICABLE under require_r_graded=True."""
    n1 = su(3, label=NODE1_LABEL)
    n2 = su(3, label=NODE2_LABEL)
    bad_magnetic = Theory(
        name="bad R(Y)",
        gauge_nodes=(n1, n2),
        fields=(
            Field(name="X", field_type="chiral multiplet",
                  gauge_reps={NODE1_LABEL: antifundamental(), NODE2_LABEL: fundamental()},
                  r_charge=Fraction(2, 3)),
            Field(name="Y", field_type="chiral multiplet",
                  gauge_reps={NODE2_LABEL: antifundamental(), NODE1_LABEL: fundamental()},
                  r_charge=Fraction(1, 2)),   # wrong
            Field(name="Phi", field_type="chiral multiplet",
                  gauge_reps={NODE1_LABEL: adjoint()}, r_charge=Fraction(2, 3)),
        ),
        superpotential_terms=(
            SuperpotentialTerm(factors=(("Phi", 1), ("X", 1), ("Y", 1))),
        ),
    )
    claim = _wrap_claim(_toy_theory(), bad_magnetic,
                        max_length=3, require_r_graded=True, profile="bad_r_charge")
    res = bounded_chiral_ring_consistency_check(claim, _certified_prior_anomalies())
    assert res.status == Status.NOT_APPLICABLE
    assert "P3" in res.details["r_graded_blocked_by"]
    assert any("Y" in failure for failure in res.details["p3_failures"])


def test_bounded_chiral_ring_wrong_r_charge_under_length_only_still_runs():
    """Same fixture, but require_r_graded=False: P3 violation no longer
    blocks, the comparison runs in length-only mode. (Result may be CERTIFIED
    or FAILED depending on coincidence — just verify it doesn't NOT_APPLICABLE.)"""
    n1 = su(3, label=NODE1_LABEL)
    n2 = su(3, label=NODE2_LABEL)
    bad_magnetic = Theory(
        name="bad R(Y)",
        gauge_nodes=(n1, n2),
        fields=(
            Field(name="X", field_type="chiral multiplet",
                  gauge_reps={NODE1_LABEL: antifundamental(), NODE2_LABEL: fundamental()},
                  r_charge=Fraction(2, 3)),
            Field(name="Y", field_type="chiral multiplet",
                  gauge_reps={NODE2_LABEL: antifundamental(), NODE1_LABEL: fundamental()},
                  r_charge=Fraction(1, 2)),
            Field(name="Phi", field_type="chiral multiplet",
                  gauge_reps={NODE1_LABEL: adjoint()}, r_charge=Fraction(2, 3)),
        ),
        superpotential_terms=(
            SuperpotentialTerm(factors=(("Phi", 1), ("X", 1), ("Y", 1))),
        ),
    )
    claim = _wrap_claim(_toy_theory(), bad_magnetic,
                        max_length=3, require_r_graded=False, profile="bad_r_relaxed")
    res = bounded_chiral_ring_consistency_check(claim, {})
    assert res.status in {Status.CERTIFIED, Status.FAILED}
    assert res.details["r_graded"] is False


# --- P4: upstream anomaly gating -------------------------------------------

def test_bounded_chiral_ring_p4_failure_blocks_r_graded_mode():
    """A FAILED upstream anomaly obligation forces NOT_APPLICABLE in
    require_r_graded=True mode, with P4 listed as the blocker and the
    upstream check name preserved in p4_failures."""
    prior = {
        "electric_gauge_anomaly": ObligationResult(
            name="electric gauge anomaly cancellation",
            description="electric cubic", status=Status.FAILED,
            message="cubic anomaly nonzero",
        ),
    }
    claim = _wrap_claim(_toy_theory(), _toy_theory(),
                        max_length=3, require_r_graded=True, profile="p4_block")
    res = bounded_chiral_ring_consistency_check(claim, prior)
    assert res.status == Status.NOT_APPLICABLE
    assert "P4" in res.details["r_graded_blocked_by"]
    assert any("electric_gauge_anomaly" in f for f in res.details["p4_failures"])


def test_bounded_chiral_ring_p4_failure_length_only_runs():
    """Same P4 failure, but require_r_graded=False: the check still runs
    (length-only fallback), produces a CERTIFIED self-equivalence."""
    prior = {
        "electric_gauge_anomaly": ObligationResult(
            name="electric gauge anomaly cancellation",
            description="electric cubic", status=Status.FAILED,
            message="cubic anomaly nonzero",
        ),
    }
    claim = _wrap_claim(_toy_theory(), _toy_theory(),
                        max_length=3, require_r_graded=False, profile="p4_relaxed")
    res = bounded_chiral_ring_consistency_check(claim, prior)
    assert res.status == Status.CERTIFIED
    assert res.details["r_graded"] is False


# --- P1, P5, P6 pre-conditions ---------------------------------------------

def test_bounded_chiral_ring_not_pure_quiver_returns_not_applicable():
    """A claim where one side is not pure_quiver (here flavored_single_gauge via
    SU(Nf) global symmetry on Q) must NOT_APPLICABLE if the check is invoked
    directly (the registry would normally not even dispatch it)."""
    from dualitycert.qft.dualities import build_seiberg_sqcd_claim
    sqcd_claim = build_seiberg_sqcd_claim(Nc=3, Nf=5)
    res = bounded_chiral_ring_consistency_check(sqcd_claim, _certified_prior_anomalies())
    assert res.status == Status.NOT_APPLICABLE
    assert res.details["preconditions"]["P1"] == "fail"


def test_bounded_chiral_ring_p5_unknown_label_returns_not_applicable():
    """If a W term references a nonexistent field, P5 fails and the check
    returns NOT_APPLICABLE with the offending term named in the rejection."""
    n1 = su(3, label=NODE1_LABEL)
    bad = Theory(
        name="bad W",
        gauge_nodes=(n1,),
        fields=(
            Field(name="Phi", field_type="chiral multiplet",
                  gauge_reps={NODE1_LABEL: adjoint()}, r_charge=Fraction(2, 3)),
        ),
        superpotential_terms=(SuperpotentialTerm(factors=(("MISSING", 1),)),),
    )
    claim = _wrap_claim(bad, bad, max_length=3, require_r_graded=False, profile="p5_bad")
    res = bounded_chiral_ring_consistency_check(claim, {})
    assert res.status == Status.NOT_APPLICABLE
    assert any(k.startswith("P5") for k in res.details["preconditions"])
    assert "MISSING" in res.details["rejection_reason"]


def test_bounded_chiral_ring_p6_max_length_too_large():
    """max_length > 8 is rejected as UNKNOWN per design doc §3.1 / P6."""
    claim = DualityClaim(
        name="huge L",
        electric_theory=_toy_theory(),
        magnetic_theory=_toy_theory(),
        metadata={
            "duality_profile": "huge",
            "theory_kind": "pure_quiver",
            "bounded_chiral_ring": {"max_length": 10, "require_r_graded": False},
        },
    )
    res = bounded_chiral_ring_consistency_check(claim, {})
    assert res.status == Status.UNKNOWN
    assert res.details["preconditions"]["P6"] == "fail"


def test_bounded_chiral_ring_default_metadata_when_block_absent():
    """No metadata['bounded_chiral_ring'] block ⇒ defaults are max_length=6,
    require_r_graded=True (design doc §3.1)."""
    claim = DualityClaim(
        name="defaults",
        electric_theory=_toy_theory(),
        magnetic_theory=_toy_theory(),
        metadata={"duality_profile": "defaults", "theory_kind": "pure_quiver"},
    )
    res = bounded_chiral_ring_consistency_check(claim, _certified_prior_anomalies())
    assert res.details["cutoff_L"] == 6
    assert res.details["require_r_graded"] is True


# --- Registry integration via evaluate_claim --------------------------------

def test_bounded_chiral_ring_runs_through_evaluate_claim_for_pure_quiver():
    """End-to-end through evaluate_claim: dP_0 self-equivalence should
    receive the new check, and prior_results from anomaly obligations must
    flow into it (option A plumbing). The check should appear in the
    certificate and be CERTIFIED for dP_0."""
    from dualitycert.groups.u1 import u1_r
    from dualitycert.qft.dualities import evaluate_claim
    from dualitycert.qft.pure_quiver_builder import (
        arrow_names, build_pure_quiver, dp0_superpotential,
    )

    r = Fraction(2, 3)
    n01 = arrow_names(0, 1, 3)
    n12 = arrow_names(1, 2, 3)
    n20 = arrow_names(2, 0, 3)
    dp0 = build_pure_quiver(
        ranks=(3, 3, 3),
        arrows={(0, 1): [r]*3, (1, 2): [r]*3, (2, 0): [r]*3},
        superpotential=dp0_superpotential(n01, n12, n20),
        u1_globals=(u1_r(),),
    )
    claim = _wrap_claim(dp0, dp0, max_length=4, require_r_graded=True, profile="dp0")
    cert = evaluate_claim(claim)
    matches = [r for r in cert.obligation_results if r.name == "bounded chiral-ring consistency"]
    assert len(matches) == 1
    assert matches[0].status == Status.CERTIFIED


def test_bounded_chiral_ring_skipped_for_non_pure_quiver_via_registry():
    """The check has applicable_kinds={'pure_quiver'}, so a flavored claim
    must not produce a result for this check at all."""
    from dualitycert.qft.dualities import build_seiberg_sqcd_claim, evaluate_claim
    cert = evaluate_claim(build_seiberg_sqcd_claim(Nc=3, Nf=5))
    matches = [r for r in cert.obligation_results if r.name == "bounded chiral-ring consistency"]
    assert matches == []


# --- Codex review fixups ----------------------------------------------------

def test_bounded_chiral_ring_p3_handles_multi_arrow_machine_labels():
    """A Field with multiplicity > 1 expands into machine labels
    f"{name}[{i}]" (§3.2). The W term must reference those labels. The P3
    check must look them up via Arrow.label (extract_arrows), NOT via
    Field.name (theory.field_map()), otherwise it falsely reports
    'unknown field X[0]' and returns NOT_APPLICABLE under r_graded=True
    even though P3 in fact passes."""
    n1 = su(3, label=NODE1_LABEL)
    n2 = su(3, label=NODE2_LABEL)
    fields = (
        Field(
            name="X",
            field_type="chiral multiplet",
            gauge_reps={NODE1_LABEL: antifundamental(), NODE2_LABEL: fundamental()},
            r_charge=Fraction(2, 3),
            multiplicity=2,  # generates labels X[0], X[1]
        ),
        Field(
            name="Y",
            field_type="chiral multiplet",
            gauge_reps={NODE2_LABEL: antifundamental(), NODE1_LABEL: fundamental()},
            r_charge=Fraction(2, 3),
        ),
        Field(
            name="Phi",
            field_type="chiral multiplet",
            gauge_reps={NODE1_LABEL: adjoint()},
            r_charge=Fraction(2, 3),
        ),
    )
    theory = Theory(
        name="multi-X toy",
        gauge_nodes=(n1, n2),
        fields=fields,
        # Each W term has R = 2/3 + 2/3 + 2/3 = 2 ⇒ P3 passes once we look up
        # X[0] / X[1] correctly.
        superpotential_terms=(
            SuperpotentialTerm(factors=(("Phi", 1), ("X[0]", 1), ("Y", 1))),
            SuperpotentialTerm(factors=(("Phi", 1), ("X[1]", 1), ("Y", 1))),
        ),
    )
    claim = _wrap_claim(theory, theory, max_length=3, require_r_graded=True,
                        profile="multi_arrow")
    res = bounded_chiral_ring_consistency_check(claim, _certified_prior_anomalies())
    assert res.status == Status.CERTIFIED
    assert res.details["preconditions"]["P3"] == "pass"


def test_bounded_chiral_ring_strict_p4_blocks_when_upstream_missing():
    """Under r_graded=True, missing entries in prior_results count as P4
    failure — the R-graded comparison cannot stand without a CERTIFIED
    upstream U(1)_R anomaly result. (Previously the check incorrectly
    treated missing entries as P4 pass; codex caught this on the
    evaluate_claim path where the toy has no U(1)_R global.)"""
    claim = _wrap_claim(_toy_theory(), _toy_theory(),
                        max_length=3, require_r_graded=True,
                        profile="missing_upstream")
    res = bounded_chiral_ring_consistency_check(claim, {})  # nothing upstream
    assert res.status == Status.NOT_APPLICABLE
    assert "P4" in res.details["r_graded_blocked_by"]
    assert any("did not run" in failure for failure in res.details["p4_failures"])


def test_bounded_chiral_ring_strict_p4_blocks_when_upstream_not_applicable():
    """NOT_APPLICABLE upstream (e.g. mixed anomaly check returned
    NOT_APPLICABLE because the claim has no U(1)_R global symmetry
    encoded) also blocks r_graded mode under strict P4: there is no
    physical anomaly-free guarantee to support the R-bucketed comparison."""
    prior = {
        key: ObligationResult(
            name=key, description="upstream",
            status=Status.NOT_APPLICABLE, message="no U(1)_R global symmetry",
        )
        for key in (
            "electric_gauge_anomaly",
            "magnetic_gauge_anomaly",
            "electric_gauge_global_mixed_anomaly",
            "magnetic_gauge_global_mixed_anomaly",
        )
    }
    claim = _wrap_claim(_toy_theory(), _toy_theory(),
                        max_length=3, require_r_graded=True,
                        profile="upstream_not_applicable")
    res = bounded_chiral_ring_consistency_check(claim, prior)
    assert res.status == Status.NOT_APPLICABLE
    assert "P4" in res.details["r_graded_blocked_by"]
    assert any("NOT_APPLICABLE" in failure for failure in res.details["p4_failures"])


def test_bounded_chiral_ring_details_carry_mandatory_r_graded_key_on_every_path():
    """Design doc §7 lists `r_graded` as a mandatory certificate key. It
    must appear on every path (CERTIFIED success, NOT_APPLICABLE early
    failure, UNKNOWN over-cutoff, NOT_APPLICABLE strict-P4-blocked) and
    must reflect what actually ran (True only when the comparison
    executed in R-graded mode; False on every early failure)."""

    # Path 1: success in r_graded mode → True.
    claim_ok = _wrap_claim(_toy_theory(), _toy_theory(),
                           max_length=3, require_r_graded=True, profile="r_graded_ok")
    res = bounded_chiral_ring_consistency_check(claim_ok, _certified_prior_anomalies())
    assert "r_graded" in res.details
    assert res.details["r_graded"] is True

    # Path 2: P1 fail (non-pure_quiver) → still has key, False.
    from dualitycert.qft.dualities import build_seiberg_sqcd_claim
    sqcd = build_seiberg_sqcd_claim(Nc=3, Nf=5)
    res_p1 = bounded_chiral_ring_consistency_check(sqcd, _certified_prior_anomalies())
    assert res_p1.status == Status.NOT_APPLICABLE
    assert res_p1.details["r_graded"] is False

    # Path 3: P6 fail (max_length too big) → False.
    huge = DualityClaim(
        name="huge",
        electric_theory=_toy_theory(),
        magnetic_theory=_toy_theory(),
        metadata={
            "duality_profile": "p6",
            "theory_kind": "pure_quiver",
            "bounded_chiral_ring": {"max_length": 10, "require_r_graded": True},
        },
    )
    res_p6 = bounded_chiral_ring_consistency_check(huge, _certified_prior_anomalies())
    assert res_p6.status == Status.UNKNOWN
    assert res_p6.details["r_graded"] is False

    # Path 4: strict P4 blocks r_graded → False (the comparison was
    # suppressed even though the user asked for r_graded).
    res_p4 = bounded_chiral_ring_consistency_check(
        _wrap_claim(_toy_theory(), _toy_theory(),
                    max_length=3, require_r_graded=True, profile="p4_block_doc_test"),
        {},
    )
    assert res_p4.status == Status.NOT_APPLICABLE
    assert res_p4.details["r_graded"] is False
    # `require_r_graded` is also carried so a consumer can distinguish
    # "user asked for r_graded but it was suppressed" from "user asked for
    # length-only".
    assert res_p4.details["require_r_graded"] is True


def test_bounded_chiral_ring_details_schema_split_between_always_and_comparison_paths():
    """Design doc §7 splits details into always-present keys (cutoff_L,
    r_graded, require_r_graded, r_graded_blocked_by, mod_cyclic_rotation,
    orientation_preserved, context_multiplied_ideal, preconditions,
    limitations) and comparison-path-only keys (tested_blocks,
    failed_blocks, sample_operators, arrow_machine_labels_electric /
    arrow_machine_labels_magnetic). Empty-list defaults on the
    comparison-only keys are explicitly NOT used so consumers can
    distinguish "comparison ran with zero failed blocks" (CERTIFIED)
    from "comparison never ran" (NOT_APPLICABLE)."""

    always_present_keys = {
        "cutoff_L",
        "r_graded",
        "require_r_graded",
        "r_graded_blocked_by",
        "mod_cyclic_rotation",
        "orientation_preserved",
        "context_multiplied_ideal",
        "preconditions",
        "limitations",
    }
    comparison_only_keys = {
        "tested_blocks",
        "failed_blocks",
        "sample_operators",
        "arrow_machine_labels_electric",
        "arrow_machine_labels_magnetic",
    }

    # CERTIFIED comparison path — both sets present.
    res_ok = bounded_chiral_ring_consistency_check(
        _wrap_claim(_toy_theory(), _toy_theory(),
                    max_length=3, require_r_graded=True, profile="schema_ok"),
        _certified_prior_anomalies(),
    )
    assert always_present_keys.issubset(res_ok.details)
    assert comparison_only_keys.issubset(res_ok.details)

    # Early NOT_APPLICABLE (P1 fail via SQCD claim) — always-present keys
    # only; comparison keys must NOT have been fabricated as empty defaults.
    from dualitycert.qft.dualities import build_seiberg_sqcd_claim
    res_p1 = bounded_chiral_ring_consistency_check(
        build_seiberg_sqcd_claim(Nc=3, Nf=5), _certified_prior_anomalies()
    )
    assert res_p1.status == Status.NOT_APPLICABLE
    assert always_present_keys.issubset(res_p1.details)
    assert not (comparison_only_keys & set(res_p1.details))

    # Early UNKNOWN (P6 over-cutoff) — same shape.
    huge_claim = DualityClaim(
        name="huge L",
        electric_theory=_toy_theory(),
        magnetic_theory=_toy_theory(),
        metadata={
            "duality_profile": "schema_p6",
            "theory_kind": "pure_quiver",
            "bounded_chiral_ring": {"max_length": 10, "require_r_graded": False},
        },
    )
    res_p6 = bounded_chiral_ring_consistency_check(huge_claim, {})
    assert res_p6.status == Status.UNKNOWN
    assert always_present_keys.issubset(res_p6.details)
    assert not (comparison_only_keys & set(res_p6.details))

    # Strict-P4 NOT_APPLICABLE (require_r_graded=True, empty prior) —
    # same shape: the comparison was suppressed before block-wise math.
    res_p4 = bounded_chiral_ring_consistency_check(
        _wrap_claim(_toy_theory(), _toy_theory(),
                    max_length=3, require_r_graded=True, profile="schema_p4"),
        {},
    )
    assert res_p4.status == Status.NOT_APPLICABLE
    assert always_present_keys.issubset(res_p4.details)
    assert not (comparison_only_keys & set(res_p4.details))


def test_bounded_chiral_ring_unknown_on_compute_error_still_carries_preconditions(monkeypatch):
    """If quotient_dimensions raises (R-homogeneity guard, numeric pathology,
    or any unexpected ValueError/RuntimeError after all pre-conditions
    passed), the resulting UNKNOWN verdict must still carry the
    always-present schema — including `preconditions` — per design doc §7.
    The comparison-path keys (tested_blocks etc.) remain absent because the
    block-wise comparison never ran."""
    from dualitycert.qft import quiver_chiral_ring as qcr

    def boom(*args, **kwargs):
        raise RuntimeError("simulated rank-computation failure")

    monkeypatch.setattr(qcr, "quotient_dimensions", boom)

    res = qcr.bounded_chiral_ring_consistency_check(
        _wrap_claim(_toy_theory(), _toy_theory(),
                    max_length=3, require_r_graded=True, profile="compute_boom"),
        _certified_prior_anomalies(),
    )
    assert res.status == Status.UNKNOWN
    assert "simulated rank-computation failure" in res.message

    # Always-present keys must be there.
    for key in ("cutoff_L", "r_graded", "require_r_graded", "r_graded_blocked_by",
                "mod_cyclic_rotation", "orientation_preserved",
                "context_multiplied_ideal", "preconditions", "limitations"):
        assert key in res.details, f"missing always-present key {key!r}"

    # Every pre-condition reached "pass" before quotient_dimensions blew up.
    pre = res.details["preconditions"]
    assert pre["P1"] == "pass"
    assert pre["P5_electric"] == "pass"
    assert pre["P5_magnetic"] == "pass"
    assert pre["P6"] == "pass"

    # Comparison-only keys must NOT be present (the block-wise loop never ran).
    for key in ("tested_blocks", "failed_blocks", "sample_operators",
                "arrow_machine_labels_electric", "arrow_machine_labels_magnetic"):
        assert key not in res.details, f"comparison-only key {key!r} leaked into UNKNOWN path"


def test_bounded_chiral_ring_strict_p4_length_only_unaffected_by_missing_upstream():
    """Strict P4 only matters in r_graded mode. With require_r_graded=False
    the same missing-upstream claim falls through to length-only
    comparison (CERTIFIED on self-equivalence)."""
    claim = _wrap_claim(_toy_theory(), _toy_theory(),
                        max_length=3, require_r_graded=False,
                        profile="missing_upstream_length_only")
    res = bounded_chiral_ring_consistency_check(claim, {})
    assert res.status == Status.CERTIFIED
    assert res.details["r_graded"] is False
    # P4 still recorded as blocker for diagnostics, just non-fatal here.
    assert "P4" in res.details["r_graded_blocked_by"]
