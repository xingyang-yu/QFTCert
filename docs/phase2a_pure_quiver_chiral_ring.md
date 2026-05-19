# Phase 2a Design — Bounded Cyclic Path-Algebra Quotient Check

**Status:** Design (not yet implemented). Approved direction as of 2026-05-18.
**Scope:** `pure_quiver` claims only. Other theory kinds → `NOT_APPLICABLE`.
**Output verdict:** `PASSED_BOUNDED_CHIRAL_RING_CONSISTENCY(L)` / `FAILED_AT_BLOCK(l, r)` /
`UNKNOWN` / `NOT_APPLICABLE`. The check is named
`bounded_chiral_ring_consistency` in the registry.

This document defines a single new obligation. It must not be marketed as a
"chiral ring equivalence" check. It compares **bounded single-trace
cyclic-word data** between two `pure_quiver` theories under explicit cutoff
and convention assumptions.

## 1. What this check is and is not

### Is
- A finite, exact-rational comparison of two `Theory` objects' bounded
  cyclic-word quotients in the path algebra, modulo the two-sided ideal
  generated (up to cutoff) by cyclic derivatives of the superpotential.
- Restricted to the single-trace sector: cyclic equivalence classes of
  closed walks. Multi-trace operators are not enumerated.
- Bounded by a path-length cutoff `L` recorded in the certificate.
- Optionally R-graded: when the superpotential is R-homogeneous and all
  arrow R-charges are provided, blocks are split by (length, total
  R-charge).

### Is not
- A chiral ring equivalence or isomorphism check. PASS only means
  block-wise dimension agreement up to cutoff `L`.
- A Groebner / noncommutative ideal completion. The two-sided ideal is
  generated only up to length `L`; truncation effects are part of the
  guarantee, not bugs.
- A multi-trace, moduli-space, baryonic-branch, or quantum-corrected
  chiral ring engine. These are explicit non-goals (Section 12).

## 2. Conventions

Fix once, used everywhere. Drift here will silently corrupt every
downstream `pure_quiver` test.

**Arrows.** An arrow `X` has `source(X)` and `target(X)`. Conventionally
"X points from source to target."

**Path multiplication: left-to-right traversal.** A product `AB` denotes
"first traverse `A`, then traverse `B`." It is defined iff
`target(A) == source(B)`, and the result has `source(AB) = source(A)`,
`target(AB) = target(B)`. In particular `(AB)C == A(BC)` and the empty
path at node `v` is the idempotent `e_v` with `e_v X = X` iff
`source(X) = v`.

**Closed walks and cyclic words.** A closed walk at node `v` is a path
`P` with `source(P) = target(P) = v`. A **cyclic word** is an
equivalence class of closed walks under cyclic rotation **only** —
orientation is preserved, walks are not identified with their reverses.
That is, `X Y Z` is equivalent to `Y Z X` and `Z X Y`, but is *not*
equivalent to `Z Y X` unless an explicit physical or geometric input
(e.g. a real-structure / charge-conjugation symmetry) is provided.
Canonical representative: lex-smallest rotation under a fixed total
order on arrow labels. Cyclic words are the single-trace
gauge-invariant operators.

This orientation rule matters from Phase 2b onward: the dP_0
superpotential `ε_{ijk} X^i_{12} X^j_{23} X^k_{31}` is sensitive to
arrow ordering, and silently identifying `X Y Z` with `Z Y X` would
collapse independent operators.

**Length.** `len(P) = number of arrows in P`. Cutoff `L` applies to the
length of cyclic words being analyzed.

**R-charge of a path.** `R(P) = Σ_i R(A_i)` where `P = A_1 ... A_n`.
R-homogeneous superpotential ⇒ R-charge is a well-defined function on
cyclic words.

**Cyclic derivative.** For a single cyclic monomial `W_j =
Tr(A_1 ... A_n)`, define `∂_X W_j` as: for each cyclic rotation
positioning `X` at the start, remove `X` and take the remaining open
path. Sum over occurrences. The result is an element of `e_{target(X)} A
e_{source(X)}` (a path from `target(X)` to `source(X)`). For full
`W = Σ_j c_j W_j`, `∂_X W = Σ_j c_j ∂_X W_j`.

## 3. Inputs

### 3.1 Claim JSON additions

