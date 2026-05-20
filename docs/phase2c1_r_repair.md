# Phase 2c1 Linear R-Charge Repair (MVP)

**Status:** spec + design lock for Phase 2c1. R-repair is a standalone
JSON-in / JSON-out layer that sits between the mutation engine output and
the verifier. It is independent of both: the engine does not call it, and
it does not call `evaluate_claim`. Callers (verifier pre-processing, LLM
harness, ablation tests) decide whether to apply it.

**Purpose:** close the F_0 phase II boundary regression. The trial UV R
that `mutate_bare` produces via `R(q̃) = 1 − R(Q)` and `R(M) = R(Q) +
R(Q̃)` is not the SCFT R in general; for F_0 II it fails SU(N)² × U(1)_R
on non-dualized nodes. Linear R-repair solves the linear feasibility
problem `R(W) = 2 ∧ Σ mixed-anomaly = 0` and returns the L2-nearest
feasible R-assignment to the input trial R.

**Architecture: four-layer ablation matrix**

```
bare mutation
bare + integration
bare + integration + R-repair        ← Phase 2c1 adds this layer
bare + integration + R-repair + bounded chiral-ring
```

R-repair is exposed as a standalone tool so callers can choose whether to
apply it. The mutation engine itself does **not** call R-repair — that
keeps the engine's "deterministic structural JSON operation" semantics
clean. The separation also enables R-repair on hand-built theories that
did not come from the mutation engine.

**Explicitly NOT in scope (Phase 2c1 MVP):**

- a-maximization (picking the SCFT R within the feasible affine space).
- Unitarity bounds / positivity constraints on R-charges.
- Changing the W structure (factor multisets) or W coefficients.
- Changing the gauge ranks, edge multiplicities, or any other structural
  data of the theory.
- Tying R-charges across distinct Fields ("edge_family" tying); the MVP
  only supports `tie_mode="field"` (one R variable per Field).
- Representatives other than the L2-nearest projection of the trial R
  (e.g. lex-min, sum-max, a-maximized picker). The schema is forward
  compatible — the `representative` field is kept separate from
  `feasible_space.particular_solution` precisely so future pickers can
  swap in without breaking callers.

---

## 1. API and return schema

```python
from dualitycert.qft.r_repair import repair_r_charges, RRepairError

repair_r_charges(
    theory_json,
    *,
    tie_mode="field",                       # MVP only; future: "edge_family"
    representative="l2_nearest_trial",      # MVP only; future: "lex_min", ...
) -> dict
```

Return schema:

```python
{
    "status": "unique" | "underdetermined" | "infeasible",
    "dimension": int | None,           # None when infeasible
    "trial_feasible": bool,            # explicit, not inferred from changed_fields
    "representative": pure_quiver_json | None,
    "feasible_space": {
        "particular_solution": {"X02[0]": "1/3", ...},
        "homogeneous_basis": [
            {"X02[0]": "1", "X02[1]": "-1", ...},
            ...
        ]
    } | None,
    "changed_fields": [
        {"label": "X02[0]", "from": "0", "to": "1/3"},
        ...
    ],
    "failure_reason": str | None       # populated only when status == "infeasible"
}
```

**`representative` vs `feasible_space.particular_solution`** (verbatim
spec note):

> In the Phase 2c1 MVP, `representative` and
> `feasible_space.particular_solution` are the same point: the
> L2-nearest feasible R-assignment to the input trial R.
>
> They are kept as separate fields because they serve different
> consumers: `representative` is the concrete repaired theory that
> callers should feed to the verifier; `feasible_space.particular_solution`
> is the affine-space anchor used to reconstruct all feasible
> R-assignments as
>
> `R = particular_solution + Σ c_i · basis_i`.
>
> Future pickers may choose a different `representative` (e.g. an
> a-maximized point) while preserving the same affine-space anchor.

**`changed_fields` schema lock.** A list of objects of the form
`{label, from, to}` (not `{label: [from, to]}`). Extensibility for future
`delta` / `reason` / `constraint_source` fields is preserved by keeping
the per-entry shape an object rather than a tuple.

