# Phase 2c0 Single-Node Seiberg Mutation Engine (MVP)

**Status:** spec + design lock for Phase 2c0. The engine is intentionally
independent of the verifier: JSON in / JSON out, no internal call to
`evaluate_claim`. The verifier consumes engine output through the
standard `pure_quiver_from_json` → `Theory` → `DualityClaim` pipeline.

**MVP scope (locked with user):** two stand-alone functions, separately
testable.

1. `mutate_bare(theory_json, *, node)` — pure mechanical Seiberg
   mutation at one gauge node. Reverses arrows incident to the node,
   adds all bypass mesons (no symmetrization), writes the pre-integration
   superpotential (inherited mass term + Seiberg coupling). No F-equation
   reasoning. Output may **legitimately FAIL** the bounded chiral-ring
   check against the original electric (pre-integration carries extra
   bifundamentals on the not-incident edge plus the full meson matrix).
2. `integrate_linear_fields(theory_json)` — minimum-scope F-equation
   substitution: identify fields appearing **linearly** in `W` (every
   monomial holds the field as a single factor) whose `∂_F W` is a
   homogeneous linear polynomial in *other* field components; solve the
   linear system, eliminate the auxiliary field plus the constrained
   components, drop the now-vanished `W` terms. **Out of scope for MVP:**
   general F-term Gröbner, multi-degree mass matrices, mixed
   bilinear/cubic mass patterns. Anything beyond a single linear-field
   pass is deferred.

The MVP oracle is:

```
integrate_linear_fields(mutate_bare(dp0_toric_json, node=0))
```

must structurally match `build_dp0_magnetic_effective(N=3)` (modulo
canonical machine labels) and certify
`bounded_chiral_ring_consistency` at `max_length=3, r_graded=True`
against the electric dP_0 fixture. A Type-4 W-drop on the engine output
must still FAIL.

---

## 1. JSON schema (`pure_quiver_json.py`)

A pure-quiver theory is encoded as a plain dict (JSON-serializable):

```json
{
  "name": "dP_0 toric (electric)",
  "node_labels": ["SU(3)_0", "SU(3)_1", "SU(3)_2"],
  "ranks": [3, 3, 3],
  "u1_globals": ["U(1)_R"],
  "arrows": [
    {"label": "X01[0]", "source": 0, "target": 1, "r_charge": "2/3"},
    {"label": "X01[1]", "source": 0, "target": 1, "r_charge": "2/3"},
    ...
  ],
  "superpotential": [
    {"factors": ["X01[0]", "X12[1]", "X20[2]"], "coefficient": "1"},
    {"factors": ["X01[0]", "X12[2]", "X20[1]"], "coefficient": "-1"},
    ...
  ]
}
```

Conventions:
- **arrows** is a list of one entry per arrow copy (the multiplicity-1
  builder convention). `label` is the machine label (must equal the
  resulting `Field.name`). `source` / `target` are 0-indexed positions
  into `node_labels`. `r_charge` is a string parsed as `Fraction`.
- **superpotential.factors** is a flattened list of machine labels (one
  entry per factor; powers are repeated entries, mirroring
  `SuperpotentialTerm.field_names`).
- **u1_globals** is a list of U(1) symmetry labels. MVP only supports
  `["U(1)_R"]` (forwarded to `u1_r()`); other entries raise
  `PureQuiverJSONError`. Wider global-symmetry schema is out of MVP scope.
- **node_labels** length must equal `len(ranks)`.

`pure_quiver_to_json(theory)` reads a `Theory` produced by
`build_pure_quiver` (or any compatible Theory whose Fields are all
multiplicity-1 bifundamentals/adjoints with `u1_r` attached) and emits
this dict.

`pure_quiver_from_json(data)` reverses it via `build_pure_quiver` with
the same conventions as `build_dp0_magnetic_effective` (per-edge label
naming `X{i}{j}[k]`). The JSON's `label` field must match what
`build_pure_quiver` would produce; the function asserts the equality so
hand-written JSON cannot diverge from the builder's naming. (This keeps
the engine's output machine labels consistent with the rest of the
codebase — important because the verifier reads JSON via this path.)

Round-trip on `build_dp0_magnetic_effective(N=3)` and the electric dP_0
fixture must be the identity (up to deterministic field ordering).

## 2. `mutate_bare(theory_json, *, node)`

**Input:** a pure-quiver JSON, plus `node` (the 0-indexed gauge node to
dualize).

**Algorithm:**