A `pure_quiver` `DualityClaim` is constructed via the existing
`build_claim_from_data` interface. Phase 2a adds one optional metadata
block:

```json
"metadata": {
    "duality_profile": "<profile_name>",
    "theory_kind": "pure_quiver",
    "bounded_chiral_ring": {
        "max_length": 6,
        "require_r_graded": true
    }
}
```

Defaults if the block is absent: `max_length = 6`, `require_r_graded =
true`. A claim asking for `max_length > 8` is rejected at load time
(`UNKNOWN` with rationale) — the linear algebra is fast for small `L`
but the closed-walk count grows multiplicatively.

### 3.2 Theory data already available

Arrows are inferred from existing `Field` objects in `Theory`:
- `field.gauge_reps` has exactly one node with `fundamental` and exactly
  one (possibly the same) node with `antifundamental` → arrow from the
  antifundamental node to the fundamental node, with multiplicity
  `field.multiplicity`.
- `field.gauge_reps` has exactly one node with `adjoint` → adjoint arrow
  at that node (self-loop), with multiplicity `field.multiplicity`.
- Any other configuration in a `pure_quiver` claim → `NOT_APPLICABLE` for
  this check, with the offending field reported.

**Multi-arrow expansion (fixed convention, applies from Phase 2a
onward).** A `Field` with `multiplicity = m > 1` is expanded into `m`
distinct arrows with **machine labels** `Field.name + "[" + str(i) + "]"`
for `i ∈ {0, ..., m-1}` (e.g. `X[0], X[1], X[2]` for a field named `X`
with multiplicity 3). The `Field.name` itself becomes the **display
label** stored on `Arrow.display_label` for diagnostic output; the
machine label is what cyclic-word enumeration, lex ordering, and F-ideal
matrices use. Multiplicity is never an implicit integer; the verifier
always sees three independent arrows, not "X with multiplicity 3."

This is a hard rule from Phase 2a — dP_0's 9 bifundamentals (3 per edge
pair) will rely on it, and deferring the convention to Phase 2b-pre
risks the toy-fixture code defaulting to "at most one arrow per (source,
target) ordered pair." Superpotential terms in the claim JSON must
reference machine labels (`"X[0]"`) when invoking a specific copy and
may not use shorthand.

### 3.3 Superpotential terms

Each `SuperpotentialTerm` in the `pure_quiver` setting must be a single
closed-walk monomial: factors are arrow labels in order, the implied
walk closes, and the coefficient is rational. Multi-trace products and
non-monomial structure are not accepted (→ `NOT_APPLICABLE` with
diagnostics).

## 4. Pre-conditions (Lean-style R-charge contract)

The check refuses to compute a quotient on data it cannot trust. All
must hold before any matrix is built:

| # | Pre-condition | Failure mode |
|---|---------------|--------------|
| P1 | Both sides are `pure_quiver` | `NOT_APPLICABLE` |
| P2 | All arrows have explicit `r_charge` | mode-dependent (see P4 row) |
| P3 | Each `SuperpotentialTerm` on each side has `R = 2` | mode-dependent (see P4 row) |
| P4 | Upstream gauge-anomaly obligations passed on each side (each gauge node `a` is ABJ-free under U(1)_R) — **inherited from Phase 1's `anomalies.py` checks, not re-asserted here** | mode-dependent — see below |
| P5 | Each W term is a closed monomial walk | `NOT_APPLICABLE` |
| P6 | `max_length ≤ 8` | `UNKNOWN` |

**Division of responsibility.** Phase 2a does **not** re-check gauge
anomaly cancellation itself. The Phase 1 anomaly checks in
[`dualitycert/qft/anomalies.py`](../dualitycert/qft/anomalies.py) own that
obligation. Those checks already cover `pure_quiver` claims without
modification: their `applicable_kinds = None` is interpreted by the
registry (`dualitycert/core/registry.py`) as "all non-`FLAVORED_QUIVER`
kinds," so anomaly verdicts exist on every `pure_quiver` claim by the
time Phase 2a runs. Phase 2a then simply *reads* whether anomaly checks
passed on each side; it does not duplicate the arithmetic. (See §14
step 0 for the verification work and the regression that pins it.)

