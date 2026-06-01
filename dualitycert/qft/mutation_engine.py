"""Single-node Seiberg mutation engine (Phase 2c0 MVP).

Two stand-alone JSON-in / JSON-out functions, independent of the
verifier (no `evaluate_claim` / `Theory` imports at runtime — only
the JSON-schema helpers from `pure_quiver_json` for label conventions):

  - `mutate_bare(theory_json, *, node)` — mechanical Seiberg duality at
    one node: reverse incident arrows, add all bypass mesons, write the
    pre-integration superpotential (mass term inherited from the
    electric W plus the bare Seiberg coupling). Output may legitimately
    FAIL the bounded chiral-ring check; that's the unit-test's job.

  - `integrate_linear_fields(theory_json)` — minimum-scope F-equation
    elimination: identify fields appearing linearly in W whose `∂_F W`
    is a *homogeneous linear polynomial in single-field-component
    monomials*. Solve the linear system, drop the auxiliary field plus
    the pivot field-components, substitute equivalences in the
    remaining W, and re-index labels to the canonical
    `X{i}{j}[k]` per-edge packing.

See `docs/phase2c0_mutation_engine.md` for the full spec and locked
scope (no general F-term Gröbner, no quadratic mass matrices, no
adjoint loops at the dualized node).
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any, Mapping

from dualitycert.qft.pure_quiver_builder import _arrow_base_name


__all__ = [
    "mutate_bare",
    "integrate_linear_fields",
    "integrate_fields",
    "MutationEngineError",
]


# Safety bounds for the general quadratic reduction (Stage 3). The
# physical reduction terminates (DWZ Splitting Theorem); these guard
# against a transcription bug / out-of-scope input looping or blowing up
# the W degree instead of raising an informative error.
_MAX_REDUCTION_STEPS = 1000
_MAX_W_DEGREE = 16


class MutationEngineError(ValueError):
    """Raised when the mutation engine is asked to do something outside
    the Phase 2c0 MVP scope (multi-visit W terms, adjoint loops at the
    dualized node, anomaly mismatch, nonlinear F-equations, ...).

    The error is intentionally informative — engine users (the LLM
    harness, mutation chain runner) should pattern-match on the message
    rather than catching generic ValueErrors.
    """


def mutate_bare(theory_json: Mapping[str, Any], *, node: int) -> dict[str, Any]:
    """Apply bare single-node Seiberg duality at gauge node `node`.

    Output is a fresh JSON-compatible dict (the input is not mutated).
    The output's W is the pre-integration form; the bounded chiral-ring
    check is expected to FAIL until `integrate_linear_fields` runs.
    """

    arrows = [dict(a) for a in theory_json["arrows"]]
    ranks = list(theory_json["ranks"])
    node_labels = list(theory_json["node_labels"])
    u1_globals = list(theory_json.get("u1_globals", []))
    name = theory_json["name"]
    superpotential = [
        {"factors": list(t["factors"]), "coefficient": t["coefficient"]}
        for t in theory_json["superpotential"]
    ]

    if not (0 <= node < len(ranks)):
        raise MutationEngineError(
            f"node index {node} out of range for {len(ranks)}-node quiver"
        )

    # ------------------------------------------------------------------
    # 1. Classify arrows incident to `node`.
    # ------------------------------------------------------------------
    in_arrows: list[dict[str, Any]] = []
    out_arrows: list[dict[str, Any]] = []
    untouched: list[dict[str, Any]] = []
    for a in arrows:
        s, t = int(a["source"]), int(a["target"])
        if s == node and t == node:
            raise MutationEngineError(
                f"adjoint loop {a['label']!r} at the dualized node {node} "
                "is out of MVP scope (Kutasov-style mutations not supported)"
            )
        if t == node:
            in_arrows.append(a)
        elif s == node:
            out_arrows.append(a)
        else:
            untouched.append(a)

    if not in_arrows or not out_arrows:
        raise MutationEngineError(
            f"node {node} has in-degree {len(in_arrows)} and out-degree "
            f"{len(out_arrows)}; Seiberg mutation needs both > 0"
        )

    # ------------------------------------------------------------------
    # 2. Compute new gauge rank from anomaly cancellation.
    # ------------------------------------------------------------------
    N_in = sum(ranks[int(a["source"])] for a in in_arrows)
    N_out = sum(ranks[int(a["target"])] for a in out_arrows)
    if N_in != N_out:
        raise MutationEngineError(
            f"node {node} is not cubic-anomaly-free under the proposed "
            f"mutation: in-flavor count {N_in} != out-flavor count {N_out}"
        )
    N_c = ranks[node]
    N_m = N_in - N_c
    if N_m < 2:
        raise MutationEngineError(
            f"magnetic rank N_m = N_f - N_c = {N_in} - {N_c} = {N_m} < 2, "
            "not supported by SU(N) builder (free magnetic phase / "
            "confinement is out of MVP scope)"
        )

    new_ranks = list(ranks)
    new_ranks[node] = N_m
    new_node_labels = list(node_labels)
    new_node_labels[node] = f"SU({N_m})_{node}"

    # ------------------------------------------------------------------
    # 3. Reverse incident arrows. Build a label rewrite map so the W
    #    rewrite step can refer to original labels.
    # ------------------------------------------------------------------
    new_arrows_by_edge: dict[tuple[int, int], list[dict[str, Any]]] = {}
    relabel_map: dict[str, str] = {}

    def _add_arrow(edge_key: tuple[int, int], r_charge: Fraction) -> str:
        """Allocate a fresh machine label on `edge_key` and return it."""

        bucket = new_arrows_by_edge.setdefault(edge_key, [])
        k = len(bucket)
        label = f"{_arrow_base_name(*edge_key)}[{k}]"
        bucket.append(
            {
                "label": label,
                "source": edge_key[0],
                "target": edge_key[1],
                "r_charge": str(r_charge),
            }
        )
        return label

    # 3a. Untouched arrows keep their (source, target) but get re-indexed
    # within the new per-edge expansion so labels stay canonical.
    for a in untouched:
        edge_key = (int(a["source"]), int(a["target"]))
        new_label = _add_arrow(edge_key, Fraction(a["r_charge"]))
        relabel_map[a["label"]] = new_label

    # 3b. Reversed in-arrows: original (u, node) → new (node, u). The
    # quark R-charge dualizes as R(q̃) = 1 - R(Q).
    for a in in_arrows:
        u = int(a["source"])
        edge_key = (node, u)
        r_new = Fraction(1, 1) - Fraction(a["r_charge"])
        new_label = _add_arrow(edge_key, r_new)
        relabel_map[a["label"]] = new_label

    # 3c. Reversed out-arrows: (node, w) → (w, node), R(q) = 1 - R(Q').
    for a in out_arrows:
        w = int(a["target"])
        edge_key = (w, node)
        r_new = Fraction(1, 1) - Fraction(a["r_charge"])
        new_label = _add_arrow(edge_key, r_new)
        relabel_map[a["label"]] = new_label

    # 3d. Bypass mesons: for each (in_arrow, out_arrow) pair, add a meson
    # on edge (source(in), target(out)) with R = R(in) + R(out). A DIAGONAL
    # meson (source(in) == target(out) = u) is M_uu = Q̃_u Q_u, which under
    # SU(N_u) decomposes as adjoint ⊕ singlet; the arrow carries the adjoint,
    # so we also emit a gauge-singlet field S_u for the trace part.
    meson_label_for_pair: dict[tuple[str, str], str] = {}
    meson_label_set: set[str] = set()
    singlet_for_pair: dict[tuple[str, str], str] = {}
    singlets_payload: list[dict[str, str]] = []
    singlet_counts: dict[int, int] = {}
    for in_a in in_arrows:
        u = int(in_a["source"])
        r_in = Fraction(in_a["r_charge"])
        for out_a in out_arrows:
            w = int(out_a["target"])
            r_out = Fraction(out_a["r_charge"])
            edge_key = (u, w)
            label = _add_arrow(edge_key, r_in + r_out)
            meson_label_for_pair[(in_a["label"], out_a["label"])] = label
            meson_label_set.add(label)
            if u == w:
                k = singlet_counts.get(u, 0)
                singlet_counts[u] = k + 1
                s_label = f"S{u}[{k}]"
                singlets_payload.append(
                    {"label": s_label, "r_charge": str(r_in + r_out)}
                )
                singlet_for_pair[(in_a["label"], out_a["label"])] = s_label

    # ------------------------------------------------------------------
    # 4. Flatten new_arrows_by_edge into the JSON list, ordered by edge.
    # ------------------------------------------------------------------
    new_arrows: list[dict[str, Any]] = []
    for edge_key in sorted(new_arrows_by_edge):
        new_arrows.extend(new_arrows_by_edge[edge_key])

    # ------------------------------------------------------------------
    # 5. Rewrite W: replace each (in, out) adjacency at `node` with the
    #    matching meson; relabel non-incident factors via relabel_map.
    # ------------------------------------------------------------------
    in_labels = {a["label"] for a in in_arrows}
    out_labels = {a["label"] for a in out_arrows}

    new_W: list[dict[str, Any]] = []
    for term in superpotential:
        factors = list(term["factors"])
        new_factors = _rewrite_term_through_node(
            factors,
            in_labels=in_labels,
            out_labels=out_labels,
            meson_label_for_pair=meson_label_for_pair,
            relabel_map=relabel_map,
            node=node,
        )
        new_W.append(
            {"factors": new_factors, "coefficient": str(Fraction(term["coefficient"]))}
        )

    # ------------------------------------------------------------------
    # 6. Add bare Seiberg coupling: for each meson M_{(α,β)} on edge
    #    (u, w), the closed walk q[β] · q̃[α] · M closes w → node → u → w.
    # ------------------------------------------------------------------
    for in_a in in_arrows:
        for out_a in out_arrows:
            meson_label = meson_label_for_pair[(in_a["label"], out_a["label"])]
            q_label = relabel_map[out_a["label"]]  # reversed out-arrow
            qtilde_label = relabel_map[in_a["label"]]  # reversed in-arrow
            new_W.append(
                {
                    "factors": [q_label, qtilde_label, meson_label],
                    "coefficient": "1",
                }
            )
            # Singlet half of a diagonal meson: S_u · (q q̃ trace part).
            s_label = singlet_for_pair.get((in_a["label"], out_a["label"]))
            if s_label is not None:
                new_W.append(
                    {
                        "factors": [s_label, q_label, qtilde_label],
                        "coefficient": "1",
                    }
                )

    result = {
        "name": f"{name} (Seiberg-mutated at node {node}, bare)",
        "node_labels": new_node_labels,
        "ranks": new_ranks,
        "u1_globals": u1_globals,
        "arrows": new_arrows,
        "superpotential": new_W,
    }
    if singlets_payload:
        result["singlets"] = singlets_payload
    return result


def _rewrite_term_through_node(
    factors: list[str],
    *,
    in_labels: set[str],
    out_labels: set[str],
    meson_label_for_pair: dict[tuple[str, str], str],
    relabel_map: dict[str, str],
    node: int,
) -> list[str]:
    """Substitute the (in, out) adjacency at `node` with its meson label.

    Algorithm: rotate the cyclic factor tuple so an in-arrow at `node`
    immediately precedes an out-arrow at `node`. The MVP requires this
    pair to occur exactly once per W term. Returns the new factor list
    in the rotated order with the (in, out) pair collapsed to the meson.
    """

    n = len(factors)
    if n < 2:
        # Length-1 W term cannot traverse `node` (no in/out pair).
        return [relabel_map.get(f, f) for f in factors]

    # Build the node sequence: the "entered node" before factor i is the
    # source of factor i, which equals the target of factor (i - 1) mod n.
    # We need to find positions (i, i+1) such that factors[i] is an
    # in-arrow at `node` and factors[i+1 mod n] is an out-arrow at `node`.
    hit_positions: list[int] = []
    for i in range(n):
        if factors[i] in in_labels and factors[(i + 1) % n] in out_labels:
            hit_positions.append(i)

    if len(hit_positions) == 0:
        # The W term doesn't traverse `node` — leave it alone (after
        # relabeling of any untouched factors).
        return [relabel_map.get(f, f) for f in factors]

    if len(hit_positions) > 1:
        raise MutationEngineError(
            "MVP scope violation: W term "
            f"{factors!r} traverses dualized node {node} multiple times; "
            "needs general meson-substitution semantics"
        )

    pivot = hit_positions[0]
    # Rotate so factors[pivot] is at index 0 and factors[pivot+1] at index 1.
    rotated = factors[pivot:] + factors[:pivot]
    in_label = rotated[0]
    out_label = rotated[1]
    meson_label = meson_label_for_pair[(in_label, out_label)]
    # Replace the (in, out) pair with the meson; relabel the rest.
    rest = [relabel_map.get(f, f) for f in rotated[2:]]
    return [meson_label] + rest


# ----------------------------------------------------------------------
# Stage 2: linear-field integration.
# ----------------------------------------------------------------------


def integrate_linear_fields(theory_json: Mapping[str, Any]) -> dict[str, Any]:
    """Eliminate fields appearing linearly in W via their F-equations.

    Single-pass MVP: iterates the find/solve/substitute loop until no
    progress. Per the Phase 2c0 spec, only handles linear auxiliary
    fields whose `∂_F W` is a homogeneous linear polynomial in
    individual field components (no quadratic / cross-product F-equations).
    """

    arrows = [dict(a) for a in theory_json["arrows"]]
    ranks = list(theory_json["ranks"])
    node_labels = list(theory_json["node_labels"])
    u1_globals = list(theory_json.get("u1_globals", []))
    singlets = [dict(s) for s in theory_json.get("singlets", [])]
    name = theory_json["name"]
    superpotential = [
        {"factors": list(t["factors"]), "coefficient": Fraction(t["coefficient"])}
        for t in theory_json["superpotential"]
    ]
    arrow_by_label: dict[str, dict[str, Any]] = {a["label"]: a for a in arrows}

    while True:
        progress = _integration_pass(
            arrows=arrows,
            arrow_by_label=arrow_by_label,
            superpotential=superpotential,
        )
        if not progress:
            break

    # Recanonicalize arrow labels: per-edge re-index 0..k-1 in the
    # current relative ordering, so the surviving JSON matches the
    # `X{i}{j}[k]` builder convention.
    final_arrows, final_W = _recanonicalize_labels(arrows, superpotential)

    result: dict[str, Any] = {
        "name": f"{name} (integrated)",
        "node_labels": node_labels,
        "ranks": ranks,
        "u1_globals": u1_globals,
        "arrows": final_arrows,
        "superpotential": [
            {"factors": list(t["factors"]), "coefficient": str(t["coefficient"])}
            for t in final_W
        ],
    }
    if singlets:
        result["singlets"] = singlets
    return result


def _integration_pass(
    *,
    arrows: list[dict[str, Any]],
    arrow_by_label: dict[str, dict[str, Any]],
    superpotential: list[dict[str, Any]],
) -> bool:
    """Run one pass of linear-field elimination. Mutates inputs in place.

    Returns True iff something changed.
    """

    linear_field = _find_linear_field(superpotential, arrows)
    if linear_field is None:
        return False

    derivative_terms = _partial_derivative(superpotential, linear_field)

    # MVP guard: every monomial in ∂_F W must be a single-field-component
    # linear monomial (no products of two or more fields).
    all_other_labels = {a["label"] for a in arrows if a["label"] != linear_field}
    for coeff, factors in derivative_terms:
        if len(factors) != 1:
            raise MutationEngineError(
                f"∂W/∂{linear_field} has a non-linear monomial "
                f"(factors {factors!r}); MVP scope is single-component "
                "linear F-equations only"
            )
        if factors[0] not in all_other_labels:
            raise MutationEngineError(
                f"∂W/∂{linear_field} references unknown field "
                f"{factors[0]!r}"
            )

    # ------------------------------------------------------------------
    # Build the linear system A · v = 0.
    # Rows: one per copy of the linear field whose ∂W constraint we read.
    # The linear field may have multiple copies (e.g. X_BC[0..2]); each
    # copy's ∂W gives one row. We collect all linear field labels that
    # are siblings (same base name) and group their ∂W into rows.
    # ------------------------------------------------------------------
    sibling_labels = _sibling_field_labels(linear_field, arrows)
    columns: list[str] = []
    column_index: dict[str, int] = {}
    rows: list[list[Fraction]] = []
    for sibling in sibling_labels:
        derivative = _partial_derivative(superpotential, sibling)
        if not derivative:
            # This sibling doesn't appear in W; skip — no constraint.
            continue
        row_vector = [Fraction(0)] * len(columns)
        for coeff, factors in derivative:
            if len(factors) != 1:
                raise MutationEngineError(
                    f"∂W/∂{sibling} has a non-linear monomial "
                    f"(factors {factors!r}); MVP scope is single-component "
                    "linear F-equations only"
                )
            col_label = factors[0]
            if col_label not in column_index:
                column_index[col_label] = len(columns)
                columns.append(col_label)
                for r in rows:
                    r.append(Fraction(0))
                row_vector.append(Fraction(0))
            row_vector[column_index[col_label]] += coeff
        rows.append(row_vector)

    # Reduced row echelon form via Fraction arithmetic.
    rref_rows, pivot_columns = _rref(rows, num_cols=len(columns))

    # For each pivot column, derive the substitution rule:
    #   pivot_var = -(1/pivot_coeff) · sum_{non-pivot cols} coeff · var
    substitutions: dict[str, list[tuple[str, Fraction]]] = {}
    for row, pivot_col in zip(rref_rows, pivot_columns):
        pivot_var = columns[pivot_col]
        pivot_coeff = row[pivot_col]
        non_pivot_terms: list[tuple[str, Fraction]] = []
        for j, coeff in enumerate(row):
            if j == pivot_col or coeff == 0:
                continue
            # row[pivot_col] · pivot_var + row[j] · columns[j] + ... = 0
            # pivot_var = -row[j] / pivot_coeff · columns[j] + ...
            non_pivot_terms.append((columns[j], -coeff / pivot_coeff))
        # MVP requires that the substitution is a single-term identification
        # (so e.g. M_{(2,1)} = M_{(1,2)} works, but M = X + Y does not).
        if len(non_pivot_terms) != 1:
            raise MutationEngineError(
                f"pivot {pivot_var!r} needs nontrivial substitution "
                f"(non-pivot terms: {non_pivot_terms!r}); MVP only handles "
                "single-term identifications"
            )
        substitutions[pivot_var] = non_pivot_terms

    # ------------------------------------------------------------------
    # Apply substitutions in W; drop W terms containing siblings.
    # ------------------------------------------------------------------
    new_W: list[dict[str, Any]] = []
    sibling_set = set(sibling_labels)
    for term in superpotential:
        if any(f in sibling_set for f in term["factors"]):
            # The linear field F-equation collapses these terms to 0
            # in the chiral ring (mass-pair integration).
            continue
        new_factors = []
        coeff_multiplier = Fraction(1)
        for f in term["factors"]:
            if f in substitutions:
                replacement, mult = substitutions[f][0]
                new_factors.append(replacement)
                coeff_multiplier *= mult
            else:
                new_factors.append(f)
        new_W.append(
            {
                "factors": new_factors,
                "coefficient": term["coefficient"] * coeff_multiplier,
            }
        )

    # ------------------------------------------------------------------
    # Drop linear-field siblings and pivot columns from the arrows list.
    # ------------------------------------------------------------------
    dropped_labels = sibling_set | set(substitutions)
    surviving_arrows = [a for a in arrows if a["label"] not in dropped_labels]
    # Mutate the caller's lists in place.
    arrows[:] = surviving_arrows
    arrow_by_label.clear()
    arrow_by_label.update({a["label"]: a for a in surviving_arrows})
    superpotential[:] = new_W
    return True


def _find_linear_field(
    superpotential: list[dict[str, Any]],
    arrows: list[dict[str, Any]],
) -> str | None:
    """Find a field appearing at most once per W term, but in ≥1 W term."""

    appearances: dict[str, int] = {}
    multi_appearances: set[str] = set()
    for term in superpotential:
        seen_in_term: dict[str, int] = {}
        for f in term["factors"]:
            seen_in_term[f] = seen_in_term.get(f, 0) + 1
        for f, count in seen_in_term.items():
            if count > 1:
                multi_appearances.add(f)
            appearances[f] = appearances.get(f, 0) + 1

    # Pick the linear field with the lowest label (deterministic). Only
    # genuine arrow fields are integrable; gauge singlets that appear in W
    # are never selected (they carry no edge / sibling structure).
    arrow_labels = {a["label"] for a in arrows}
    candidates = sorted(
        f for f in appearances
        if f not in multi_appearances and appearances[f] >= 1 and f in arrow_labels
    )
    if not candidates:
        return None
    # Among candidates, prefer one whose ∂W is purely degree-1.
    # We need to actually try the elimination — but checking degree-1
    # is cheap; defer to caller. For now, return the first candidate
    # whose derivative is non-empty and pure degree-1.
    for f in candidates:
        deriv = _partial_derivative(superpotential, f)
        if not deriv:
            continue
        if all(len(factors) == 1 for _, factors in deriv):
            return f
    return None


def _partial_derivative(
    superpotential: list[dict[str, Any]],
    target_label: str,
) -> list[tuple[Fraction, list[str]]]:
    """Compute the cyclic-derivative-style partial of W w.r.t. `target_label`.

    For a pure-quiver pre-integration W where `target_label` appears
    linearly, the cyclic derivative reduces to: remove one occurrence
    of `target_label` from each containing W term, leaving the residual
    monomial in the other factors. The residual is what enters the
    F-equation `∂_F W = 0`.

    Returns a list of (coefficient, residual_factors) summands. The
    factor list preserves the cyclic order of remaining factors.
    """

    results: list[tuple[Fraction, list[str]]] = []
    for term in superpotential:
        factors = term["factors"]
        for i, f in enumerate(factors):
            if f == target_label:
                residual = list(factors[i + 1 :]) + list(factors[:i])
                results.append((Fraction(term["coefficient"]), residual))
    return results


def _sibling_field_labels(
    label: str,
    arrows: list[dict[str, Any]],
) -> list[str]:
    """Return all arrows on the same (source, target) edge as `label`.

    These are the "siblings" of the linear field whose F-equations form
    the constraint matrix. In dP_0, X12[0], X12[1], X12[2] are siblings.
    """

    target = next(a for a in arrows if a["label"] == label)
    edge_key = (int(target["source"]), int(target["target"]))
    return [
        a["label"]
        for a in arrows
        if (int(a["source"]), int(a["target"])) == edge_key
    ]


def _rref(
    matrix: list[list[Fraction]],
    *,
    num_cols: int,
) -> tuple[list[list[Fraction]], list[int]]:
    """Reduced row echelon form. Returns (reduced_rows, pivot_columns).

    Operates on Fractions; produces exact arithmetic. Trims zero rows
    from the output; the pivot columns are in column order so the rows
    align positionally.
    """

    rows = [list(r) for r in matrix]
    pivot_columns: list[int] = []
    pivot_row_for_col: dict[int, int] = {}
    current_row = 0
    for col in range(num_cols):
        # Find a row at index >= current_row with nonzero col entry.
        pivot = None
        for r_index in range(current_row, len(rows)):
            if rows[r_index][col] != 0:
                pivot = r_index
                break
        if pivot is None:
            continue
        rows[current_row], rows[pivot] = rows[pivot], rows[current_row]
        pivot_coeff = rows[current_row][col]
        rows[current_row] = [v / pivot_coeff for v in rows[current_row]]
        for r_index in range(len(rows)):
            if r_index == current_row:
                continue
            factor = rows[r_index][col]
            if factor == 0:
                continue
            rows[r_index] = [
                a - factor * b
                for a, b in zip(rows[r_index], rows[current_row])
            ]
        pivot_columns.append(col)
        pivot_row_for_col[col] = current_row
        current_row += 1
    reduced = [
        rows[pivot_row_for_col[c]]
        for c in pivot_columns
    ]
    return reduced, pivot_columns


def _recanonicalize_labels(
    arrows: list[dict[str, Any]],
    superpotential: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Pack surviving arrow labels into the X{i}{j}[0..k-1] canonical form."""

    by_edge: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for a in arrows:
        edge_key = (int(a["source"]), int(a["target"]))
        by_edge.setdefault(edge_key, []).append(a)

    rename: dict[str, str] = {}
    new_arrows: list[dict[str, Any]] = []
    for edge_key in sorted(by_edge):
        for k, a in enumerate(by_edge[edge_key]):
            new_label = f"{_arrow_base_name(*edge_key)}[{k}]"
            rename[a["label"]] = new_label
            new_arrows.append(
                {
                    "label": new_label,
                    "source": edge_key[0],
                    "target": edge_key[1],
                    "r_charge": str(Fraction(a["r_charge"])),
                }
            )

    new_W: list[dict[str, Any]] = []
    for term in superpotential:
        new_factors = [rename.get(f, f) for f in term["factors"]]
        new_W.append(
            {"factors": new_factors, "coefficient": term["coefficient"]}
        )

    return new_arrows, new_W