1. **Validate** that there is at least one in-arrow (`target == node`)
   and one out-arrow (`source == node`). Reject adjoint loops at the
   target node for MVP (`MutationEngineError`) — Kutasov-style mutations
   on adjoints are out of MVP scope. If either in-degree or out-degree
   is zero (degenerate / isolated node), raise `MutationEngineError`
   reporting both degrees so the caller can route this case explicitly
   instead of silently consuming a degenerate output.

2. **Flavor count and new rank.** Let
   - `N_in  = sum(ranks[a.source] for a in in_arrows)`
   - `N_out = sum(ranks[a.target] for a in out_arrows)`
   
   Anomaly-free pure-quivers satisfy `N_in == N_out` (this is the SU(N_v)^3
   cubic anomaly cancellation). MVP requires equality; raise if not.
   Let `N_f = N_in`, `N_c = ranks[node]`, `N_m = N_f - N_c`.
   For dP_0 at node 0: `N_in = N_out = 9`, `N_c = 3`, `N_m = 6` ✓.

3. **Build new ranks** by replacing `ranks[node]` with `N_m`. Replace the
   `node_labels[node]` with the canonical `f"SU({N_m})_{node}"`.

4. **Reverse incident arrows.** For each in-arrow `(u → node)` of
   R-charge `r`, replace with `(node → u)` of R-charge `1 - r` (this is
   the Seiberg dualization of the quark R-charge: original `R(Q) =
   r_in`, dual `R(q̃) = 1 - r_in`). For each out-arrow `(node → w)` of
   R-charge `r`, replace with `(w → node)` of R-charge `1 - r`. For dP_0
   electric with `r = 2/3`, reversed `r = 1/3` ✓.

5. **Add bypass mesons.** For each pair `(in_arrow Q : u → node,
   out_arrow Q' : node → w)`, add a meson field on edge `(u, w)` with
   R-charge `r(Q) + r(Q')`. Pair count: `len(in_arrows) ×
   len(out_arrows)`. For dP_0: 3 × 3 = 9 mesons.

6. **Re-label** all arrows after the above per the standard naming
   `X{i}{j}[k]` (or `Phi{i}[k]` for adjoints — not produced by MVP).
   Within each `(i, j)` edge, arrows are ordered by a stable rule:
   reversed quarks first preserve their original copy index, mesons are
   indexed by `(in_copy * len(out_arrows) + out_copy)` so the meson
   indexing is deterministic.

7. **Rewrite W.** Each original W monomial is a closed walk. For each
   monomial:
   - Locate cyclic rotations of the factors that bring the (in-arrow,
     out-arrow) pair through `node` to *adjacent* positions. There is
     exactly one such rotation per occurrence of `node` in the walk's
     node sequence (MVP requires `node` to occur at most once per
     monomial; W terms that visit `node` twice are rejected with
     `MutationEngineError`).
   - Replace the adjacent `(X_{u,node}, X_{node,w})` pair with the
     corresponding meson `M[in_copy, out_copy]` (machine label per
     step 6) on edge `(u, w)`.
   - Adopt the new factor order so that the (still) closed walk uses
     the meson plus the surviving factors. Coefficient carries through.

8. **Add Seiberg coupling.** For each meson `M_{α,β}` on edge `(u, w)`:
   - Find the reversed-quark fields: `q̃_α` on edge `(node, u)` and
     `q_β` on edge `(w, node)`.
   - Add a W term `(q_β, q̃_α, M_{α,β})` (factor order picked so the
     walk closes `w → node → u → w`) with coefficient `+1`.
   - Pair count: `N_in × N_out` (when `N_in_arrows × N_out_arrows = 9`,
     9 Seiberg terms for dP_0).

9. **No internal post-output validation.** The engine does not re-run
   closed-walk or anomaly checks on its own output. The schema is
   enforced when the JSON is rebuilt into a `Theory` via
   `pure_quiver_from_json` (label naming, edge endpoints) and the
   physics (cubic + mixed anomaly, W consistency, bounded chiral-ring)
   is left to the verifier downstream. The engine's only post-mutation
   guard is the cubic-anomaly balance check from step 2 — that one
   *is* hand-coded because it's required to compute `N_m`. Adding an
   internal mixed-anomaly cross-check is a Phase 2c1 hardening
   candidate, not a Phase 2c0 requirement.

**Output JSON shape** matches the input schema. For dP_0 at node 0:
- ranks `[6, 3, 3]`.
- 18 arrows: 3 q on (1, 0), 3 q̃ on (0, 2), 3 X12 unchanged on (1, 2),
  9 mesons on (2, 1).
- 6 + 9 = 15 W terms (6 mass-inherited from electric, 9 Seiberg).

