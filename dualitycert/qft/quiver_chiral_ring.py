"""Bounded cyclic path-algebra primitives for pure_quiver theories.

Phase 2a steps 1-4: arrow extraction, cyclic-word enumeration, cyclic
derivatives of the superpotential, two-sided context multiplication into
F-relation matrices, per-block quotient dimensions, and the
bounded_chiral_ring_consistency verdict that compares two pure-quiver
theories block-wise
(see docs/phase2a_pure_quiver_chiral_ring.md §7 / §14).

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
from typing import Iterable, Iterator, Mapping, Optional

from dualitycert.core.objects import (
    CheckResult,
    DualityClaim,
    Field,
    SuperpotentialTerm,
    Theory,
)
from dualitycert.core.obligations import ObligationResult
from dualitycert.core.status import Status
from dualitycert.core.theory_kind import PURE_QUIVER, infer_theory_kind


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


class WTermShapeError(ValueError):
    """Raised when a superpotential term is not a closed monomial walk on
    the given arrow set, or references a label outside the arrow set.

    P5 in design doc §4. Upstream (step 4) converts this into a
    NOT_APPLICABLE verdict, mirroring `PureQuiverShapeError` at the
    arrow-extraction layer.
    """

    def __init__(self, term_display: str, reason: str) -> None:
        super().__init__(f"Superpotential term {term_display!r}: {reason}")
        self.term_display = term_display
        self.reason = reason


# Block key for build_relation_matrix / quotient_dimensions output.
# (length, r_charge) when r_graded=True; (length, None) when length-only.
Block = tuple[int, Optional[Fraction]]


@dataclass(frozen=True)
class RelationMatrix:
    """One block's F-relation matrix expressed in the cyclic-word basis.

    `column_basis` lists the canonical cyclic-word tuples that index the
    columns (in the same order they were produced by
    `enumerate_cyclic_words`). Each row in `rows` is a dense Fraction
    vector aligned to that order. `block` records the (length, r_charge)
    key the matrix lives in.

    Invariants enforced at construction (RelationMatrix is publicly
    exported and rank()/quotient_dimension assume well-formed data):
      - `column_basis` and `rows` (and each row) are coerced to tuples
        so `frozen=True` and `hash()` actually hold even on list inputs;
      - every row has length `== len(column_basis)`, so rank() cannot
        silently drop columns or trip on short rows.
    """

    block: Block
    column_basis: tuple[tuple[str, ...], ...]
    rows: tuple[tuple[Fraction, ...], ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "column_basis",
            tuple(tuple(column) for column in self.column_basis),
        )
        object.__setattr__(self, "rows", tuple(tuple(row) for row in self.rows))
        width = len(self.column_basis)
        for index, row in enumerate(self.rows):
            if len(row) != width:
                raise ValueError(
                    f"RelationMatrix row {index} has length {len(row)}, "
                    f"expected {width} to match len(column_basis)"
                )

    @property
    def num_rows(self) -> int:
        return len(self.rows)

    @property
    def num_cols(self) -> int:
        return len(self.column_basis)

    @property
    def rank(self) -> int:
        return _gaussian_rank(self.rows, self.num_cols)

    @property
    def quotient_dimension(self) -> int:
        return self.num_cols - self.rank


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


def cyclic_derivative(
    W_terms: Iterable[SuperpotentialTerm],
    arrow: Arrow,
) -> dict[tuple[str, ...], Fraction]:
    """Compute ∂_arrow W as a Q-linear combination of open paths.

    For each term `c · A_1 ... A_n` in `W_terms` and each position `i`
    with `A_i.label == arrow.label`, the cyclic derivative contributes
    `c · (A_{i+1}, ..., A_n, A_1, ..., A_{i-1})` — the rotation that
    places the matched arrow at the start, with that arrow stripped off.
    Per design doc §2, the open path runs from `target(arrow)` back to
    `source(arrow)`; this function returns it as a tuple of machine
    labels and lets the caller verify endpoints if needed.

    Multiple occurrences within a single term contribute independently.
    Multiple terms contribute additively. Paths that sum to zero across
    the input are omitted from the returned dict.

    Factor names in `W_terms` are interpreted as Arrow machine labels
    (design doc §3.2: claim JSON references machine labels, not
    Field.name shorthands, for multi-arrow expansions).
    """

    result: dict[tuple[str, ...], Fraction] = {}
    target_label = arrow.label
    for term in W_terms:
        flat = term.field_names
        coefficient = term.coefficient
        for position, name in enumerate(flat):
            if name != target_label:
                continue
            open_path = tuple(flat[position + 1 :]) + tuple(flat[:position])
            result[open_path] = result.get(open_path, Fraction(0)) + coefficient
    return {path: coeff for path, coeff in result.items() if coeff != 0}


def validate_w_terms(
    arrows: Iterable[Arrow],
    W_terms: Iterable[SuperpotentialTerm],
) -> None:
    """Enforce P5 (design doc §4) on every superpotential term.

    For each `SuperpotentialTerm` in `W_terms`:
      - every factor name must equal some `Arrow.label` in `arrows`;
      - the flattened arrow sequence A_1...A_n must form a closed monomial
        walk, i.e. `target(A_i) == source(A_{i+1})` for all `i` and
        `target(A_n) == source(A_1)`.

    Raises `WTermShapeError(term_display, reason)` on the first offending
    term. `cyclic_derivative` itself is deliberately kept as a low-level
    string-matching primitive (it does not check well-formedness), so this
    helper must run before `build_relation_matrix` to guarantee that the
    F-relations it produces are physically meaningful.
    """

    arrows_by_label: dict[str, Arrow] = {arrow.label: arrow for arrow in arrows}
    for term in W_terms:
        labels = term.field_names
        if not labels:
            raise WTermShapeError(term.display_name, "term has no factors")
        for label in labels:
            if label not in arrows_by_label:
                raise WTermShapeError(
                    term.display_name,
                    f"factor {label!r} is not the machine label of any arrow",
                )
        for index in range(len(labels)):
            a = arrows_by_label[labels[index]]
            b = arrows_by_label[labels[(index + 1) % len(labels)]]
            if a.target != b.source:
                raise WTermShapeError(
                    term.display_name,
                    f"arrows {a.label!r} -> {b.label!r} do not compose: "
                    f"target({a.label})={a.target!r} but source({b.label})={b.source!r}",
                )


def build_relation_matrix(
    arrows: Iterable[Arrow],
    W_terms: Iterable[SuperpotentialTerm],
    max_length: int,
    r_graded: bool = True,
) -> dict[Block, RelationMatrix]:
    """Build the F-relation matrix in each cyclic-word block up to cutoff L.

    For each arrow X, split its cyclic derivative ∂_X W into homogeneous
    generators by path length (design doc §5.1). For each generator
    g = Σ α_p · path_p (length n, source = target(X), target = source(X))
    and each context path C with source(C) = target(g), target(C) =
    source(g), length(C) = ℓ - n where ℓ ∈ {n, ..., max_length}: emit one
    row whose entry on canonical(C · path_p) equals α_p (summed over p,
    zeros dropped). Rows are bucketed into blocks `(ℓ, r_charge)` if
    `r_graded`, else `(ℓ, None)`.

    Pre-condition: `validate_w_terms` must pass — caller's responsibility,
    but this function calls it defensively to fail loudly rather than
    silently producing garbage rows on malformed W.

    Returns a dict keyed by every basis block (length 1..max_length, and
    each R-charge bucket if r_graded); `RelationMatrix.rows` is `()` when
    no relation reaches the block.
    """

    if max_length < 1:
        raise ValueError(f"max_length must be >= 1, got {max_length}")

    arrows_tuple = tuple(arrows)
    W_tuple = tuple(W_terms)
    validate_w_terms(arrows_tuple, W_tuple)

    arrows_by_label = {a.label: a for a in arrows_tuple}

    cyclic_basis = enumerate_cyclic_words(arrows_tuple, max_length)
    blocks: dict[Block, list[CyclicWord]] = {}
    for length, words in cyclic_basis.items():
        for word in words:
            key: Block = (length, word.r_charge) if r_graded else (length, None)
            blocks.setdefault(key, []).append(word)

    column_basis: dict[Block, tuple[tuple[str, ...], ...]] = {
        key: tuple(w.arrows for w in words) for key, words in blocks.items()
    }
    column_index: dict[Block, dict[tuple[str, ...], int]] = {
        key: {cols: i for i, cols in enumerate(basis)}
        for key, basis in column_basis.items()
    }

    generators = _enumerate_generators(arrows_tuple, W_tuple)
    free_paths = _enumerate_free_paths(arrows_tuple, max_length)

    rows_by_block: dict[Block, list[tuple[Fraction, ...]]] = {key: [] for key in blocks}

    for gen in generators:
        n = gen["length"]
        context_endpoints = (gen["target"], gen["source"])  # source(C), target(C)
        # Length-0 generators arise from legitimate mass terms (e.g. ∂_Phi Tr(Phi)
        # = identity at the node, if R(Phi)=2). The resulting F-relation kills
        # cyclic words of every positive length through that node, but the
        # cyclic-word basis itself starts at length 1 — skip total_length=0.
        for total_length in range(max(1, n), max_length + 1):
            context_length = total_length - n
            contexts = free_paths.get((*context_endpoints, context_length), ())
            for context in contexts:
                row_dict: dict[tuple[str, ...], Fraction] = {}
                for path, coeff in gen["paths"].items():
                    closed_walk = context + path
                    canonical = _canonical_rotation(closed_walk)
                    row_dict[canonical] = row_dict.get(canonical, Fraction(0)) + coeff
                row_dict = {k: v for k, v in row_dict.items() if v != 0}
                if not row_dict:
                    continue

                sample = next(iter(row_dict))
                r_total = sum(
                    (arrows_by_label[label].r_charge for label in sample),
                    Fraction(0),
                )
                if r_graded and len(row_dict) > 1:
                    # Defensive: under P3 (each W term has R=2), every cyclic
                    # word in a single relation row has the same R-charge —
                    # rows live in one R-bucket. Catching this here turns a
                    # P3 violation into an explicit error instead of silently
                    # mis-bucketing the row. Step 4 should validate P3 first;
                    # this is belt-and-suspenders.
                    for other_canonical in row_dict:
                        if other_canonical is sample:
                            continue
                        r_other = sum(
                            (arrows_by_label[label].r_charge for label in other_canonical),
                            Fraction(0),
                        )
                        if r_other != r_total:
                            raise ValueError(
                                "build_relation_matrix(r_graded=True) requires "
                                "every W term to satisfy P3 (R=2). A relation "
                                "row mixes cyclic words of different R-charges: "
                                f"{sample!r} has R={r_total} but "
                                f"{other_canonical!r} has R={r_other}. "
                                "Validate P3 upstream (or use r_graded=False)."
                            )
                block_key: Block = (
                    (total_length, r_total) if r_graded else (total_length, None)
                )
                if block_key not in column_index:
                    # Should not happen: enumerate_cyclic_words covers every
                    # closed-walk class up to max_length.
                    raise RuntimeError(
                        f"row produced for unknown block {block_key} "
                        f"(canonical word {sample!r})"
                    )
                ncols = len(column_basis[block_key])
                indexer = column_index[block_key]
                dense = [Fraction(0)] * ncols
                for canonical, coeff in row_dict.items():
                    dense[indexer[canonical]] = coeff
                rows_by_block[block_key].append(tuple(dense))

    return {
        key: RelationMatrix(
            block=key,
            column_basis=column_basis[key],
            rows=tuple(rows_by_block[key]),
        )
        for key in column_basis
    }


def quotient_dimensions(
    arrows: Iterable[Arrow],
    W_terms: Iterable[SuperpotentialTerm],
    max_length: int,
    r_graded: bool = True,
) -> dict[Block, int]:
    """Convenience wrapper: per-block `|basis| - rank(M)`."""

    matrices = build_relation_matrix(arrows, W_terms, max_length, r_graded=r_graded)
    return {key: matrix.quotient_dimension for key, matrix in matrices.items()}


# Default cutoffs from design doc §3.1.
_BOUNDED_CHIRAL_RING_DEFAULT_MAX_LENGTH = 6
_BOUNDED_CHIRAL_RING_MAX_SUPPORTED = 8  # P6 hard cap
_BOUNDED_CHIRAL_RING_MIN_SUPPORTED = 1

# Registry keys for upstream anomaly obligations that gate P4 (see Phase 2a
# design doc §4 / phase2a_implementation.md). These keys come from
# `dualitycert/qft/checks.py`.
_UPSTREAM_ANOMALY_KEYS: tuple[str, ...] = (
    "electric_gauge_anomaly",
    "magnetic_gauge_anomaly",
    "electric_gauge_global_mixed_anomaly",
    "magnetic_gauge_global_mixed_anomaly",
)

_BOUNDED_CHIRAL_RING_LIMITATIONS: tuple[str, ...] = (
    "two-sided F-ideal generated only up to length L",
    "single-trace sector only",
    "cyclic rotation only — no orientation-reversal identification",
    "no quantum / instanton corrections",
    "no a-maximization, R-charges taken as claim input",
    "Casimir / tracelessness identities not imposed (out of scope per design doc §12)",
)


def bounded_chiral_ring_consistency_check(
    claim: DualityClaim,
    prior_results: Mapping[str, ObligationResult] | None = None,
) -> CheckResult:
    """Compare two pure_quiver theories block-wise on bounded cyclic-word
    quotient dimensions (design doc §6 / §7).

    Verdict:
      - CERTIFIED: every (length, r) block has equal electric and magnetic
        quotient dimension up to the cutoff.
      - FAILED: at least one block disagrees; details include the failing
        block(s), sample operators from each side, and dimension counts.
      - UNKNOWN: P6 violated (max_length outside [1, 8]) or a numeric
        pathology surfaced from build_relation_matrix.
      - NOT_APPLICABLE: P1 (pure_quiver on both sides) / P5 (W terms are
        closed monomial walks on known labels) violated, or in r_graded
        mode P3 (every W term has R=2) / P4 (upstream anomaly checks
        passed) failed.

    Reads `claim.metadata["bounded_chiral_ring"]`:
      - `max_length` (default 6, capped at 8 per design doc §3.1 / P6);
      - `require_r_graded` (default True). When False, P3/P4 failures are
        recorded as warnings and the comparison runs in length-only mode.

    Reads `prior_results` for the four upstream anomaly obligation keys
    (option A from design doc §14 step 4); a None argument is treated as
    an empty mapping so the function can be called directly.
    """

    if prior_results is None:
        prior_results = {}

    raw_metadata = claim.metadata.get("bounded_chiral_ring", {})
    max_length = int(raw_metadata.get("max_length", _BOUNDED_CHIRAL_RING_DEFAULT_MAX_LENGTH))
    require_r_graded = bool(raw_metadata.get("require_r_graded", True))

    base_details: dict = {
        "cutoff_L": max_length,
        # `r_graded` is the mandatory key from design doc §7: it records
        # whether this run actually executed in R-graded mode. Defaults to
        # False (early-fail paths never reach the comparison); the success
        # path overwrites it once `require_r_graded` and the P3/P4 blockers
        # are resolved. `require_r_graded` is also exposed separately so
        # consumers can distinguish "user asked for r_graded but it got
        # downgraded" from "user asked for length-only".
        "r_graded": False,
        "require_r_graded": require_r_graded,
        # `r_graded_blocked_by` defaults to [] so it is always present on
        # every path; the strict-P4 NOT_APPLICABLE and the success paths
        # overwrite it with the actual blocker list when applicable.
        "r_graded_blocked_by": [],
        "mod_cyclic_rotation": True,
        "orientation_preserved": True,
        "context_multiplied_ideal": True,
        "limitations": list(_BOUNDED_CHIRAL_RING_LIMITATIONS),
    }

    # --- P1: both sides must be pure_quiver --------------------------------
    e_kind = infer_theory_kind(claim.electric_theory)
    m_kind = infer_theory_kind(claim.magnetic_theory)
    if e_kind != PURE_QUIVER or m_kind != PURE_QUIVER:
        return CheckResult(
            status=Status.NOT_APPLICABLE,
            message=(
                "Bounded chiral-ring consistency only applies when both sides "
                f"are pure_quiver; got electric={e_kind}, magnetic={m_kind}."
            ),
            details={**base_details, "preconditions": {"P1": "fail"}},
        )

    # --- P6: cutoff range ---------------------------------------------------
    if (
        max_length < _BOUNDED_CHIRAL_RING_MIN_SUPPORTED
        or max_length > _BOUNDED_CHIRAL_RING_MAX_SUPPORTED
    ):
        return CheckResult(
            status=Status.UNKNOWN,
            message=(
                f"max_length={max_length} is outside the supported range "
                f"[{_BOUNDED_CHIRAL_RING_MIN_SUPPORTED}, "
                f"{_BOUNDED_CHIRAL_RING_MAX_SUPPORTED}] (design doc §3.1 / P6)."
            ),
            details={**base_details, "preconditions": {"P6": "fail"}},
        )

    # --- P5: extract arrows and validate W on each side ---------------------
    try:
        electric_arrows = extract_arrows(claim.electric_theory)
        validate_w_terms(electric_arrows, claim.electric_theory.superpotential_terms)
    except (PureQuiverShapeError, WTermShapeError) as exc:
        return CheckResult(
            status=Status.NOT_APPLICABLE,
            message=f"Electric side rejected by P5: {exc}",
            details={
                **base_details,
                "preconditions": {"P5_electric": "fail"},
                "rejection_reason": str(exc),
            },
        )
    try:
        magnetic_arrows = extract_arrows(claim.magnetic_theory)
        validate_w_terms(magnetic_arrows, claim.magnetic_theory.superpotential_terms)
    except (PureQuiverShapeError, WTermShapeError) as exc:
        return CheckResult(
            status=Status.NOT_APPLICABLE,
            message=f"Magnetic side rejected by P5: {exc}",
            details={
                **base_details,
                "preconditions": {"P5_magnetic": "fail"},
                "rejection_reason": str(exc),
            },
        )

    # --- P3: every W term has total R-charge equal to 2 ---------------------
    # Sum over Arrow.r_charge (keyed by machine label) so the check works on
    # multi-arrow expansions where Field.name != Arrow.label (a Field with
    # multiplicity m > 1 expands to labels f"{Field.name}[{i}]" per §3.2,
    # and the W term must reference those machine labels). Using
    # theory.field_map() would falsely report "unknown field 'X[0]'" on any
    # multi-arrow fixture.
    p3_failures = _check_p3_w_term_r_charges(
        claim.electric_theory, electric_arrows, "electric"
    )
    p3_failures += _check_p3_w_term_r_charges(
        claim.magnetic_theory, magnetic_arrows, "magnetic"
    )

    # --- P4: upstream anomaly obligations passed on both sides --------------
    # Strict interpretation (design doc §4 / §8): r_graded mode requires a
    # physically meaningful U(1)_R, which means the upstream anomaly checks
    # must have returned CERTIFIED on both sides. Missing entries (the check
    # was filtered out of the registry or prior_results was supplied empty by
    # a direct caller) and NOT_APPLICABLE entries (e.g. no U(1)_R global
    # symmetry was encoded, so the mixed anomaly could not even compute)
    # both block r_graded mode — they leave the R-grading on Field.r_charge
    # values without an anomaly-free guarantee. Callers that want to proceed
    # anyway must set require_r_graded=false to opt into length-only fallback.
    p4_failures: list[str] = []
    for key in _UPSTREAM_ANOMALY_KEYS:
        result = prior_results.get(key)
        if result is None:
            p4_failures.append(
                f"{key} did not run (missing from prior_results — upstream "
                "obligation must produce CERTIFIED for r_graded mode)"
            )
            continue
        if result.status != Status.CERTIFIED:
            p4_failures.append(f"{key} returned {result.status.value}: {result.message}")

    r_graded_blocked_by: list[str] = []
    if p3_failures:
        r_graded_blocked_by.append("P3")
    if p4_failures:
        r_graded_blocked_by.append("P4")

    if require_r_graded and r_graded_blocked_by:
        return CheckResult(
            status=Status.NOT_APPLICABLE,
            message=(
                "r_graded mode requires P3 (every W term has R=2) and P4 "
                "(upstream gauge anomalies pass) on both sides. Blocked by: "
                f"{', '.join(r_graded_blocked_by)}. Set "
                "metadata['bounded_chiral_ring']['require_r_graded']=false "
                "to fall back to length-only comparison, or fix the upstream "
                "obligation."
            ),
            details={
                **base_details,
                "preconditions": {
                    "P1": "pass",
                    "P3": "pass" if not p3_failures else "fail",
                    "P4": "pass" if not p4_failures else "fail",
                    "P5_electric": "pass",
                    "P5_magnetic": "pass",
                    "P6": "pass",
                },
                "r_graded_blocked_by": r_graded_blocked_by,
                "p3_failures": p3_failures,
                "p4_failures": p4_failures,
            },
        )

    # --- Compute quotient dimensions on each side --------------------------
    r_graded_effective = require_r_graded and not r_graded_blocked_by
    try:
        electric_dims = quotient_dimensions(
            electric_arrows,
            claim.electric_theory.superpotential_terms,
            max_length=max_length,
            r_graded=r_graded_effective,
        )
        magnetic_dims = quotient_dimensions(
            magnetic_arrows,
            claim.magnetic_theory.superpotential_terms,
            max_length=max_length,
            r_graded=r_graded_effective,
        )
    except (ValueError, RuntimeError) as exc:
        # We reach here only after every pre-condition passed, so they all
        # carry "pass" / "pass (length-only fallback)" semantics consistent
        # with the success path. The always-present schema contract
        # (design doc §7) requires `preconditions` on every verdict path.
        return CheckResult(
            status=Status.UNKNOWN,
            message=f"Quotient-dimension computation failed: {exc}",
            details={
                **base_details,
                "preconditions": {
                    "P1": "pass",
                    "P3": "pass" if not p3_failures else "fail (length-only fallback)",
                    "P4": "pass" if not p4_failures else "fail (length-only fallback)",
                    "P5_electric": "pass",
                    "P5_magnetic": "pass",
                    "P6": "pass",
                },
                "compute_error": str(exc),
            },
        )

    # --- Per-block comparison ---------------------------------------------
    all_blocks = set(electric_dims) | set(magnetic_dims)
    tested_blocks: list[dict] = []
    failed_blocks: list[dict] = []

    for block in sorted(all_blocks, key=_block_sort_key):
        e_dim = electric_dims.get(block, 0)
        m_dim = magnetic_dims.get(block, 0)
        record = {
            "length": block[0],
            "r_charge": str(block[1]) if block[1] is not None else None,
            "electric_dim": e_dim,
            "magnetic_dim": m_dim,
        }
        tested_blocks.append(record)
        if e_dim != m_dim:
            failed_blocks.append(record)

    sample_operators = (
        _collect_sample_operators(
            electric_arrows,
            magnetic_arrows,
            failed_blocks,
            max_length=max_length,
            r_graded=r_graded_effective,
        )
        if failed_blocks
        else {}
    )

    details = {
        **base_details,
        "r_graded": r_graded_effective,
        "r_graded_blocked_by": r_graded_blocked_by,
        "tested_blocks": tested_blocks,
        "failed_blocks": failed_blocks,
        "sample_operators": sample_operators,
        "arrow_machine_labels_electric": sorted(a.label for a in electric_arrows),
        "arrow_machine_labels_magnetic": sorted(a.label for a in magnetic_arrows),
        "preconditions": {
            "P1": "pass",
            "P3": "pass" if not p3_failures else "fail (length-only fallback)",
            "P4": "pass" if not p4_failures else "fail (length-only fallback)",
            "P5_electric": "pass",
            "P5_magnetic": "pass",
            "P6": "pass",
        },
    }

    warnings: list[str] = [
        "PASS only means block-wise dimension agreement up to cutoff L — "
        "this does NOT imply chiral-ring equivalence.",
    ]
    if not r_graded_effective:
        warnings.append(
            "Comparison ran in length-only mode (r_graded=False) — accidental "
            "block-size coincidences across R-charges are invisible."
        )

    if failed_blocks:
        first = failed_blocks[0]
        return CheckResult(
            status=Status.FAILED,
            message=(
                f"FAILED_AT_BLOCK length={first['length']} "
                f"r_charge={first['r_charge']}: electric dim "
                f"{first['electric_dim']} != magnetic dim {first['magnetic_dim']} "
                f"({len(failed_blocks)} of {len(tested_blocks)} blocks differ)."
            ),
            details=details,
            warnings=tuple(warnings),
        )
    return CheckResult(
        status=Status.CERTIFIED,
        message=(
            f"PASSED_BOUNDED_CHIRAL_RING_CONSISTENCY at L={max_length} "
            f"({len(tested_blocks)} blocks)."
        ),
        details=details,
        warnings=tuple(warnings),
    )


def _check_p3_w_term_r_charges(
    theory: Theory,
    arrows: tuple[Arrow, ...],
    side: str,
) -> list[str]:
    """Return a list of human-readable strings describing every W term on
    `theory` whose total **machine-label-keyed** R-charge is not 2 (P3
    violation, design doc §4). Empty list ⇒ P3 passes on this side.

    Uses `Arrow.label` rather than `Field.name` so multi-arrow expansion
    (§3.2) is handled correctly: a Field "X" with multiplicity 2 is
    visible here as arrows labelled "X[0]", "X[1]", matching what the W
    term must reference.
    """

    arrows_by_label = {arrow.label: arrow for arrow in arrows}
    failures: list[str] = []
    for term in theory.superpotential_terms:
        total = Fraction(0)
        missing_label: str | None = None
        for name in term.field_names:
            if name not in arrows_by_label:
                missing_label = name
                break
            total += arrows_by_label[name].r_charge
        if missing_label is not None:
            # validate_w_terms should have already caught this; defensive.
            failures.append(
                f"{side} term {term.display_name!r} references unknown arrow "
                f"label {missing_label!r}"
            )
            continue
        if total != Fraction(2):
            failures.append(
                f"{side} term {term.display_name!r} has total R-charge {total}, expected 2"
            )
    return failures


def _block_sort_key(block: Block) -> tuple:
    """Sort blocks by length, then by R-charge (None last)."""
    length, r_charge = block
    if r_charge is None:
        return (length, 1, Fraction(0))
    return (length, 0, r_charge)


def _collect_sample_operators(
    electric_arrows: tuple[Arrow, ...],
    magnetic_arrows: tuple[Arrow, ...],
    failed_blocks: list[dict],
    *,
    max_length: int,
    r_graded: bool,
    samples_per_side: int = 2,
) -> dict[str, dict[str, list]]:
    """For each failed block, list up to `samples_per_side` canonical cyclic
    words from each side at that block. Used to populate the certificate's
    diagnostic on mismatch — not part of the verdict logic."""

    def words_for_side(arrows: tuple[Arrow, ...]) -> dict[Block, list[CyclicWord]]:
        words = enumerate_cyclic_words(arrows, max_length)
        bucketed: dict[Block, list[CyclicWord]] = {}
        for length, block in words.items():
            for word in block:
                key: Block = (length, word.r_charge) if r_graded else (length, None)
                bucketed.setdefault(key, []).append(word)
        return bucketed

    electric_words = words_for_side(electric_arrows)
    magnetic_words = words_for_side(magnetic_arrows)

    result: dict[str, dict[str, list]] = {}
    for record in failed_blocks:
        length = record["length"]
        r_charge_str = record["r_charge"]
        r_charge = Fraction(r_charge_str) if r_charge_str is not None else None
        block: Block = (length, r_charge)
        block_label = f"length={length},r={r_charge_str}"
        result[block_label] = {
            "electric": [
                list(w.arrows) for w in electric_words.get(block, [])[:samples_per_side]
            ],
            "magnetic": [
                list(w.arrows) for w in magnetic_words.get(block, [])[:samples_per_side]
            ],
        }
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


def _enumerate_generators(
    arrows: tuple[Arrow, ...],
    W_terms: tuple[SuperpotentialTerm, ...],
) -> list[dict]:
    """Split each ∂_X W into homogeneous generators by path length.

    Returns one record per (arrow X, path_length) with at least one
    surviving path. Different arrows X give independent generators even
    if their endpoints match: each contributes its own relation rows.
    """

    records: list[dict] = []
    for arrow in arrows:
        derivative = cyclic_derivative(W_terms, arrow)
        if not derivative:
            continue
        paths_by_length: dict[int, dict[tuple[str, ...], Fraction]] = {}
        for path, coeff in derivative.items():
            paths_by_length.setdefault(len(path), {})[path] = coeff
        for path_length, paths in paths_by_length.items():
            records.append(
                {
                    "arrow_label": arrow.label,
                    "source": arrow.target,   # source(g) = target(X)
                    "target": arrow.source,   # target(g) = source(X)
                    "length": path_length,
                    "paths": paths,
                }
            )
    return records


def _enumerate_free_paths(
    arrows: tuple[Arrow, ...],
    max_length: int,
) -> dict[tuple[str, str, int], tuple[tuple[str, ...], ...]]:
    """Enumerate all free (un-quotiented) paths up to `max_length`, indexed
    by `(source, target, length)`.

    Length 0 = the empty path / node idempotent `e_v`. It exists for every
    gauge node and has `source == target == v`. Higher lengths are
    generated by DFS over the arrow adjacency.
    """

    by_source: dict[str, list[Arrow]] = defaultdict(list)
    for arrow in arrows:
        by_source[arrow.source].append(arrow)

    nodes: set[str] = set()
    for arrow in arrows:
        nodes.add(arrow.source)
        nodes.add(arrow.target)

    paths: dict[tuple[str, str, int], list[tuple[str, ...]]] = defaultdict(list)
    for node in nodes:
        paths[(node, node, 0)].append(())

    frontier: list[tuple[str, str, tuple[str, ...]]] = [
        (node, node, ()) for node in nodes
    ]
    for current_length in range(max_length):
        next_frontier: list[tuple[str, str, tuple[str, ...]]] = []
        for source, head, labels in frontier:
            for arrow in by_source.get(head, ()):
                new_labels = labels + (arrow.label,)
                paths[(source, arrow.target, current_length + 1)].append(new_labels)
                next_frontier.append((source, arrow.target, new_labels))
        frontier = next_frontier
        if not frontier:
            break

    return {key: tuple(value) for key, value in paths.items()}


def _gaussian_rank(rows: tuple[tuple[Fraction, ...], ...], num_cols: int) -> int:
    """Exact rank of a Fraction matrix via Gaussian elimination in row-echelon
    form. Matrices stay tiny at the Phase 2a cutoffs (max_length <= 8), so
    naive elimination is fast and avoids a sympy dependency."""

    if not rows or num_cols == 0:
        return 0
    matrix: list[list[Fraction]] = [list(row) for row in rows]
    rank = 0
    pivot_col = 0
    num_rows = len(matrix)
    while rank < num_rows and pivot_col < num_cols:
        pivot_row = None
        for row_index in range(rank, num_rows):
            if matrix[row_index][pivot_col] != 0:
                pivot_row = row_index
                break
        if pivot_row is None:
            pivot_col += 1
            continue
        if pivot_row != rank:
            matrix[rank], matrix[pivot_row] = matrix[pivot_row], matrix[rank]
        pivot = matrix[rank][pivot_col]
        matrix[rank] = [entry / pivot for entry in matrix[rank]]
        for row_index in range(num_rows):
            if row_index == rank:
                continue
            factor = matrix[row_index][pivot_col]
            if factor == 0:
                continue
            matrix[row_index] = [
                a - factor * b for a, b in zip(matrix[row_index], matrix[rank])
            ]
        rank += 1
        pivot_col += 1
    return rank


__all__ = [
    "Arrow",
    "Block",
    "CyclicWord",
    "PureQuiverShapeError",
    "RelationMatrix",
    "WTermShapeError",
    "bounded_chiral_ring_consistency_check",
    "build_relation_matrix",
    "cyclic_derivative",
    "enumerate_cyclic_words",
    "extract_arrows",
    "quotient_dimensions",
    "validate_w_terms",
]
