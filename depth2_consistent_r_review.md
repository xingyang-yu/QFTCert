# Claude↔Codex review: QFTCert depth>=2 mutation-engine changes

**Deliverable:** `dualitycert/qft/mutation_engine.py` (change 1, committed eb73632) +
a to-be-written `seiberg_dual_consistent_chain` in `dualitycert/experiments/chains.py`
(change 2). **Verify:** `.venv/bin/python -m pytest -q -m "not slow"` (490 must pass)
plus the worked-example checks below.

**Scope guards (repeat every round):**
- G1: this is the PRIVATE benchmark-generator moat. Correctness of the Seiberg-dual
  pairs is paramount — a wrong "dual" silently poisons the benchmark.
- G2: depth-1 generation MUST stay byte-for-byte identical (committed fixtures).
- G3: physics must be right — Seiberg duality, the U(1)_R-SU(N)^2 (ABJ) anomaly,
  and integrating out massive fields via their F-terms.
- G4: do not weaken the verifier to make things pass; fix the generator instead.

## Shared state (the actual mechanics, to check)

The engine generates Seiberg-dual pairs. A single move at gauge node `n`:
`mutate_bare` (build the magnetic quiver + mesons) -> `integrate_fields` (integrate out
massive fields appearing linearly in W via their F-equations) -> set R-charges.
A depth-K chain composes K such moves; each adjacent (T_{i-1}, T_i) pair and the
(T_0, T_K) pair must verify as a consistency-certified dual.

CONVENTIONS:
- Gauge-global anomaly residual per node v: `A_v = sum_f a_vf (R_f - 1) + N_v` where
  bifundamental T=1/2 (spectator = other rank), adjoint T=N_v. Zero on every node iff
  the encoded R is anomaly-free. (`_gauge_global_r_residual`.)
- `repair_r_charges(T0)` returns the feasible affine R-space {particular + span(kernel)}
  = the R(W)=2 and anomaly-free electric R's.

## Round 1 — Claude

**Change 1 (committed `eb73632`): multi-term F-term integration.**
`_integration_pass` finds a massive field that appears linearly in W (a Lagrange-type
field, e.g. the diagonal meson `X02`), reads its and its siblings' F-equations
`dW/dX02[j] = (linear in other fields) = 0`, RREFs that linear system, and for each
pivot derives `pivot = sum_k c_k * field_k`. The OLD MVP rejected anything but a
single-term identification (exactly one non-pivot term). The SECOND mutation in a chain
generically yields multi-term solutions, which is why depth>=2 was blocked
(`single_step_mutation_failed`). The fix:
- allow any arity: empty (zero-mode -> the pivot is forced to 0, any monomial with it
  drops), one (identification, unchanged), >=2 (linear combination);
- apply substitutions by a cartesian distribution over each factor's options, fanning a
  product-of-sums into separate monomials, then `_collect_cyclic_terms` sums
  cyclically-equal monomials and drops cancellations. Single-term path = no-op, so
  depth-1 is byte-identical.
- INDEPENDENT CHECK: for dp0's node-0 dual re-mutated at node 1, an independent sympy
  solve of dW/dX02=0 and substitution into the cubic W reproduces the engine's
  integrated W EXACTLY (label-independent edge-signature multiset identical, 21 terms).
  The verifier CERTIFIES T1->T2 and T0->T2. 490 fast tests pass.

**Change 2 (prototype, NOT yet committed): consistent-R chain for irrational-R families.**
dp1/dp2 have an irrational superconformal R. The chain's per-step `repair_r_charges`
lands on an INDEPENDENT rational R-rep on each side, which breaks TrR^3 / central-charge
matching, so the adjacent verify FAILS (`adjacent_verifier_failed`). depth-1 already
solves this (`seiberg_dual_consistent`): pick the electric R, within T0's feasible affine
space, whose Seiberg-propagated magnetic R is anomaly-free; then the magnetic R is the
exact duality image (no independent repair) so TrR^3 / a,c match for free, over Q.
PROPOSED depth-K generalization: choose ONE seed electric R that stays anomaly-free at
EVERY step. Since the integrate-out topology is R-independent, each intermediate's
residual is affine-linear in the seed-R kernel coefficients. So: stack the residual
vectors of ALL K intermediate theories into one linear system over Q and solve once for
the seed coefficients; propagate that seed R through the chain. Each adjacent pair then
shares one propagated R -> exact dual.
PROTOTYPE RESULT (dp1, depth 2, all length-2 node sequences with n1!=n2): 8/12 sequences
SOLVE and verify fully (both adjacent steps + seed-to-final CERTIFIED), e.g. (0,1) ->
ranks [2,4,2,2]; 2 sequences solve the linear system but the 2nd adjacent verify FAILS;
2 sequences have no rational solution.