# ----------------------------------------------------------------------
# Stage 3: general quadratic reduction (DWZ reduction / mesonic
# integrate-out). Removes the mass terms the linear pass cannot reach,
# i.e. 2-cycles c·a·b whose F-equations involve paths of length >= 2.
# ----------------------------------------------------------------------


def integrate_fields(theory_json: Mapping[str, Any]) -> dict[str, Any]:
    """Full F-term integration: linear pass, then general DWZ reduction.

    Runs `integrate_linear_fields` first (the cheap, single-field-
    identification pass that reproduces the dp0/F_0 MVP byte-for-byte),
    then iteratively integrates out any remaining 2-cycle mass terms via
    their equations of motion (the step the linear pass cannot do because
    the F-equation `∂_F W` contains paths of length >= 2).

    For theories whose magnetic dual has no leftover quadratic terms
    (dp0, F_0) the second stage is a no-op, so the output is identical to
    `integrate_linear_fields`. For the more-connected seeds (C^3/Z2xZ2,
    dP_1, ...) it eliminates the spurious massive fields that otherwise
    break 't Hooft anomaly / central-charge / bounded-chiral-ring
    matching.
    """

    linear = integrate_linear_fields(theory_json)

    arrows = [dict(a) for a in linear["arrows"]]
    arrow_by_label: dict[str, dict[str, Any]] = {a["label"]: a for a in arrows}
    superpotential = [
        {"factors": list(t["factors"]), "coefficient": Fraction(t["coefficient"])}
        for t in linear["superpotential"]
    ]

    steps = 0
    while _reduce_one_quadratic(
        arrows=arrows,
        arrow_by_label=arrow_by_label,
        superpotential=superpotential,
        arrow_labels={a["label"] for a in arrows},
    ):
        steps += 1
        if steps > _MAX_REDUCTION_STEPS:
            raise MutationEngineError(
                "general quadratic reduction did not terminate after "
                f"{_MAX_REDUCTION_STEPS} steps; likely an out-of-scope "
                "coupled mass structure or a transcription bug"
            )
        max_deg = max((len(t["factors"]) for t in superpotential), default=0)
        if max_deg > _MAX_W_DEGREE:
            raise MutationEngineError(
                f"reduced W reached degree {max_deg} > cap {_MAX_W_DEGREE}; "
                "the integrate-out is blowing up (out-of-scope input)"
            )

    final_arrows, final_W = _recanonicalize_labels(arrows, superpotential)

    result: dict[str, Any] = {
        "name": linear["name"],
        "node_labels": list(linear["node_labels"]),
        "ranks": list(linear["ranks"]),
        "u1_globals": list(linear.get("u1_globals", [])),
        "arrows": final_arrows,
        "superpotential": [
            {"factors": list(t["factors"]), "coefficient": str(Fraction(t["coefficient"]))}
            for t in final_W
        ],
    }
    singlets = linear.get("singlets", [])
    if singlets:
        result["singlets"] = [dict(s) for s in singlets]
    return result


