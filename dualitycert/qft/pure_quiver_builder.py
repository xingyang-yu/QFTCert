"""Builder for pure-quiver theories with SU(N) gauge nodes.

Conventions (must match design doc §3.2):
  - Node indices are 0-based. Arrow (i, j) means source node i, target node j.
  - Bifundamental (i != j): antifundamental at source i, fundamental at target j.
    Rationale: "arrow from antifundamental node to fundamental node" is the
    Jacobi-algebra / derived-category convention used throughout Phase 2a's
    cyclic-derivative math (∂_X W ∈ paths(target(X) → source(X))).
  - Adjoint (i == i): adjoint at node i.
  - arrows[(i,j)] is a list of R-charges, one entry per arrow copy.
  - All output Fields have multiplicity=1; the [k] index is embedded in field name.

Field naming scheme:
  - Bifundamental from node i to node j, copy k: "X{i}{j}[{k}]" (or "X_{i}_{j}[{k}]"
    for i or j >= 10).
  - Adjoint at node i, copy k: "Phi{i}[{k}]" (or "Phi_{i}[{k}]" for i >= 10).
"""

from __future__ import annotations

from fractions import Fraction
from itertools import permutations

from dualitycert.core.objects import (
    Field,
    GlobalSymmetry,
    SuperpotentialTerm,
    Theory,
)
from dualitycert.groups.su import adjoint, antifundamental, fundamental, su


def build_pure_quiver(
    *,
    ranks: tuple[int, ...],
    arrows: dict[tuple[int, int], list[Fraction]],
    superpotential: tuple[SuperpotentialTerm, ...] = (),
    node_labels: tuple[str, ...] | None = None,
    u1_globals: tuple[GlobalSymmetry, ...] = (),
) -> Theory:
    """Build a pure-quiver Theory from a rank vector and arrow dictionary.

    Args:
        ranks: SU(N) rank for each gauge node (0-indexed).
        arrows: maps (source_idx, target_idx) to list of R-charges per copy.
            len(arrows[(i,j)]) is the number of arrow copies on that directed edge.
        superpotential: superpotential monomials whose factor names must match
            the field names produced by this builder (use arrow_names() to
            look up the generated names).
        node_labels: display labels for gauge nodes; defaults to "SU({N})_{i}".
        u1_globals: global U(1) symmetries to attach (e.g. (u1_r(),) for ABJ check).

    Returns:
        Theory with one SU(N) gauge node per rank and one chiral-multiplet Field
        per arrow copy. All Fields have multiplicity=1.
    """
    n_nodes = len(ranks)
    if node_labels is None:
        node_labels = tuple(f"SU({ranks[i]})_{i}" for i in range(n_nodes))
    if len(node_labels) != n_nodes:
        raise ValueError(
            f"node_labels length {len(node_labels)} != ranks length {n_nodes}"
        )
    for i, j in arrows:
        if not (0 <= i < n_nodes and 0 <= j < n_nodes):
            raise ValueError(
                f"Arrow ({i}, {j}) out of range for {n_nodes}-node quiver"
            )

    gauge_nodes = tuple(su(ranks[i], label=node_labels[i]) for i in range(n_nodes))

    fields: list[Field] = []
    for (i, j), r_charges in sorted(arrows.items()):
        base = _arrow_base_name(i, j)
        for k, r_charge in enumerate(r_charges):
            name = f"{base}[{k}]"
            if i == j:
                gauge_reps = {node_labels[i]: adjoint()}
            else:
                gauge_reps = {
                    node_labels[i]: antifundamental(),
                    node_labels[j]: fundamental(),
                }
            fields.append(
                Field(
                    name=name,
                    field_type="chiral multiplet",
                    gauge_reps=gauge_reps,
                    r_charge=r_charge,
                    multiplicity=1,
                )
            )

    return Theory(
        name=f"{n_nodes}-node pure quiver",
        gauge_nodes=gauge_nodes,
        fields=tuple(fields),
        superpotential_terms=superpotential,
        global_symmetries=u1_globals,
    )


def arrow_names(i: int, j: int, multiplicity: int) -> tuple[str, ...]:
    """Return the field names assigned to the (i, j) arrow copies by build_pure_quiver."""
    base = _arrow_base_name(i, j)
    return tuple(f"{base}[{k}]" for k in range(multiplicity))


def dp0_superpotential(
    names_01: tuple[str, str, str],
    names_12: tuple[str, str, str],
    names_20: tuple[str, str, str],
) -> tuple[SuperpotentialTerm, ...]:
    """Generate W = ε_{abc} A[a] B[b] C[c] for the dP_0 toric phase.

    Expands the antisymmetric tensor over {0,1,2} to 6 monomials with
    coefficients equal to the permutation signature (+1 or -1).

    Args:
        names_01: field names for the 3 arrow copies on directed edge 0→1.
        names_12: field names for the 3 arrow copies on directed edge 1→2.
        names_20: field names for the 3 arrow copies on directed edge 2→0.

    Returns:
        6 SuperpotentialTerms, each a cubic monomial with coefficient ±1.
    """
    terms: list[SuperpotentialTerm] = []
    for perm in permutations(range(3)):
        a, b, c = perm
        sign = _permutation_sign(perm)
        terms.append(
            SuperpotentialTerm(
                factors=(
                    (names_01[a], 1),
                    (names_12[b], 1),
                    (names_20[c], 1),
                ),
                coefficient=Fraction(sign),
            )
        )
    return tuple(terms)


def _arrow_base_name(i: int, j: int) -> str:
    if i == j:
        return f"Phi{i}" if i < 10 else f"Phi_{i}"
    if i < 10 and j < 10:
        return f"X{i}{j}"
    return f"X_{i}_{j}"


def _permutation_sign(perm: tuple[int, ...]) -> int:
    seen = [False] * len(perm)
    sign = 1
    for start in range(len(perm)):
        if seen[start]:
            continue
        cycle_len = 0
        i = start
        while not seen[i]:
            seen[i] = True
            i = perm[i]
            cycle_len += 1
        if cycle_len % 2 == 0:
            sign *= -1
    return sign