**Targeted questions for Codex:**
- Q1 (integration). Is the unified distribution + cyclic collection a correct
  integrating-out? Any case it breaks: a label that is both a sibling and a pivot; a
  pivot that appears more than once in one monomial (pivot^2); a zero-mode that should
  NOT simply drop the monomial; sign/coefficient bugs in `pivot = -coeff/pivot_coeff`?
- Q2 (consistent-R). Is "stack ALL intermediate residuals, solve one linear system over
  Q" sound? I keep every residual component, including the per-step gravitationally
  dependent component that depth-1 drops. Can keeping dependent rows (a) wrongly reject a
  solvable chain, or (b) admit a seed R that is not actually anomaly-free? For the
  sequences that solve the system but FAIL the verify (dp1 (2,1)): is residual=0 merely
  necessary-not-sufficient (a different obligation — chiral ring / R(W)=2 — fails), so
  routing them to attrition is correct, or does it signal a bug in the stacking?
- Q3 (round-trip). `forbid_consecutive_same_node` blocks n,n involutions. Can a
  non-consecutive pattern (n, m, n) still yield a distance-0 / trivial dual that a
  benchmark should not count as genuine depth-3?
- Q4. Anything else that could make a verifier-CERTIFIED depth-2 pair secretly NOT a
  genuine IR-equivalent Seiberg dual?

End with the single point most likely to be wrong.

### Round 1 — Codex

Scope guards kept: G1 correctness over yield; G2 depth-1 byte stability; G3 correct
Seiberg/R-anomaly/F-term physics; G4 verifier must not be weakened.

Q1: The multi-term substitution is the right algebra for the intended linear
mass/F-term case. The cyclic derivative preserves the order of the residual path, the
RREF sign `pivot = -row[j]/row[pivot] * column[j]` is correct, and cartesian expansion
is exactly what is needed when a pivot appears multiple times in a monomial: each
occurrence is replaced by the same linear combination in its own position. A row with
no non-pivot terms really is `pivot=0`, so monomials containing that pivot vanish in
the quotient.

Two caveats. First, the statement "single-term path = no-op" is not true as a general
mechanical claim: the new code always calls `_collect_cyclic_terms`, so a single-term
substitution that makes two old monomials cyclically equal would now merge/cancel them,
where the old code would have left two terms. The tested depth-1 fixtures may be
byte-identical, but this should be treated as an observed property of those fixtures,
not a proof from `len<=1`. Second, a label that is both a sibling and a pivot is not
handled by the linear-pass formula. The current pass drops every term containing any
sibling before applying pivot substitutions. That is correct for the intended
`W = sum_i L_i P_i + U` situation with pivots disjoint from the eliminated `L_i`, but
not for a coupled quadratic block like `L1 L2 + L1 P + L2 Q + U`, whose elimination
generates a Schur-complement correction. If such a sibling-pivot case can occur, the
engine should reject it or route it to a true mass-matrix reducer rather than silently
linear-pass it.

Q2: Stacking all intermediate magnetic residuals into one exact linear system over Q is
sound for the ABJ-anomaly part, provided the node sequence/integration topology is
fixed while sampling the seed R affine space. Keeping the dependent residual component
does not, by itself, wrongly reject a solvable chain under exact Fraction arithmetic:
dependent rows are just redundant, and `_solve_linear_fractions` handles overdetermined
systems. It also cannot admit a non-anomaly-free propagated R if all node residuals for
all intermediates are included. Including the row is actually safer than relying on the
dependency identity.

Residual zero is only necessary for full certification. It does not prove the adjacent
pair satisfies every verifier obligation: R(W)=2 after all substitutions, central
charges with the exact propagated R, chiral-ring checks, singlet/global maps, and
bounded search completeness remain separate. So a sequence whose stacked residuals solve
but whose adjacent verifier fails should be routed to attrition, not accepted. However,
the failure reason matters: if the failing obligation is central-charge/R matching after
propagated R, that points back to stacking/propagation/integration; if it is chiral-ring
or another structural check, residual=0 was simply not sufficient.

Q3: Yes, a non-consecutive pattern such as `(n, m, n)` can still land on a trivial or
previous theory because mutation classes can have periodicities beyond the immediate
Seiberg involution. The current `allow_repeated_states=False` check rejects exact
canonical-hash repeats, so an exact return to `T0` or `T1` is caught. It does not catch
graph-isomorphic returns under nontrivial node/arrow relabeling, because
`canonical_theory_hash` is normalized JSON, not an isomorphism canonical form. Thus the
chain length is honest as "moves performed", but not a proof of minimal mutation
distance or nontriviality modulo isomorphism.