**P2/P3/P4 failure mode depends on `require_r_graded`.** These three
preconditions are *physical R-symmetry* requirements, not requirements
for the bounded path-algebra quotient itself. The quotient is
well-defined as a length-graded object even when no R-symmetry exists.
The check must distinguish the two:

- `require_r_graded = true` (default):
  - P2 missing → `NOT_APPLICABLE` (cannot R-grade without arrow R-charges)
  - P3 fails → `NOT_APPLICABLE` (W not R = 2 ⇒ F-relations not R-homogeneous)
  - P4 fails (any upstream anomaly obligation **not** `CERTIFIED` —
    `FAILED`, `NOT_APPLICABLE`, or missing from `prior_results` — on
    either side) → `NOT_APPLICABLE` with category
    `r_symmetry_anomalous_upstream`, pointing to the specific upstream
    obligation. The R-graded chiral-ring comparison requires a
    physically meaningful, anomaly-free U(1)_R; an absent or
    indeterminate upstream verdict is treated identically to an
    anomalous one because neither supplies the anomaly-free guarantee
    R-grading rests on. Callers that lack an encoded U(1)_R global
    must opt into `require_r_graded = false` (length-only fallback).
- `require_r_graded = false`:
  - P2 / P3 / P4 may all fail without blocking the check. The verifier
    proceeds with the length-only quotient (Section 8 fallback) and
    records explicit warnings in the certificate that this is
    **not** an R-graded physical comparison — it is a structural
    cyclic-word count modulo F-relations only.

This separation prevents conflating "R-symmetry consistency failure"
(which Phase 1 owns) with "path algebra quotient not computable"
(which Phase 2a owns). The two are independent modes of failure and
the certificate must report them as such.

P3 should already be checked by Phase 1's superpotential obligation on
the same claim; P4 is owned by Phase 1's anomaly obligations. Phase 2a
reads their structured results to decide which mode (R-graded vs
length-only) it is allowed to run in, and does not redo their work.

## 5. Building the F-ideal up to cutoff L

This section encodes the **most important** technical commitment of the
Phase 2a design. Naive "put `∂W` itself into the relation row space"
misses most of the F-ideal and would yield false-PASS verdicts.

### 5.1 Generators

For each arrow `X` on a given side, compute the cyclic derivative
`∂_X W` as a `Q`-linear combination of paths from `target(X)` to
`source(X)`. Each generator carries `(source = target(X), target =
source(X), R-charge = 2 - R(X), length = len(W_term) - 1)`.

### 5.2 Two-sided context multiplication up to L

For each generator `g` with `source(g) = s`, `target(g) = t`, `len(g) =
n`, and for each desired total cyclic length `ℓ` with `n ≤ ℓ ≤ L`, and
for each context path `C` with `source(C) = t`, `target(C) = s`, `len(C)
= ℓ - n`:

1. Form `C · g`, a closed walk at node `t` of length `ℓ` (a `Q`-linear
   combination of closed walks, one per monomial term in `g`).
