"""Linear R-charge repair (Phase 2c1 MVP).

Standalone JSON-in / JSON-out layer that solves the linear feasibility
problem `R(W) = 2 ∧ Σ SU(N)² × U(1)_R = 0` on a pure-quiver theory and
returns the L2-nearest feasible R-assignment to the input trial R.

Independent of both the mutation engine and the verifier: no imports
from `mutation_engine.py` (engine does not call this) and no imports
from `evaluate_claim` / verifier modules (this does not call the
verifier). Mirrors the architectural posture of `mutation_engine.py`.

See `docs/phase2c1_r_repair.md` for the full spec, locked scope, and
the locked-fixture behavior table.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any, Mapping


__all__ = [
    "repair_r_charges",
    "RRepairError",
]


class RRepairError(ValueError):
    """Raised for inputs outside the Phase 2c1 MVP scope.

    Mirrors `MutationEngineError` / `PureQuiverJSONError`: pattern-match
    on the message rather than catching generic ValueErrors. Note that
    *infeasibility* of the linear system is NOT an RRepairError — it is
    reported via `status: "infeasible"` in the return dict so callers
    can branch without try/except.
    """


def repair_r_charges(
    theory_json: Mapping[str, Any],
    *,
    tie_mode: str = "field",
    representative: str = "l2_nearest_trial",
    flavor_ranks: "list[int] | None" = None,
) -> dict[str, Any]:
    """Repair R-charges by L2-projecting trial R onto the feasible affine space.

    See `docs/phase2c1_r_repair.md` §1 for the return schema and §2 for
    the linear-system construction.
    """

    if tie_mode != "field":
        raise RRepairError(
            f"tie_mode {tie_mode!r} not supported by Phase 2c1 MVP "
            "(only 'field' is implemented)"
        )
    if representative != "l2_nearest_trial":
        raise RRepairError(
            f"representative {representative!r} not supported by Phase 2c1 MVP "
            "(only 'l2_nearest_trial' is implemented)"
        )

    singlets = list(theory_json.get("singlets", []))
    field_labels = [a["label"] for a in theory_json["arrows"]] + [
        s["label"] for s in singlets
    ]
    n = len(field_labels)
    if n == 0:
        raise RRepairError("theory has no Fields; nothing to repair")

    trial_r = [Fraction(a["r_charge"]) for a in theory_json["arrows"]] + [
        Fraction(s["r_charge"]) for s in singlets
    ]

    A, b = _build_constraint_system(theory_json, field_labels, flavor_ranks)

    trial_feasible = _check_trial_feasible(A, b, trial_r)

    rref_aug, pivot_cols, infeasible_row = _rref_augmented(A, b, n)
    if infeasible_row is not None:
        return {
            "status": "infeasible",
            "dimension": None,
            "trial_feasible": False,
            "representative": None,
            "feasible_space": None,
            "changed_fields": [],
            "failure_reason": (
                "linear system A r = b is inconsistent "
                f"(zero row with nonzero RHS detected at reduced row index "
                f"{infeasible_row})"
            ),
        }

    rank = len(pivot_cols)
    dimension = n - rank

    particular_rref, kernel_basis = _kernel_and_particular(
        rref_aug, pivot_cols, n
    )

    repaired_r = _l2_project(trial_r, particular_rref, kernel_basis, n)

    status = "unique" if dimension == 0 else "underdetermined"

    changed_fields = _compute_changed_fields(field_labels, trial_r, repaired_r)

    representative_json = _build_representative_json(
        theory_json,
        field_labels,
        repaired_r,
        is_noop=not changed_fields,
    )

    feasible_space = {
        "particular_solution": {
            label: str(repaired_r[i]) for i, label in enumerate(field_labels)
        },
        "homogeneous_basis": [
            {label: str(ker[i]) for i, label in enumerate(field_labels)}
            for ker in kernel_basis
        ],
    }

    return {
        "status": status,
        "dimension": dimension,
        "trial_feasible": trial_feasible,
        "representative": representative_json,
        "feasible_space": feasible_space,
        "changed_fields": changed_fields,
        "failure_reason": None,
    }


# ----------------------------------------------------------------------
# Constraint-system construction.
# ----------------------------------------------------------------------


def _build_constraint_system(
    theory_json: Mapping[str, Any],
    field_labels: list[str],
    flavor_ranks: "list[int] | None" = None,
) -> tuple[list[list[Fraction]], list[Fraction]]:
    """Build A, b for the linear system A r = b.

    Rows: one per W term (R-sum = 2), then one per GAUGE node
    (SU(N_v)² × U(1)_R = 0). Columns: one per Field label, in the
    order given by `field_labels`.

    `flavor_ranks` (optional) are SU(N) GLOBAL flavor nodes, indexed after
    the gauge nodes. They get NO anomaly row (a flavor-R 't Hooft anomaly
    is allowed, not a constraint), but they DO enter the gauge-node anomaly
    coefficients as the spectator dimension of a flavored field (so a quark
    Q_{gauge,flavor} contributes T(fund) × N_flavor). With no flavor_ranks
    this is byte-identical to the pure-quiver system.
    """

    n = len(field_labels)
    col_idx = {label: i for i, label in enumerate(field_labels)}
    gauge_ranks = [int(r) for r in theory_json["ranks"]]
    n_gauge = len(gauge_ranks)
    ranks = gauge_ranks + [int(r) for r in (flavor_ranks or [])]
    arrows = list(theory_json["arrows"])

    A: list[list[Fraction]] = []
    b: list[Fraction] = []

    # W constraints.
    for term in theory_json["superpotential"]:
        row = [Fraction(0)] * n
        for f in term["factors"]:
            if f not in col_idx:
                raise RRepairError(
                    f"W term references unknown Field {f!r}; "
                    f"known labels: {field_labels!r}"
                )
            row[col_idx[f]] += Fraction(1)
        A.append(row)
        b.append(Fraction(2))

    # Anomaly constraints, one per GAUGE node only (flavor nodes get none).
    for v in range(n_gauge):
        N_v = ranks[v]
        row = [Fraction(0)] * n
        sum_a = Fraction(0)
        for arrow in arrows:
            s = int(arrow["source"])
            t = int(arrow["target"])
            label = arrow["label"]
            if s == v and t == v:
                # Adjoint at v: T(adj) = N_v, spectator dim = 1.
                a_vf = Fraction(N_v)
            elif s == v:
                # Antifundamental at v: T = 1/2, spectator = N_t.
                a_vf = Fraction(1, 2) * Fraction(ranks[t])
            elif t == v:
                # Fundamental at v: T = 1/2, spectator = N_s.
                a_vf = Fraction(1, 2) * Fraction(ranks[s])
            else:
                continue
            row[col_idx[label]] += a_vf
            sum_a += a_vf
        A.append(row)
        # Σ a · R = Σ a − N_v  (gaugino T(adj) = N_v moves to RHS with sign flip).
        b.append(sum_a - Fraction(N_v))

    return A, b


def _check_trial_feasible(
    A: list[list[Fraction]],
    b: list[Fraction],
    trial: list[Fraction],
) -> bool:
    """Return True iff `trial` satisfies every equation exactly."""

    for row, rhs in zip(A, b):
        value = sum((c * r for c, r in zip(row, trial)), Fraction(0))
        if value != rhs:
            return False
    return True


# ----------------------------------------------------------------------
# Linear-algebra helpers.
# ----------------------------------------------------------------------


def _rref_augmented(
    A: list[list[Fraction]],
    b: list[Fraction],
    num_vars: int,
) -> tuple[list[list[Fraction]], list[int], int | None]:
    """RREF on the augmented matrix [A | b].

    Returns `(reduced_rows, pivot_columns, infeasible_row)`.

    `reduced_rows` is the full row-reduced augmented matrix (one row per
    original equation, in possibly permuted order); each row has
    `num_vars + 1` Fraction entries. Trailing zero rows are KEPT so the
    caller can detect infeasibility from a zero left-side with nonzero
    RHS.

    `pivot_columns` lists pivot columns in column order, aligned with
    the *first* `len(pivot_columns)` rows of `reduced_rows`.

    `infeasible_row` is the index (into `reduced_rows`) of the first
    zero-row-with-nonzero-RHS, or None if the system is consistent.
    """

    rows = [list(row) + [b[i]] for i, row in enumerate(A)]
    pivot_columns: list[int] = []
    current_row = 0
    n_rows = len(rows)

    for col in range(num_vars):
        # Find a pivot at or below current_row in column col.
        pivot = None
        for r in range(current_row, n_rows):
            if rows[r][col] != 0:
                pivot = r
                break
        if pivot is None:
            continue
        if pivot != current_row:
            rows[current_row], rows[pivot] = rows[pivot], rows[current_row]
        pivot_coeff = rows[current_row][col]
        rows[current_row] = [v / pivot_coeff for v in rows[current_row]]
        for r in range(n_rows):
            if r == current_row:
                continue
            factor = rows[r][col]
            if factor == 0:
                continue
            rows[r] = [
                a - factor * b_
                for a, b_ in zip(rows[r], rows[current_row])
            ]
        pivot_columns.append(col)
        current_row += 1

    # Infeasibility scan: any row whose left side is all zero but RHS is nonzero.
    infeasible_row: int | None = None
    for r in range(n_rows):
        if all(rows[r][c] == 0 for c in range(num_vars)) and rows[r][num_vars] != 0:
            infeasible_row = r
            break

    return rows, pivot_columns, infeasible_row


def _kernel_and_particular(
    rref_aug: list[list[Fraction]],
    pivot_columns: list[int],
    num_vars: int,
) -> tuple[list[Fraction], list[list[Fraction]]]:
    """Extract a particular solution and a kernel basis from the RREF.

    Convention: free variables (non-pivot columns) take 0 in the
    particular solution and unit vectors as kernel-basis seeds. Pivot
    columns are then read off the RREF.
    """

    pivot_set = set(pivot_columns)
    free_columns = [j for j in range(num_vars) if j not in pivot_set]

    # Particular solution: free vars = 0, pivot vars = RHS of their row.
    particular = [Fraction(0)] * num_vars
    for i, pc in enumerate(pivot_columns):
        particular[pc] = rref_aug[i][num_vars]

    # Kernel basis: one vector per free column. Free col set to 1, other
    # free cols 0, pivot cols read as -coefficient_of_free_col_in_that_row.
    kernel_basis: list[list[Fraction]] = []
    for j in free_columns:
        ker = [Fraction(0)] * num_vars
        ker[j] = Fraction(1)
        for i, pc in enumerate(pivot_columns):
            ker[pc] = -rref_aug[i][j]
        kernel_basis.append(ker)

    return particular, kernel_basis


def _l2_project(
    trial: list[Fraction],
    particular: list[Fraction],
    kernel_basis: list[list[Fraction]],
    num_vars: int,
) -> list[Fraction]:
    """L2-project `trial` onto the affine space `particular + span(kernel_basis)`.

    Returns the projection point (exact Fraction). When `kernel_basis`
    is empty, the affine space is the single point `particular`.
    """

    if not kernel_basis:
        return list(particular)

    dim = len(kernel_basis)

    # delta = trial - particular, expressed in R^{num_vars}.
    delta = [trial[i] - particular[i] for i in range(num_vars)]

    # Build Gram matrix G_{ij} = <k_i, k_j> and RHS h_i = <k_i, delta>.
    gram = [[Fraction(0)] * dim for _ in range(dim)]
    rhs = [Fraction(0)] * dim
    for i in range(dim):
        for j in range(dim):
            gram[i][j] = sum(
                (kernel_basis[i][k] * kernel_basis[j][k] for k in range(num_vars)),
                Fraction(0),
            )
        rhs[i] = sum(
            (kernel_basis[i][k] * delta[k] for k in range(num_vars)),
            Fraction(0),
        )

    # Solve gram · c = rhs via Gauss-Jordan on the augmented matrix.
    coefficients = _solve_square(gram, rhs)

    # repaired = particular + Σ c_i · k_i.
    repaired = list(particular)
    for i, ker in enumerate(kernel_basis):
        c_i = coefficients[i]
        if c_i == 0:
            continue
        for k in range(num_vars):
            repaired[k] += c_i * ker[k]
    return repaired


def _solve_square(
    matrix: list[list[Fraction]],
    rhs: list[Fraction],
) -> list[Fraction]:
    """Solve `matrix · x = rhs` for a square invertible Fraction matrix.

    Used only for the kernel-basis Gram system, which is PD by
    construction (kernel basis is linearly independent), so we expect a
    unique exact-rational solution.
    """

    n = len(matrix)
    aug = [list(matrix[i]) + [rhs[i]] for i in range(n)]
    for col in range(n):
        pivot = None
        for r in range(col, n):
            if aug[r][col] != 0:
                pivot = r
                break
        if pivot is None:
            raise RRepairError(
                "kernel Gram matrix is singular; this should not happen for a "
                "linearly-independent kernel basis (R-repair internal error)"
            )
        if pivot != col:
            aug[col], aug[pivot] = aug[pivot], aug[col]
        pivot_coeff = aug[col][col]
        aug[col] = [v / pivot_coeff for v in aug[col]]
        for r in range(n):
            if r == col:
                continue
            factor = aug[r][col]
            if factor == 0:
                continue
            aug[r] = [
                a - factor * b_
                for a, b_ in zip(aug[r], aug[col])
            ]
    return [aug[i][n] for i in range(n)]


# ----------------------------------------------------------------------
# Output formatting.
# ----------------------------------------------------------------------


def _compute_changed_fields(
    field_labels: list[str],
    trial: list[Fraction],
    repaired: list[Fraction],
) -> list[dict[str, str]]:
    """Per-field diff entries in `{label, from, to}` form."""

    changes: list[dict[str, str]] = []
    for i, label in enumerate(field_labels):
        if trial[i] != repaired[i]:
            changes.append(
                {
                    "label": label,
                    "from": str(trial[i]),
                    "to": str(repaired[i]),
                }
            )
    return changes


def _build_representative_json(
    theory_json: Mapping[str, Any],
    field_labels: list[str],
    repaired: list[Fraction],
    *,
    is_noop: bool,
) -> dict[str, Any]:
    """Reconstruct the theory JSON with the repaired R-charges in place.

    When `is_noop` is True (no field changed value), the original name is
    preserved so that repair-on-already-feasible JSON is byte-for-byte
    idempotent. When `is_noop` is False, the name gets a `(R-repaired)`
    suffix so downstream traces / LLM logs can distinguish the input
    theory from the repaired one.
    """

    r_by_label = {label: repaired[i] for i, label in enumerate(field_labels)}
    new_arrows = [
        {
            "label": a["label"],
            "source": int(a["source"]),
            "target": int(a["target"]),
            "r_charge": str(r_by_label[a["label"]]),
        }
        for a in theory_json["arrows"]
    ]
    name = (
        theory_json["name"]
        if is_noop
        else f"{theory_json['name']} (R-repaired)"
    )
    result: dict[str, Any] = {
        "name": name,
        "node_labels": list(theory_json["node_labels"]),
        "ranks": [int(r) for r in theory_json["ranks"]],
        "u1_globals": list(theory_json.get("u1_globals", [])),
        "arrows": new_arrows,
        "superpotential": [
            {"factors": list(t["factors"]), "coefficient": str(t["coefficient"])}
            for t in theory_json["superpotential"]
        ],
    }
    singlets = theory_json.get("singlets", [])
    if singlets:
        result["singlets"] = [
            {"label": s["label"], "r_charge": str(r_by_label[s["label"]])}
            for s in singlets
        ]
    return result