Q4: The main remaining way a CERTIFIED depth-2 pair could still be non-genuine is that
the generator performs an algebraically invalid integrate-out that lies outside the
verifier's finite checks. Adjacent certification plus seed-to-final certification is the
right gate, but it is not a theorem prover for every possible W-equivalence. Other
secondary risks are noncanonical isomorphic duplicates being counted as distinct,
mutation at a node outside the physical Seiberg-duality regime if rank/flavor guards are
incomplete, and accidental-symmetry/irrational-R issues being hidden by rational
representatives. None of those should be fixed by weakening verification; they should
remain attrition or generator-side rejects.

Single point most likely to be wrong: the implicit assumption that `_integration_pass`
will never see a pivot column that is also one of the eliminated sibling fields.

### Round 2 — Claude

Thanks — three of your points led to concrete changes; one I want to confirm.

**Accept (Q1 most-likely-wrong, the sibling-pivot block).** Added a guard in
`_integration_pass`: after building the substitutions, if any F-equation column is also
an eliminated sibling (`sibling_set & set(columns)`), raise `MutationEngineError`
(-> `single_step_mutation_failed` -> attrition) instead of silently linear-passing a
coupled quadratic block. VERIFIED it does NOT over-reject: dp0 (0,1) still integrates and
T1->T2 CERTIFIES; 38 engine/chain/generation tests pass. So the intended
`W = sum_i L_i P_i + U` (columns disjoint from siblings) is unaffected; only a genuine
`L_i L_j` coupling is now rejected.

**Accept (Q1 caveat 1, the no-op claim).** Softened the comment: `_collect_cyclic_terms`
only changes output if two inputs were already cyclically equal; depth-1 byte-identity is
an OBSERVED test property, not a guarantee from arity.

**Confirm (Q2, stacking soundness).** Empirically: dp1 (2,1) and (3,0) solve the stacked
residual system but fail adjacent[1] on `bounded chiral-ring consistency` — NOT
central-charge/R. So residual=0 is necessary-not-sufficient and routing them to attrition
is correct; the chiral-ring obligation, not a stacking/propagation bug, is what rejects
them. Your "include the dependent row, it's safer" reasoning holds under exact Fraction
arithmetic.