2. Project to cyclic words (sum over the cyclic class of each closed
   walk's lex-min rotation, accumulating coefficients).
3. Emit one relation row per `(g, C)` pair in the matrix for block `ℓ`
   (or `(ℓ, r)` if R-graded; see Section 6).

Contexts `C` are themselves enumerated as free paths (no F-reduction
applied to contexts). Redundant relations are absorbed by the rank
computation. This is the bounded analog of saturating the two-sided
ideal `(∂W)` to length `L`.

### 5.3 Rationale

If `∂_X W = Y · Φ` for the toy fixture (Section 11), the relation in
the cyclic-word basis at length 3 comes from context `C = X` (the only
length-1 path `source 1 → target 2`), giving cyclic word `XYΦ = 0`. At
length 4 there are more contexts (`X · Φ`, `Φ · X`, ...), producing
multiple distinct relations. Without enumerating contexts, the quotient
at length 4 would be over-counted.

### 5.4 Cost

Number of cyclic words at length `ℓ` is bounded by `A^ℓ / ℓ` where `A`
is the number of arrows. Number of context-multiplied relations at
length `ℓ` is bounded by `(# generators) · A^{ℓ-n_min}`. With `L = 6`
and a handful of arrows, both fit comfortably in a sparse `Fraction`
matrix and `sympy.Matrix.rank()` finishes in milliseconds.

## 6. The two operations: Reduce and Compare

The Phase 2a check is two distinct operations with separate
responsibilities. Both run on each side independently.

### 6.1 Reduce — build the quotient basis

For a given side:
1. Enumerate cyclic-word basis `B_ℓ` for each `ℓ ∈ 1..L` (and optionally
   bucket by R-charge into `B_{ℓ,r}`).
2. Build relation matrix `M_ℓ` (or `M_{ℓ,r}`) from Section 5.
3. Quotient dimension: `dim Q_{ℓ,r} = |B_{ℓ,r}| - rank(M_{ℓ,r})`.

The "normal form" of a specific cyclic word — for diagnostic / repair
prompt use — is its image under projection onto a chosen complement of
`row(M)`. Phase 2a exposes this as a utility but does not require it for
the verdict.

### 6.2 Compare — block-wise dimension match

For each `(ℓ, r)` block, compare `dim Q_{ℓ,r}^{electric}` against
`dim Q_{ℓ,r}^{magnetic}`. Verdict logic in Section 7.

## 7. Verdict semantics

Outcomes:

- **`PASSED_BOUNDED_CHIRAL_RING_CONSISTENCY`**: every tested `(ℓ, r)`
  block has equal electric and magnetic quotient dimension. Certificate
  must include the cutoff `L`, the list of tested blocks, and explicit
  acknowledgement that this does not imply chiral-ring equivalence.
- **`FAILED`**: at least one `(ℓ, r)` block has unequal dimensions.
  Diagnostic includes the offending blocks, dimensions on each side,
  and one or two sample cyclic words from each side at the smallest
  failing block.
- **`UNKNOWN`**: pre-condition P6 violated (cutoff too large), or
  internal numeric pathology (e.g. rank computation timed out — should
  not happen at `L ≤ 8` but is recorded defensively).
- **`NOT_APPLICABLE`**: any of P1, P2, P3, P4, P5 violated, or claim is
  not `pure_quiver`. (Recall that under `require_r_graded = true`, P3
  and P4 also fire `NOT_APPLICABLE`; under `require_r_graded = false`,
  P3 and P4 are downgraded to warnings and length-only fallback runs.)
  Recorded with explanation.

`FAILED_AT_BLOCK(l, r)` is a structured detail inside the `FAILED`
result, not a separate top-level status.

### Certificate `details` for this check

Mandatory keys:

```python
{
    "cutoff_L": int,
    "mod_cyclic_rotation": True,
    "orientation_preserved": True,        # cyclic only, not reversal
    "r_graded": bool,
    "r_graded_blocked_by": list[str],     # subset of {"P2","P3","P4"}, empty if r_graded
    "context_multiplied_ideal": True,
    "tested_blocks": [{"length": int, "r_charge": "Fraction(...)"|None,
                       "electric_dim": int, "magnetic_dim": int}, ...],
    "failed_blocks": [...],   # subset of tested_blocks with mismatch
    "sample_operators": {     # at most 2 per side per failed block
        "(l, r)": {"electric": [...], "magnetic": [...]}
    },
    "arrow_machine_labels_electric": [...],  # canonical labels per side
    "arrow_machine_labels_magnetic": [...],
    "preconditions": {"P1": "pass", ..., "P6": "pass"},
    "limitations": [
        "two-sided F-ideal generated only up to length L",
        "single-trace sector only",
        "cyclic rotation only — no orientation-reversal identification",
        "no quantum / instanton corrections",
        "no a-maximization, R-charges taken as claim input",
    ],
}
```

## 8. R-graded vs length-only fallback

Default behaviour when `require_r_graded = true`:
- P3 ensures every W term is R = 2 (so F-relations are R-homogeneous).
- P2 ensures every arrow has an R-charge.
- P4 (upstream anomaly check passed) ensures the U(1)_R is
  gauge-anomaly-free, so the R-grading corresponds to a physical
  symmetry. Anomalous U(1)_R would still admit an R-graded *formal*
  count, but the physics interpretation collapses, and the upstream
  Phase 1 failure already speaks to that — no point doing the formal
  count here.
- → safe to bucket blocks by `(ℓ, r)`.

If `require_r_graded = false`, the check accepts P2/P3/P4 failures and
falls back to length-only comparison (blocks indexed by `ℓ` alone). The
certificate records:
- `r_graded = false`,
- `r_graded_blocked_by`: which of P2/P3/P4 failed, with structured
  reasons (P4 entry includes the upstream anomaly obligation id),
- an explicit warning that the result is a **structural cyclic-word
  count modulo F-relations**, not an R-graded physical chiral-ring
  comparison.

This mode is strictly weaker (accidental block-size coincidences across
R-grades become invisible) and is intended for early prototyping or for
quivers without a candidate non-anomalous U(1)_R. Production
`pure_quiver` claims should keep `require_r_graded = true` and produce
P2/P3/P4 as Phase-1 obligations passing before Phase 2a runs.

If `require_r_graded = true` and any of P2/P3/P4 fail, the verdict is
`NOT_APPLICABLE` with the appropriate category — the R-graded check is
suppressed and the certificate points to the upstream physics obligation
that needs to be fixed first (Phase 1 superpotential R-charge check for
P3, Phase 1 anomaly check for P4). Phase 2a does not re-flag a physics
failure that Phase 1 already reported.

## 9. Module and API layout

New module: `dualitycert/qft/quiver_chiral_ring.py`.

Public surface (sketch — names may evolve during implementation):

```python
@dataclass(frozen=True)
class Arrow:
    label: str
    source: str           # gauge node label
    target: str
    r_charge: Fraction

@dataclass(frozen=True)
class CyclicWord:
    arrows: tuple[str, ...]   # lex-min rotation; canonical
    length: int
    r_charge: Fraction | None

def extract_arrows(theory: Theory) -> tuple[Arrow, ...]: ...
def cyclic_derivative(W: tuple[SuperpotentialTerm, ...], arrow: Arrow)
    -> Mapping[tuple[str, ...], Fraction]: ...
def enumerate_cyclic_words(arrows, max_length) -> Mapping[int, tuple[CyclicWord, ...]]: ...
def build_relation_matrix(arrows, W, max_length, r_graded=True)
    -> Mapping[Block, Matrix]: ...
def quotient_dimensions(arrows, W, max_length, r_graded=True)
    -> Mapping[Block, int]: ...

def bounded_chiral_ring_consistency_check(claim: DualityClaim) -> CheckResult: ...
```

`Block = tuple[int, Fraction]` when R-graded, `tuple[int, None]` when
length-only. Sparse matrices use `sympy.Matrix` with `Rational` entries
(consistent with the rest of the codebase's exact-rational stance).

The existing `dualitycert/qft/chiral_ring.py` stays untouched — it is
SQCD F-term consequence logic, not a path algebra engine, and
intermixing them risks regressions on Phase 1.6 checks. The two modules
co-exist.

## 10. Registry integration

Append one `CheckSpec` to `dualitycert/qft/checks.py`:

```python
CheckSpec(
    name="bounded_chiral_ring_consistency",
    runner=bounded_chiral_ring_consistency_check,
    applicable_kinds=frozenset({"pure_quiver"}),
    applicable_duality_profiles=None,    # all pure_quiver profiles
    always_run=False,
)
```

Place after `theory_kind_classification` and the universal anomaly
checks, so that pre-condition P4 (gauge anomaly cancellation) has
already produced its own structured result and Phase 2a can reference
it without re-running.

## 11. Toy fixture for Phase 2a self-test

The Phase 2a tests must exercise both `Reduce` and `Compare` without
depending on any specific physics duality. The dP_0 sanity check
belongs to Phase 2b-pre.

### 11.1 The toy quiver

Two gauge nodes `1`, `2`. Arrows (each with `multiplicity = 1`, so
machine label and display label coincide):
- `X : 1 → 2`, R-charge `2/3`
- `Y : 2 → 1`, R-charge `2/3`
- `Φ : 1 → 1` (adjoint at 1), R-charge `2/3`

Superpotential: `W = Tr(Φ X Y)` with coefficient `1`. Each W term has
length 3 and R-charge `2`. ✓ P3.

The toy intentionally does **not** exercise multi-arrow expansion (§3.2);
that is covered by a separate unit test that takes the same quiver with
`multiplicity(X) = 2` and checks the machine labels `X[0], X[1]` appear
as independent generators in the cyclic-word enumeration.

Cyclic derivatives under the conventions of Section 2:
- `∂_Φ W = X Y` (path `1 → 2 → 1`, length 2, R-charge `4/3`)
- `∂_X W = Y Φ` (path `2 → 1 → 1`, length 2, R-charge `4/3`)
- `∂_Y W = Φ X` (path `1 → 1 → 2`, length 2, R-charge `4/3`)

### 11.2 Self-equivalence test

Compare the toy quiver to itself. Every `(ℓ, r)` block trivially has
equal dimensions → verdict `PASSED_BOUNDED_CHIRAL_RING_CONSISTENCY`.
Confirms the pipeline does not crash and that cyclic-word
canonicalisation and F-ideal saturation are stable under identity.

### 11.3 Detectable failure tests

Three intentionally broken comparisons:
1. **Wrong arrow R-charge on magnetic side** (e.g. `R(Y) = 1/2`): P3
   should already fail on the magnetic side; Phase 2a returns
   `NOT_APPLICABLE` and the existing R=2 obligation catches the bug.
2. **Wrong arrow count on magnetic side** (drop `Φ`): Compare detects
   length-3 block dimension mismatch (electric has nonzero count, magnetic
   has zero) → `FAILED_AT_BLOCK(3, 2)`.
3. **Wrong superpotential on magnetic side** (replace `Tr(Φ X Y)` with
   `Tr(Φ Φ Φ)`): P5 still satisfied (closed monomial), but the F-ideal
   differs and length-3+ block dimensions diverge → `FAILED_AT_BLOCK`
   diagnostic identifies the smallest failing block.

These three cases pin down Reduce, Compare, and the F-ideal contract
respectively.

## 12. Out of scope (must be recorded as limitations)

The verifier outputs these alongside every Phase 2a certificate so
downstream consumers do not over-interpret PASS:

- multi-trace operators and their mixing;
- moduli-space / Hilbert series equivalence beyond single-trace block
  counts;
- quantum / instanton corrections to the chiral ring;
- non-monomial or multi-trace superpotential terms;
- accidental U(1)s and a-maximization;
- baryonic branches (would require ε-tensor invariants beyond cyclic
  words);
- non-rational R-charges (Fraction-only is enforced);
- F-ideal saturation beyond length `L` (the cutoff is intentional and
  must be reported in every certificate);
- orientation-reversal identifications (e.g. an unspecified real
  structure / charge conjugation): not applied — cyclic words are
  identified only under rotation, not under reversal. Fixtures that
  *do* admit such an identification must declare it explicitly.

## 13. Open questions deferred to Phase 2b / 2b+

- Should `Reduce(specific operator)` be exposed in CLI for repair-loop
  use? — likely yes, but only when Phase 2b operator maps need it.
- Mutation engine (Phase 2b+) outputs JSON claims; does that JSON
  include `bounded_chiral_ring.max_length` overrides? — propose a
  per-mutation-depth default scaling, but defer to engine design.
- Per-block sample operator selection: lex-min vs physically meaningful
  (e.g. shortest)? Lex-min is deterministic and is the default; revisit
  if dP_0 diagnostics need physical naming.
- Orientation-reversal identification on quivers with a real structure
  (e.g. SO/Sp gauge groups, parity-related dualities). Not in Phase 2a
  scope; if/when added, it will be an explicit per-claim flag, never
  inferred.

## 14. Implementation sequencing

0. **Verify Phase 1 anomaly coverage of `pure_quiver` — no registry
   changes needed.** `CheckSpec.applicable_kinds = None` already means
   "all non-`FLAVORED_QUIVER` kinds," so the SU(N)^3 cubic and SU(gauge)^2
   U(1) anomaly checks fire for `pure_quiver` claims without any
   registry modifications. `anomalies.py` runners are already K-agnostic
   (no hard-coded `"Q"` / `"Qtilde"` assumptions). One real bug *was*
   fixed in [`anomalies.py`](../dualitycert/qft/anomalies.py) during this
   work: `gauge_anomaly_cancellation` was double-counting
   `field.multiplicity` (an explicit factor on top of the one already
   inside `_spectator_dimension`). SQCD/Kutasov tests were unaffected
   because they use `multiplicity = 1`; dP_0 and any future quiver with
   `multiplicity > 1` would have produced silently-inflated anomaly
   numbers. Regression pinned by `test_cubic_anomaly_multiplicity_scales_linearly`
   (mult=1 vs mult=3 must give 1:3, the bug gave 1:9).

   Step 0 adds [`tests/test_pure_quiver_anomalies.py`](../tests/test_pure_quiver_anomalies.py)
   (10 tests, all pass; 103 total) to pin this coverage:
   - cubic gauge anomaly CERTIFIED on the 3-node SU(3)^3 cyclic fixture
     (3 bifundamentals per directed edge pair, R = 2/3). SU(3) is chosen
     over SU(2) because SU(2) fundamentals are pseudoreal and the
     ordinary SU(N)^3 cubic anomaly is degenerate there (Witten global
     anomaly applies separately and is not implemented);
   - SU(gauge)^2 U(1)_R mixed anomaly CERTIFIED at R = 2/3, FAILED at
     R = 1/2, NOT_APPLICABLE when no `GlobalSymmetry(kind="U1_R")` is
     present;
   - regression on multiplicity scaling (catches the bug above);
   - SQCD/Kutasov-specific checks correctly NOT_APPLICABLE on pure_quiver.

   **Physics note on the §11 toy fixture (Φ/X/Y, W = Tr(ΦXY), all R = 2/3):**
   This 2-node quiver is NOT ABJ-free under U(1)_R for any SU(N₁)×SU(N₂)
   with N₁, N₂ ≥ 2 (derivation in the module docstring of
   `test_pure_quiver_anomalies.py`). The toy is therefore a
   **structural test only** — it runs with `require_r_graded = false`.
   R-graded verification of the bounded chiral-ring comparison uses the
   3-node SU(3)^3 cyclic fixture introduced in step 0, which IS ABJ-free.
1. Land the `Arrow` / `CyclicWord` extraction with a unit test on the
   toy quiver (no F-ideal yet, just enumeration).
2. Land `cyclic_derivative` with hand-checked outputs for the toy.
3. Land `build_relation_matrix` with two-sided context multiplication;
   test against hand-computed `dim Q_{ℓ, r}` for the toy at `L = 4`.
4. Land `bounded_chiral_ring_consistency_check`; add the three Section
   11.3 failure fixtures. **Architecture decision required before this
   step.** The current pipeline ([`dualitycert/qft/dualities.py`](../dualitycert/qft/dualities.py)
   `evaluate_claim`) runs each obligation independently — no checker can
   read another checker's result. Phase 2a's P4 ("upstream anomaly
   passed?") needs one of:

   - **(A) Context accumulator (recommended).** Extend `evaluate_claim`
     to maintain a `dict[str, CheckResult]` keyed by obligation name and
     pass it to each subsequent obligation. `CheckSpec.factory` signature
     becomes `(claim, prior_results) -> Obligation`. Touches: registry,
     dualities.py, and every checker that wants to opt in (rest can
     ignore the new argument). Cleanest long-term, ~30-line core change.
   - **(B) Two-pass registry.** Tag each `CheckSpec` with a `phase: int`;
     phase-2 checkers receive phase-1 results. More structural but
     overkill for the immediate need.
   - **(C) Re-run anomaly internally.** Have the bounded chiral-ring
     check call `gauge_anomaly_cancellation` / `gauge_global_mixed_anomaly_cancellation`
     itself before doing path-algebra work. Zero architecture change,
     ~10 lines of duplication. Acceptable if Phase 2a is the only
     consumer; ugly if more upstream-reading checkers follow.
   - **(D) Claim metadata gate.** Require the claim loader to pre-validate
     anomalies and stamp `metadata["anomaly_passed"] = bool`. Moves the
     check outside the obligation system. Rejected because it
     bypasses the structured certificate audit trail.

   **Recommendation: (A).** It is the smallest change that unblocks
   future cross-checker reads (Phase 2b will need to read Phase 2a's
   result the same way). Implement before step 4 begins.
   Then the bounded chiral-ring checker reads
   `prior_results["electric gauge anomaly cancellation"].status` etc.,
   and emits `NOT_APPLICABLE` with category `r_symmetry_anomalous_upstream`
   pointing at the failed obligation name.
5. Wire into `checks.py` registry, update `design.md` Roadmap entry to
   point here, update `MEMORY.md` notes.

No dP_0 fixture, no mutation engine, no LLM harness in Phase 2a.