def _reduce_one_quadratic(
    *,
    arrows: list[dict[str, Any]],
    arrow_by_label: dict[str, dict[str, Any]],
    superpotential: list[dict[str, Any]],
    arrow_labels: set[str],
) -> bool:
    """Integrate out one 2-cycle mass term via its equations of motion.

    Picks the first length-2 W term ``c·a·b`` (a: i->j, b: j->i), solves
    the EOMs ``b = -P_a/c`` and ``a = -P_b/c`` where ``P_a`` / ``P_b`` are
    the residual paths from the *other* W terms, and rewrites

        W  ->  U  -  (1/c)·(P_a · P_b)

    with ``U`` the terms containing neither a nor b. Drops the arrows a, b
    and re-collects cyclically equal monomials. Mutates inputs in place.
    Returns True iff a mass term was found and reduced.
    """

    # A mass term is an arrow-arrow 2-cycle; a length-2 term containing a
    # gauge singlet is not a 2-cycle and must not be integrated out here.
    mass_idx = next(
        (
            i
            for i, t in enumerate(superpotential)
            if len(t["factors"]) == 2 and all(f in arrow_labels for f in t["factors"])
        ),
        None,
    )
    if mass_idx is None:
        return False

    mass = superpotential[mass_idx]
    c = Fraction(mass["coefficient"])
    a, b = mass["factors"][0], mass["factors"][1]
    if a == b:
        raise MutationEngineError(
            f"degenerate 2-cycle on a single field {a!r}; not a mass term"
        )

    others = [t for i, t in enumerate(superpotential) if i != mass_idx]
    p_a = _partial_derivative(others, a)  # paths j->i (replace b)
    p_b = _partial_derivative(others, b)  # paths i->j (replace a)

    # Scope guard: a clean integrate-out needs the EOM residuals to be
    # free of the integrated fields themselves. Self-reference means a
    # coupled mass matrix that the per-2-cycle recipe cannot diagonalize.
    for _coeff, factors in p_a + p_b:
        if a in factors or b in factors:
            raise MutationEngineError(
                f"mass term {a!r}·{b!r} is coupled (its F-equation still "
                "references the integrated fields); general mass-matrix "
                "diagonalization is out of current scope"
            )

    new_terms: list[dict[str, Any]] = [
        {"factors": list(t["factors"]), "coefficient": Fraction(t["coefficient"])}
        for t in others
        if a not in t["factors"] and b not in t["factors"]
    ]
    # Correction  -(1/c)·P_a·P_b : cyclic concatenation of every residual
    # path j->i (from P_a) with every residual path i->j (from P_b).
    for coeff_a, factors_a in p_a:
        for coeff_b, factors_b in p_b:
            new_terms.append(
                {
                    "factors": list(factors_a) + list(factors_b),
                    "coefficient": -(coeff_a * coeff_b) / c,
                }
            )

    collected = _collect_cyclic_terms(new_terms)

    dropped = {a, b}
    surviving = [ar for ar in arrows if ar["label"] not in dropped]
    arrows[:] = surviving
    arrow_by_label.clear()
    arrow_by_label.update({ar["label"]: ar for ar in surviving})
    superpotential[:] = collected
    return True


def _cyclic_canonical(factors: tuple[str, ...]) -> tuple[str, ...]:
    """Lexicographically minimal rotation — a canonical key for the cyclic
    word, so equal closed loops collect regardless of where they start."""

    n = len(factors)
    if n <= 1:
        return tuple(factors)
    return min(tuple(factors[i:] + factors[:i]) for i in range(n))


def _collect_cyclic_terms(
    terms: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Sum coefficients of cyclically-equal monomials; drop zero terms.

    Preserves first-seen order and the first-seen factor rotation as the
    representative (cyclic order is physically irrelevant in W)."""

    bucket: dict[tuple[str, ...], list[Any]] = {}
    order: list[tuple[str, ...]] = []
    for term in terms:
        factors = tuple(term["factors"])
        key = _cyclic_canonical(factors)
        if key not in bucket:
            bucket[key] = [list(factors), Fraction(0)]
            order.append(key)
        bucket[key][1] += Fraction(term["coefficient"])

    out: list[dict[str, Any]] = []
    for key in order:
        rep_factors, coeff = bucket[key]
        if coeff != 0:
            out.append({"factors": rep_factors, "coefficient": coeff})
    return out