**`trial_feasible` semantics.** True iff the input trial R already
satisfies every constraint (W-sum and per-node mixed-anomaly). When
`trial_feasible` is True, `representative` is the trial R itself and
`changed_fields == []`. The flag is explicit (not inferred from
`changed_fields`) so callers can distinguish "no change because trial was
already feasible" from "no change because the L2 projection happened to
fall on the trial" — the latter cannot occur with a strict L2 picker, but
future pickers may surface that ambiguity.

**`RRepairError`.** Raised for inputs outside the MVP scope:
`tie_mode != "field"`, `representative != "l2_nearest_trial"`, or an
internally inconsistent kernel-projection state (should not happen for
a linearly-independent kernel basis — raised as a defensive check).
Mirrors `MutationEngineError` / `PureQuiverJSONError` patterns
elsewhere in the codebase. Infeasibility of the linear system is **not**
an exception — it is `status: "infeasible"` in the returned dict, so
callers can branch on it without try/except.

R-repair otherwise trusts its input JSON (mirrors `mutation_engine.py`'s
posture — see §6). Missing keys / type errors in the input surface as
plain `KeyError` / `TypeError`. Callers that want schema validation
should run `pure_quiver_from_json` on the input first.

---

## 2. Linear system

**Variables.** One R per Field (`tie_mode="field"` for MVP). Each JSON
arrow is one Field; the variable vector `r ∈ Q^n` is indexed by
`theory_json["arrows"]` in input order.

**Constraints.**

- **W constraints.** One equation per W term: `Σ R(factors) = 2`. A
  factor appearing with multiplicity k contributes coefficient k to that
  variable in the row.

- **Anomaly constraints.** One equation per gauge node `v`: the
  SU(N_v)² × U(1)_R mixed anomaly cancels. Formula (matching
  `dualitycert/qft/anomalies.gauge_global_mixed_anomaly_cancellation`):

  ```
  Σ_{f: non-singlet at v}  T_v(f) · D_v(f) · (R_f - 1)  +  T(adj_v) = 0
  ```

  where `T_v(f)` is the Dynkin index of the rep at node v (1/2 for
  fundamental / antifundamental on a bifundamental, N_v for an adjoint),
  `D_v(f)` is the spectator dimension (= product of dims for other
  gauge factors; for a pure-quiver bifundamental on edge `(s, t)` with
  `s ≠ t` and `v ∈ {s, t}`, `D_v = N_other`), and `T(adj_v) = N_v` is
  the gaugino's contribution.

  In linear-system form (move the constants to the RHS):

  ```
  Σ_f T_v(f) · D_v(f) · R_f  =  Σ_f T_v(f) · D_v(f)  −  N_v
  ```

  **Important: all gauge nodes, not just dualized.** F_0 II's failure
  mode under trial R is exactly that the *non-dualized* node 1 has
  `Σ SU(N)² × U(1)_R = +3 ≠ 0`. Restricting the constraint to the
  dualized node would silently miss this.

- **Adjoint loops at a node `v`** contribute `T(adj) · 1 · (R_F - 1) =
  N_v · (R_F - 1)` to that node's row (Dynkin of adjoint is N_v;
  spectator dim is 1 since the adjoint is a singlet of every other
  factor). Phase 2c0's mutation engine rejects adjoint loops at the
  dualized node (Kutasov out of MVP scope), but R-repair has no reason
  to reject them — the linear system handles them uniformly.

**Solver.** Exact rational arithmetic via `fractions.Fraction`. Build
the `(m_W + n_nodes) × n_fields` constraint matrix `A` and RHS vector
`b`, then reduce the augmented matrix `[A | b]` to RREF. Pivot columns
give the "eliminated" variables; non-pivot columns give the kernel-free
variables.

- **Infeasibility detection.** If any all-zero row of `A` has a nonzero
  RHS entry after RREF, `A r = b` has no solution. Return
  `status: "infeasible"`.

- **Dimension.** `dimension = n_fields - rank(A)` when feasible. Equal
  to the dimension of the affine solution space (and the kernel of `A`).