This output is **expected to FAIL** the bounded chiral-ring check
against the electric dP_0 at length-1 R=2/3 block (electric has 9
copies of bifundamentals at R=2/3; bare-magnetic has only the 3 X12
copies — the 9-vs-3 mismatch is the smoking gun that integration is
needed). The Phase 2c0 test suite pins this failure mode explicitly so
the next layer can be unit-tested independently.

## 3. `integrate_linear_fields(theory_json)`

**Input:** a pure-quiver JSON.

**Algorithm (single pass; iterates until no progress):**

1. Identify each field `G` (machine label) such that every W term
   contains `G` at most once as a single factor (no power ≥ 2; no W
   term holds `G` twice). Call these the **linear fields**.

2. For each linear field `G`, partition W into `W = G · L_G + W_rest`
   where `L_G` is the residual sum (per monomial: `coefficient × product
   of remaining factors`). Each summand in `L_G` is a monomial in OTHER
   fields, of degree `n - 1` where `n` is the monomial's original
   degree. (In dP_0 pre-integration, `G = X_BC[b]`, `L_G = sum_{a,c}
   ε_{a,b,c} M_{(c,a)}` — degree-1 polynomial in M.)

3. **Require** that `L_G` is **degree-1** in the field-component vector
   space (every summand is `coefficient × one_field_component`, no
   products of fields). If any term in `L_G` has degree ≠ 1, skip this
   `G` (this MVP cannot solve nonlinear F-equations).

4. **Linear constraint extraction.** `∂_G W = L_G = 0` is a linear
   equation in the surviving fields. For each independent copy of `G`
   (e.g. `X_BC[0]`, `X_BC[1]`, `X_BC[2]`), we get one such equation.
   Stack them into a matrix `A · v = 0` where `v` is the vector of all
   field components appearing in any `L_G`.

5. **Solve** by Fraction Gaussian elimination (reuse `_gaussian_rank`
   pattern from `quiver_chiral_ring.py`; for the eliminated solution
   we run a full row-echelon reduction and read off the pivot columns).
   Each pivot variable is solved as a linear combination of free
   variables. Pivot variables are **eliminated** from the theory; free
   variables stay.

6. **Determine which field components survive.** A surviving field
   component is one whose label is a free variable AND whose only
   constraint is "it equals itself" (or it equals another free variable
   via substitution — in dP_0 we get pivots `M_{(α,β)}` for `α > β`
   equal `M_{(β,α)}` for `α < β`, so the antisymmetric components are
   eliminated and the symmetric components survive). MVP requires that
   every pivot column is expressible as a single free variable (i.e.
   the substitution is a simple identification / sign-flip), not a
   nontrivial linear combination. If a pivot column needs a sum of two
   or more free variables, raise `MutationEngineError("pivot needs
   nontrivial substitution")` — this case requires more careful
   chiral-ring algebra than the MVP commits to.

7. **Rewrite W.** Substitute every pivot variable with its
   free-variable representative in every remaining W term. Drop any W
   term that contains an `G` factor (linear field is being removed) —
   those terms collapse to zero in the chiral ring after F-equation
   substitution.

8. **Drop fields.** Remove `G` and all eliminated pivot field
   components from the arrows list.

9. **Re-label.** Within each surviving edge `(i, j)`, re-index arrows
   so the labels are `X{i}{j}[0]`, `X{i}{j}[1]`, ... in deterministic
   order (preserve relative ordering from before elimination, just
   re-pack the indices so there are no gaps). Update all references in
   W accordingly.

10. **Iterate.** Repeat steps 1–9 until no progress (no new linear
    field detected, or no eliminations possible).

For dP_0 pre-integration:
- Pass 1: linear field `G = X_BC[b]` for b = 0, 1, 2. Constraint:
  `ε_{a,b,c} M_{(c,a)} = 0`, i.e. (re-indexing α=c, β=a)
  `ε_{β,b,α} M_{(α,β)} = 0`.
- For b=0: `M_{(2,1)} - M_{(1,2)} = 0` → pivot `M_{(2,1)}`, free
  `M_{(1,2)}`.
- For b=1: `M_{(0,2)} - M_{(2,0)} = 0` → pivot `M_{(2,0)}`, free
  `M_{(0,2)}` (or vice versa; MVP picks the lexicographically later
  one as pivot so the surviving free variable matches the lex-min
  symmetric representative).
- For b=2: pivot `M_{(1,0)}`, free `M_{(0,1)}`.
- Substitute in 9 Seiberg terms (sym M + diagonal); drop 6 mass-W
  terms; drop 3 `X_BC[b]`; drop 3 antisymmetric `M_{(α,β)}`.