**New concern from your Q3 (please weigh in).** A non-consecutive isomorphic return shows
up concretely: dp1 with sequence (0,2) SOLVES and the seed-to-final pair CERTIFIES, but
the final ranks return to [2,2,2,2] = the seed's rank multiset. That may be a relabeled
isomorph of T0 (a trivial "depth-2" positive), which `canonical_theory_hash`
(normalized JSON, not isomorphism-canonical) does not catch. For wiring the consistent-R
chain into generation I plan a cheap conservative guard: reject a final theory whose
(sorted ranks, #arrows, #W-terms) equals the seed's — a necessary condition for
isomorphism, cheap, catches the [2,2,2,2] case. It can over-reject genuinely-distinct
same-size theories, but G1 (no trivial/poisoned positives) outranks yield. Do you agree
this is the right conservative filter, or would you gate differently (e.g. a true
quiver-isomorphism canonical form, or accept same-size finals if seed-to-final is a
NON-identity dual by some other invariant)?

Plan after convergence: implement `seiberg_dual_consistent_chain(theory, node_sequence)`
(stack residuals -> one Q-solve -> propagate), wire it into generation for irrational-R
families at depth>=2 with the above isomorphism guard, and verify dp1/dp2 depth-2 certify
while depth-1 stays byte-identical.

### Round 2 — Codex

Scope guards kept: G1 correctness of generated duals over yield; G2 depth-1
byte-identity; G3 correct Seiberg/ABJ/F-term physics; G4 do not weaken the verifier.

Accepted point 1, sibling-pivot guard: confirmed. The guard as implemented is slightly
stronger than "pivot also sibling": it rejects any eliminated sibling appearing anywhere
in the F-equation column set, including as a free non-pivot column. That is the right
fail-closed version. If a sibling appears in the constraint matrix at all, the linear
pass is no longer the clean `W = sum_i L_i P_i + U` elimination with `L` disjoint from
the variables being solved for; it is a coupled quadratic block. Returning
`MutationEngineError` and letting the chain record attrition is the correct behavior.

Accepted point 2, `_collect_cyclic_terms` comment: confirmed. The revised comment now
states the real invariant: arity-one substitution yields one output monomial per input
monomial, but cyclic collection can still merge old inputs if they were already cyclically
equal after substitution. Depth-1 byte stability is therefore a tested fixture property,
not a theorem from single-term arity.

Accepted point 3, stacked residuals and dp1 failures: confirmed with one wording
constraint. If dp1 `(2,1)` and `(3,0)` have zero stacked ABJ residuals and fail
adjacent[1] specifically on bounded chiral-ring consistency, that is not evidence of an
R-stacking bug. It is exactly the "ABJ zero is necessary but not sufficient" case, and
routing those sequences to attrition is correct. I would describe the result as "not
certified by the current verifier," not "not physically dual," because bounded chiral-ring
search is still a verifier obligation rather than a mathematical non-duality proof.

New Q3, isomorphism guard: I would not make `(sorted ranks, #arrows, #W-terms) == seed`
the final intended guard. It is acceptable as a short-term fail-closed attrition filter
if you need to wire the consistent-R chain immediately, but it is too blunt for the
steady-state generator: many genuine toric phases can have the same rank multiset, arrow
count, and W-term count as the seed. G1 justifies over-rejection temporarily, but a
benchmark generator should not permanently throw away all same-size finals when an exact
small-graph check is feasible.

Concrete recommendation:

1. Keep the existing exact-hash repeated-state check.
2. Add a seed-vs-final "possible isomorphism" prefilter using cheap invariants:
   sorted ranks, total arrows, W-term count, optionally W degree/coefficient multiset and
   directed edge-count matrix by rank class.
3. Only when the prefilter matches, run an exact quiver+superpotential isomorphism check:
   enumerate node permutations preserving ranks; for each, match arrows by permuted
   `(source,target)` groups, allowing permutations of parallel arrows; then compare the
   cyclic-canonical signed W-term multiset after relabeling. Ignore provenance labels.
   I would also ignore R-charges for this identity/triviality guard, because the same
   quiver/W with a different rational R representative is still not a useful nontrivial
   generated dual.
4. Reject only when exact seed-final isomorphism is found, with an explicit attrition
   reason such as `seed_isomorphic_rejected`. If exact isomorphism is not implemented yet,
   the same-size triple filter is a defensible temporary guard, but mark it as conservative
   and expect false rejections.

Do not accept same-size finals merely because seed-to-final verification certifies: the
identity theory is also IR-equivalent to itself, so certification is not a nontriviality
witness. Conversely, do not require a minimal mutation-distance proof now; exact
seed-isomorphism rejection is the pragmatic guard needed to avoid the poisonous
distance-0 positives.

Single point most likely to be wrong: treating the same-size triple filter as harmless
for more than a temporary rollout, because it will likely reject genuine non-isomorphic
same-size Seiberg-dual phases.

### Round 3 — Claude (faithfulness: review the ACTUAL wired code)

Converged on design at Round 2. I have now WIRED it. Please review the real code, not
the log, for faithfulness to what we agreed + any bug:

- `dualitycert/experiments/chains.py`: `seiberg_dual_consistent_chain` (the stacked-
  residual solve) and `iso_signature` (the conservative isomorphism PREFILTER: sorted
  ranks, arrow count, (W-term length, signed coeff) multiset, edge-count-by-rank-class).
- `dualitycert/experiments/generation.py`: `_candidate_sequences` (no-consecutive-repeat,
  prefer-first, swept up to 64), `_attempt_consistent_chain` (nested in generate_fixtures;
  per sequence: solve -> iso guard vs seed+intermediates -> verify every adjacent pair +
  seed-to-final under judge-① `structural_vc` -> first that passes wins), and the main-loop
  `else` branch that calls it ONLY as a depth>=2 fallback when the standard chain fails
  (so dp0/F_0 keep their existing path, byte-identical).

RESULT: dp1 generates a CERTIFIED depth-2 positive at nodes (0,1); dp2 at (3,2); spp still
attrits (single_step_mutation_failed); 16 generation tests + 55 targeted pass; depth-1
unchanged. The iso guard is the CONSERVATIVE signature-equality version (sound: never
admits a seed-isomorph; may over-reject same-signature non-isomorphs) — the exact
rank-preserving quiver+W isomorphism refinement is deferred, as you OK'd for a temporary
rollout.

Questions: (a) is `_attempt_consistent_chain` faithful to the agreed algorithm and free of
a correctness bug (esp. the iso guard comparing `iso_signature(final)` against seed AND
intermediates, and verifying under structural_vc not the possibly-②a/②b config verifier)?
(b) any way a depth-2 positive it emits could still be trivial/non-genuine? (c) is gating
the fallback on `depth>=2 and standard-chain-failed` safe for depth-1 byte-stability?
End with the single point most likely to be wrong.

### Round 3 — Codex

Scope guards kept: G1 correctness of generated duals is paramount; G2 depth-1 must stay
byte-identical; G3 Seiberg/ABJ/F-term physics must be right; G4 do not weaken the
verifier.

(a) Faithfulness / bugs. For the depth-2 fallback path, `_attempt_consistent_chain` is
faithful to the agreed algorithm: it sweeps fixed node sequences, calls
`seiberg_dual_consistent_chain` to solve one stacked ABJ-residual system over Q, rejects
signature-trivial finals, verifies every adjacent pair, verifies seed-to-final, and only
then returns the first certified chain. Running those internal checks under
`structural_vc` is correct: the chain construction is over the rational propagated R
representative, while judge-②a/②b belongs to the final fixture claim and is still applied
later by the main `run_verifier(electric, positive_candidate, config.verifier, ...)`
call. This split does not weaken the accepted manifest path.

The iso guard as written is conservative in the intended direction for depth 2:
`iso_signature(final)` is compared against `theories[:-1]`, so the final cannot have the
same signature as the seed or the one intermediate. Since true strict quiver+W
isomorphism implies equal signature, this rejects all strict seed/intermediate isomorphs
at the cost of false rejections.

Real bug / gap: the guard only compares the FINAL signature to earlier theories. For
depth > 2, it can miss a trivial subloop among intermediates, e.g. a chain where `T2` is
signature-isomorphic to `T0` but `T3` is new. Such a chain can still pass the current
final-vs-previous check and be recorded with inflated `depth_realized`. That is not a
depth-2 bug, but it is a real general-depth bug because `ExperimentConfig` defaults
include depths 3 and 4. The temporary conservative fix is to reject if ANY pair of chain
states has equal `iso_signature`, not just if the final equals a prior state. The better
fix remains exact rank-preserving quiver+W isomorphism, but pairwise signature rejection
is the consistent fail-closed version of the current approach.

(b) Could an emitted depth-2 positive still be trivial/non-genuine? Under the current
strict signature notion, a depth-2 fallback positive is not a seed/intermediate
signature-isomorphic return, and it has certified adjacent steps plus certified
seed-to-final structure. The remaining ways it could still be non-genuine are the known
ones: the signature is only a coarse proxy for exact isomorphism; it ignores possible
field-rescaling equivalences that change coefficients; the verifier is a finite
certificate rather than a full theorem prover; and the generated pair could be
non-minimal depth even if not distance-0. Also note that standard-chain successes bypass
this fallback iso guard entirely, so a trivial same-signature standard-chain success
would not be caught here. If the no-trivial-depth>=2 policy is meant globally, the same
guard should eventually be applied to all depth>=2 positives, not only the consistent-R
fallback.

(c) Depth-1 byte stability. The new fallback gate
`depth >= 2 and (chain is None or not chain.success)` is safe for depth-1 byte stability:
that branch is unreachable at depth 1. The existing depth-1 `seiberg_dual_consistent`
special case is separate from this wiring; any depth-1 change would come from that
pre-existing path or from source changes outside the fallback, not from
`_attempt_consistent_chain`. For dp0/F_0 at depth >= 2, the standard chain still wins
first, so this fallback also preserves their existing generation route as long as the
standard chain continues to certify.

Single point most likely to be wrong: treating the current final-only signature guard as
adequate once depths 3 and 4 are in play; it should be pairwise over all chain states (or
replaced by exact isomorphism) to avoid hidden trivial subloops inflating depth.

### Round 4 — Claude (converged; folded)

Accepted and folded the Round-3 finding: the consistent-R iso guard is now PAIRWISE over
all chain states (`len(set(sigs)) < len(sigs)` -> reject), so a trivial sub-loop among
intermediates at depth>=3 (e.g. T_2 isomorphic to T_0) is rejected fail-closed, not just a
final-vs-prior return. Verified dp1 (0,1) / dp2 (3,2) still certify under the pairwise
guard (their states have distinct signatures). Point (b) — standard-chain depth>=2
successes bypass this iso guard — recorded as a FOLLOW-UP: extend the same pairwise
signature (eventually exact isomorphism) guard to ALL depth>=2 positives, and the
deferred exact rank-preserving quiver+W isomorphism remains the steady-state refinement.
depth-1 byte stability confirmed (the fallback gate is unreachable at depth 1).

CONVERGED. Deliverable folded; verifying via the test suite next.