- **Particular solution.** Set free variables to 0; pivot variables
  read off the RHS column. Call this `r_p^{rref}`.

- **Kernel basis.** For each free column `j`, set `r_j = 1` and other
  free vars to 0; pivot variables become `r_{pivot} = -A_{pivot, j}`
  (after RREF). Call these `k_1, ..., k_d`.

**L2 projection.** Given trial R `r_0` and the affine solution space
`{r_p^{rref} + Σ c_i k_i}`, the L2-nearest feasible point is found by
minimizing `‖r_0 − r_p^{rref} − K c‖²` over `c ∈ Q^d`, where `K` is the
`n × d` matrix whose columns are the basis vectors. The minimizer
satisfies the normal equations

```
K^T K · c  =  K^T (r_0 − r_p^{rref})
```

`K^T K` is `d × d` with Fraction entries; solve exactly via Gauss-Jordan
on the augmented `d × (d + 1)` matrix. Then

```
r*  =  r_p^{rref}  +  K c
```

is the L2-nearest feasible R. In MVP this `r*` is reported as both
`representative` (in the full theory JSON form) and
`feasible_space.particular_solution` (as a dict of field-label → string).

**Why this works with exact rationals.** `K^T K` is positive
semi-definite over Q. It is strictly positive definite iff the kernel
basis `k_1, ..., k_d` is linearly independent — which it is by
construction (one kernel vector per free column, and the unit-vector
positions on the free columns make the basis independent). So Gauss-
Jordan on `K^T K` terminates with a unique exact-Fraction solution. No
floating-point, no SVD, no pseudoinverse machinery.

---

## 3. Expected behavior on locked fixtures

These measurements were taken by codex (2026-05-20) on the pre-existing
engine fixtures. They MUST hold after implementation; tests pin every
row of the table.

| Fixture | fields | W terms | equations | rank | dim | trial_feasible | representative changes |
|---|---|---|---|---|---|---|---|
| dP_0 magnetic effective (`build_dp0_magnetic_effective(N=3)`) | 12 | 9 | 12 | 10 | 2 | True | `[]` (no-op) |
| F_0 II electric trial (`_electric_f0_phase_ii_trial(N=3)` from existing tests) | 12 | 8 | 12 | 9 | 3 | True | `[]` (no-op) |
| F_0 II engine output (mutate_bare + integrate_linear_fields at node 0 of above) | 20 | 16 | 20 | 17 | 3 | False | **8 fields** |
| Constructed infeasible toy | — | — | — | — | None | False | (representative = None) |
| Constructed 0-dim toy | — | — | — | — | 0 | depends | depends |

**F_0 II engine output's 8 changed fields** (the substantive content of
the Phase 2c1 win):

- `X02[0..3]` (reversed diagonal): R `0 → 1/3` (4 fields)
- `X10[0..1]` (reversed top out-arrows): R `1/2 → 1/6` (2 fields)
- `X30[0..1]` (reversed left out-arrows): R `1/2 → 1/6` (2 fields)
- Mesons `X21[0..5]` and `X23[0..5]` stay at R = 3/2 (the L2-minimum
  picks the meson side as fixed).

Each W term still has `R(W) = R(X10/X30) + R(X02) + R(X21/X23) = 1/6
+ 1/3 + 3/2 = 2 ✓`. The dimension is 3, which is physical (flavor /
baryonic U(1)s mixing into U(1)_R remain after fixing
W=2 ∧ mixed-anomaly=0); a-maximization would pick a unique point inside
this 3-dimensional affine space, but a-maximization is out of MVP scope.

**Constructed infeasible toy.** Two-node mass loop
`SU(2) × SU(2)` with one arrow each way (`X01[0]` and `X10[0]`) and
mass W = `X01[0] · X10[0]`. Two constraints contradict each other:
- W forces `R(X01) + R(X10) = 2`.
- Node-0 anomaly: `(1/2)·2·(R_X01 − 1) + (1/2)·2·(R_X10 − 1) + 2 = 0`
  collapses to `R(X01) + R(X10) = 0`.