- Re-label the 6 surviving symmetric mesons as `X21[0..5]` in lex
  order of `(α, β)` with `α ≤ β`:
  (0,0)→0, (0,1)→1, (0,2)→2, (1,1)→3, (1,2)→4, (2,2)→5.
- Output: 12 fields, 9 W terms, matching `build_dp0_magnetic_effective`
  exactly (including coefficients ±1 and the (q, q̃, M) factor order).

## 4. Tests (oracle + adversarial)

In `tests/test_mutation_engine.py`:

- **Round-trip independence.** Build dP_0 toric via `build_pure_quiver`,
  `to_json`, `from_json`, assert structural equality to the original
  Theory.
- **Bare mutation field count.** `mutate_bare(dp0_toric, node=0)` produces
  18 arrows on 4 edges and 15 W terms.
- **Bare mutation legitimate FAIL.** Build a DualityClaim with electric
  = dp0_toric and magnetic = `from_json(mutate_bare(...))`. Run
  `evaluate_claim`. Anomalies CERTIFY (since the bare magnetic is
  anomaly-free), but `bounded_chiral_ring_consistency` FAILs at
  length-1 R=2/3 with electric_dim=9, magnetic_dim=3 (only `X12` at
  R=2/3). This pins the integration step's necessity.
- **MVP oracle.** `to_json(mutate_bare(to_json(dp0_toric),
  node=0))`, then `integrate_linear_fields`, then `from_json`.
  Assert structural match (per-field) to
  `build_dp0_magnetic_effective(N=3)` — same arrows, same W terms,
  same R-charges, same coefficients. Build the duality claim; assert
  bounded chiral-ring CERTIFIED at L=3 r_graded.
- **Adversarial regression.** Take the engine's effective output, drop
  one W term (e.g. the (0,0)-diagonal), rebuild the duality claim,
  assert bounded chiral-ring FAILs at block (length=3, R=2) with
  electric_dim=10, magnetic_dim>10.
- **Boundary regression on F_0 phase II** (see §5 "Dual R-charge
  assignment" limitation). Confirms the engine reproduces the
  *topology* of the non-toric dual (ranks, edge multiplicities, total
  chiral count) but the verifier correctly rejects the trial UV R
  assignment on mixed-anomaly grounds. This is a *boundary* regression
  — it pins where Phase 2c0 stops and Phase 2c1 begins.

## 5. Out of MVP scope

- **Dual R-charge assignment.** The engine applies the naive Seiberg
  formula `R(q̃) = 1 − R(Q)`, `R(M) = R(Q) + R(Q̃)`. This is best
  read as a *trial UV mutation R* rather than the SCFT R of the dual.
  For SQCD and for quivers where the electric R already coincides with
  the dual's anomaly-free R (e.g. dP_0), the trial R is also the SCFT
  R and the verifier certifies. For quivers like F_0 phase II — where
  the dual's exact R needs re-solving against baryonic/flavor (and in
  some cases accidental) U(1)s — the trial R fails the SU(N)² × U(1)_R
  mixed anomaly on the non-dualized nodes, and the verifier (correctly)
  rejects. The right next step is **not** full a-maximization on top of
  the engine. The right next step (Phase 2c1) is a two-layer R-repair:
  first solve the linear feasibility space `R(W)=2 ∧ Σ mixed = 0` on
  the dualized theory; a-maximize *only* when a unique SCFT R is
  required by downstream obligations (central-charge matching,
  unitarity). The two layers serve different needs and keep the engine
  itself out of the optimization business.
- Multi-node mutation chains (the engine should be composable, but
  Phase 2c will test composition).
- Adjoint Seiberg duality at a node carrying an adjoint loop (Kutasov).
- F-term integration beyond linear-field elimination (no general
  Gröbner; no quadratic mass matrices that couple non-bilinearly).
- Robustness when `_find_linear_field` returns a candidate whose
  subsequent substitution constraint (single-term identification) is
  violated. The current engine raises `MutationEngineError` with the
  blocking field name; Phase 2c1 should turn this into an *informative
  non-fatal* deferred-elimination signal so a caller (mutation chain
  runner, LLM harness) can decide whether to fall back, without losing
  diagnostic detail.
- Picking a non-default sign convention for the Seiberg coupling
  (MVP locks `y = +1` and lifts coefficients from the electric W
  verbatim — for dP_0 this yields the `ε` signs the verified fixture
  expects).
- Symmetry-map JSON between electric and dualized theories. Phase 2c
  LLM harness deals with operator maps; Phase 2c0 only emits the
  pure_quiver theory itself.