`2 ≠ 0`, so the system is inconsistent and R-repair returns
`status: "infeasible"`. The exact fixture lives in
`tests/test_r_repair.py::test_infeasible_toy_reports_infeasible`.

**Constructed 0-dim toy.** Single SU(3) gauge node with one adjoint
chiral `Phi0[0]` and W = 0. The only constraint is the node-0 anomaly
`T(adj)·(R − 1) + T(adj) = 0`, i.e. `3·(R − 1) + 3 = 0 ⇒ R = 0`. Rank
1 = n_fields, so `dimension = 0` and the feasible R is unique. The
exact fixture lives in
`tests/test_r_repair.py::test_zero_dim_toy_single_adjoint_uniquely_determined`.

---

## 4. Acceptance gate

**Mutation-engine integration test** (`tests/test_mutation_engine.py`):

Add `test_f0_phase_ii_after_r_repair_certifies_on_anomalies` next to
(not replacing) the existing
`test_f0_phase_ii_mutation_topology_matches_but_trial_r_fails_mixed_anomaly`.
The boundary regression stays as a regression guard against backsliding
on Phase 2c0's behavior; the new test pins Phase 2c1's win:

```
mutate_bare + integrate_linear_fields + repair_r_charges  on F_0 II
   → evaluate_claim returns CERTIFIED for
       - magnetic_gauge_global_mixed_anomaly
       - bounded_chiral_ring_consistency
       - central_charge_matching_from_encoded_R_symmetry
```

Codex pre-verified this in a one-off script (2026-05-20). The acceptance
gate is therefore not speculative — implementation must reproduce it.

---

## 5. Implementation order

1. **`docs/phase2c1_r_repair.md`** — this file. Written first so the
   implementation has a self-check target.
2. **`dualitycert/qft/r_repair.py`** — `repair_r_charges` plus helpers:
   `_build_constraint_system`, `_rref_augmented`, `_kernel_and_particular`,
   `_l2_project`, `_compute_changed_fields`. No imports from verifier
   modules (independent layer, mirroring `mutation_engine.py`).
3. **`tests/test_r_repair.py`** — five fixture tests pinning the table
   in §3 (dP_0 magnetic, F_0 II electric, F_0 II engine output,
   infeasible toy, 0-dim toy).
4. **Acceptance gate in `tests/test_mutation_engine.py`** — add the new
   test described in §4.
5. Local commit (embargo still in effect per
   `memory/project_confidentiality.md`).

---

## 6. Out of MVP scope (Phase 2c1+)

- **a-maximization.** Picking the unique SCFT R inside the
  underdetermined affine space when central-charge matching or
  unitarity bounds require it. The R-repair representative picker is
  pluggable; a future `representative="a_max"` mode plugs into the
  same return schema.
- **Unitarity / positivity.** Adding `R(F) > some lower bound` (e.g.
  free-chiral bound `R ≥ 2/3`) as additional constraints. These are
  inequalities, not equalities; they need an LP solver, not Gaussian
  elimination. Adding them on top is a future layer; the spec keeps
  the linear feasibility layer and the inequality layer separable.
- **`tie_mode="edge_family"`.** Tying R across distinct Field copies on
  the same edge (e.g. all mesons on `(2, 1)` share one R). This shrinks
  the variable space and can collapse the underdetermined dimension; it
  also enforces a symmetry that is physical (gauge-invariant spectator
  permutation) but not automatic from the linear system. Deferred.
- **Other representative pickers.** `lex_min`, `sum_max`, central-
  charge-extremal, etc. All composable with the existing affine-space
  anchor + kernel basis output.
- **Symmetry-map JSON.** Phase 2c1 does not produce a map from
  electric R-charges to magnetic R-charges. The LLM harness (Phase 2c)
  will own that contract.
- **Robustness to malformed superpotential / arrow JSON.** R-repair
  trusts its input (mirrors `mutation_engine.py`'s posture). Callers
  should run `pure_quiver_from_json` on the input first if they want
  schema validation.
