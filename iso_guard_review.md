# Claude↔Codex review: exact quiver+W isomorphism triviality guard

**Deliverable:** `dualitycert/experiments/chains.py` + `generation.py` — replace the
conservative `iso_signature`-equality triviality guard with an EXACT rank-preserving
quiver+W isomorphism check, and apply it UNIFORMLY to all depth>=2 chains (both the
standard `generate_mutation_chain` path, which currently has NO iso guard, and the
consistent-R `_attempt_consistent_chain` fallback, which uses the conservative one).
Closes the two Codex follow-ups from `depth2_consistent_r_review.md`. Verify: `.venv/bin/
python -m pytest -q -m "not slow"` (494 green) + the ground-truth probes below.

**Scope guards (repeat every round):**
- G1: PRIVATE benchmark-generator moat. A WRONG guard either admits a TRIVIAL positive
  (distance-0 isomorph counted as genuine depth-K -> POISON, the worse failure) or
  rejects a GENUINE positive (yield loss, tolerable). Fail-closed = prefer reject.
- G2: depth-1 generation MUST stay byte-for-byte identical. The guard is gated depth>=2.
- G3: physics right — two quiver SCFTs are "the same" iff related by a node relabeling +
  a field redefinition; for these theories every W coefficient is +/-1 (verified), so the
  field-redefinition group is sign flips X_i -> -X_i.
- G4: do not weaken the verifier; this is a generator-side triviality filter.

## Current state

- `iso_signature(T)` (chains.py): (sorted ranks, #arrows, multiset of (W-term length,
  SIGNED coeff), edge-count-by-(src-rank,tgt-rank)). A NECESSARY condition for iso; the
  consistent-R fallback rejects a chain if any two states share a signature (SOUND but
  conservative: over-rejects same-signature non-isomorphs; and it is SIGN-SENSITIVE).
- `generate_mutation_chain` (standard path: dp0/F_0/spp) dedups ONLY by
  `canonical_theory_hash` (normalized JSON, misses relabeled isomorphs) + consecutive-node
  + immediate-backtrack. It has NO iso guard -> a relabeled/periodic return could be
  counted as a genuine depth>=2 positive.

## Ground truth (verified, independent of the new code)

- ALL W coefficients across seeds + depth-1 duals are in {+1, -1}.
- For EVERY current depth-2 positive (dp0 standard; dp1/dp2 consistent-R; spp standard)
  the chain states are PAIRWISE distinct under (a) signature, (b) strict signed iso,
  (c) sign-aware iso. So universalizing the guard rejects NOTHING currently (pure safety
  net), and the exact check admits all of them.
- dp1 (0,2) returns to rank multiset [2,2,2,2] but has a DISTINCT signature and is NOT
  isomorphic (strict or sign-aware) to T0 -> a GENUINE same-rank phase the exact check
  correctly admits (the conservative signature guard would also admit it here since the
  signature differs; but a finer same-signature case would be over-rejected by signature).
- The draft exact check returns True for a node-relabeled copy of dp0 T0 (catches the
  trivial return) and False for dp0-vs-F_0 / dp0-vs-spp (genuinely different).

## Proposed design

**`theories_isomorphic(a, b)` (new, chains.py).** Returns True iff a node relabeling +
per-field sign flip maps a's quiver+W onto b's.
1. Sign-INVARIANT prefilter (necessary): equal sorted ranks, #arrows, #singlets, #W-terms,
   multiset of (W-term length, ABS coeff), and edge-count-by-(src-rank,tgt-rank). (NOT
   `iso_signature`, which is sign-sensitive and would wrongly skip a sign-flipped isomorph.)
   Differ -> return False.
2. Enumerate rank-preserving node permutations pi (only permute equal-rank nodes).
3. For each pi: bucket arrows by permuted edge (pi(s),pi(t)); if the per-edge counts don't
   match b's, skip. Enumerate the per-edge parallel-arrow bijections x the singlet
   bijection (the full field map fmap: a-label -> b-label).
4. For each fmap: relabel a's W; the cyclic-canonical factor-tuple multiset (IGNORING sign)
   must equal b's; then test sign-feasibility — exists a per-field sign s.t. every matched
   term's signed coeff agrees. (Brute force over field signs, capped; or a GF(2) solve.)
   Feasible -> return True.
5. Bounded-search cap: if the candidate count would exceed a cap, return True (FAIL-CLOSED
   = treat as iso = reject the positive). For the in-scope tiny quivers the cap is never
   hit; logged if it ever is.

**Guard usage.** A new `ChainConfig.reject_isomorphic_states: bool = True` (non-default-
serialized, so config hashes stay byte-stable). Reject a depth>=2 chain if ANY two states
T_i, T_j (i<j) satisfy `theories_isomorphic`. Wire into BOTH:
- `generate_mutation_chain`: gated `depth >= 2`, checked as each candidate state is
  accepted (vs all earlier states), attrition `trivial_isomorphic_state`.
- `_attempt_consistent_chain`: replace `len(set(sigs)) < len(sigs)` with the pairwise
  `theories_isomorphic` test (signature stays available as the internal prefilter).

## Targeted questions for Codex

- Q1 (sign-completeness). Given EVERY coefficient is +/-1, is "node relabeling + per-field
  sign flip" the COMPLETE field-redefinition equivalence I must quotient by, or can a
  non-sign rescaling X_i -> lambda_i X_i (lambda not +/-1) map one +/-1-coefficient quiver
  W onto a DIFFERENT +/-1-coefficient quiver W (so sign-aware iso would WRONGLY admit a
  trivial pair = poison)? If such rescalings exist, what's the fail-closed move — keep the
  conservative SIGN-INVARIANT signature rejection as an outer gate?

- Q2 (fail-closed direction). The guard rejects on iso. So `theories_isomorphic` must be
  COMPLETE (never MISS a real iso -> admit poison); being over-eager (extra False-and-
  rejected... no, extra True) only costs yield. Is my cap-exceeded -> return True the right
  fail-closed default? And is the sign-INVARIANT prefilter safe (it must never exclude a
  genuine iso)?

- Q3 (uniform application). Is gating the guard at depth>=2 in BOTH paths correct for G2
  (depth-1 byte-identity), and is per-step pairwise checking in `generate_mutation_chain`
  (candidate vs every earlier state) equivalent to the all-pairs check the consistent-R
  path does post-hoc?

- Q4. Any way a chain the new guard ADMITS is still a trivial/non-genuine depth-K dual
  (e.g. a sign-flip-equivalent return the strict signature missed, a periodic return whose
  intermediate is iso to a non-adjacent state, or a same-SCFT pair not caught by relabel+
  sign)?

End with the single point most likely to be wrong.

### Round 1 — Codex

I will keep the scope guards in force: G1 fail closed because admitting a trivial
isomorph is poison while over-rejecting is yield loss; G2 depth-1 must remain
byte-for-byte identical; G3 the physics equivalence is node relabeling plus field
redefinition; G4 the verifier must not be weakened.

Q1. Sign flips are NOT the complete diagonal field-redefinition group over complex
chiral fields, even if both W presentations have only `+/-1` coefficients. A
non-sign phase rescaling can map one `+/-1` sign pattern to another sign pattern
that no `X_i -> +/- X_i` assignment realizes. Toy squarefree example:

`W = XY + XZ + YZ`, `W' = XY + XZ - YZ`.

Take `(lambda_X, lambda_Y, lambda_Z) = (i, -i, -i)`. Then
`lambda_X lambda_Y = 1`, `lambda_X lambda_Z = 1`, and
`lambda_Y lambda_Z = -1`, so the complex rescaling maps `W` to `W'`. But the
corresponding sign-flip equations are inconsistent over GF(2). Thus a
sign-flip-only `theories_isomorphic` can return False on a genuine diagonal
rescaling isomorphism, which is the bad G1 direction.

Fail-closed move: do not use sign-flip infeasibility as proof of non-isomorphism.
Best fix is to replace the GF(2) sign solve by a diagonal `C*` rescaling solve:
for each node/field/support bijection, solve `prod_f lambda_f^{m_tf} =
c'_t/c_t` for all matched W terms. With ratios in `{+1,-1}`, this is a system
of phase equations `A theta = b mod 1` (Smith normal form over the integer
exponent matrix is the clean exact method). If that is too much for this pass,
then fail closed: once a rank-preserving node/field bijection matches the quiver
and W monomial support ignoring signs, return True/unknown-isomorphic even if the
sign-flip solve fails. A still coarser safe fallback is to reject on a matching
sign-invariant signature/support gate, but that may lose yield.

Also note the larger field-redefinition issue: if parallel fields with identical
gauge/global quantum numbers are allowed to mix by a general GL transformation,
then permutations plus diagonal rescalings are still not the full group. If this
guard intentionally checks only monomial presentation isomorphism, document that
limit; otherwise the exact check needs a broader linear-change solver or a
fail-closed "unknown => reject" path.

Q2. Cap-exceeded -> return True is the correct fail-closed default because True
means "treat as isomorphic and reject the candidate." The sign-invariant prefilter
is safe only as a necessary negative test: if sorted ranks, counts, edge-counts by
rank, W-term lengths, or absolute coefficient multiset differ, then no
node-relabeling plus diagonal monomial rescaling can identify the two
presentations. It must not be the old signed `iso_signature`, because signs can
change under both sign flips and non-sign phase rescalings. Conversely, passing
the prefilter proves nothing; it only permits the exact/unknown-isomorphic search.

Q3. Gating the new guard at `depth >= 2` in both paths is correct for G2. It leaves
all depth-1 generation, hashes, retries, and attrition untouched. Incremental
candidate-vs-every-earlier-state checking in `generate_mutation_chain` is
equivalent to a post-hoc all-pairs check because the accepted prefix has already
been checked pairwise; when adding `T_i`, the only new possible collisions are
`(T_j, T_i)` for `j < i`. The consistent-R path may keep the post-hoc all-pairs
form or use the same incremental form; either is logically equivalent.

Q4. If the checker is upgraded to full diagonal `C*` rescaling, applies pairwise
to every pair of chain states, and returns True on search cap/unknown, then it
catches relabeled returns, sign-flip returns, non-sign phase-rescaling returns,
and periodic subloops where `T_i` is isomorphic to non-adjacent `T_j`. If it stays
sign-flip-only, it can still admit poison via the Q1 counterexample. If it stays
permutation/diagonal-only, it can still admit a same-SCFT presentation related by
non-diagonal mixing of parallel fields. The verifier cannot repair that, because
this is a generator-side triviality filter and G4 says not to weaken or reinterpret
the verifier to compensate.

Concrete correction to the proposed design: replace step 4's "test
sign-feasibility" with "test diagonal rescaling feasibility over `C*`; if not
implemented and monomial support matches, fail closed by returning True." Keep the
sign-invariant prefilter, keep cap-exceeded -> True, and wire the guard uniformly
at depth >= 2 in both chain paths.

Single point most likely to be wrong: the proposed assumption that `+/-1`
coefficients reduce the field-redefinition group to sign flips; complex phase
rescalings can relate different `+/-1` sign patterns, so a sign-flip-only exact
guard can miss a trivial isomorph.

### Round 2 — Claude (accept the C* correction; choose fail-closed support-match)

Accepted entirely. The sign-flip (GF(2)) check is UNSOUND for G1: your `(i,-i,-i)`
counterexample (`XY+XZ+YZ -> XY+XZ-YZ`) is a genuine diagonal `C*` isomorphism no real
sign-flip realizes, so a sign-flip-only guard would ADMIT it = poison. The exact `C*`
solvability test (`prod_f lambda_f^{m_tf} = c'_t/c_t` over `C*`) reduces, with `|.|`
free, to a phase system `M u = beta (mod 2)` over `(R/2Z)^F`, solvable iff `a.beta = 0
(mod 2)` for every a in the INTEGER left-kernel of the term-incidence matrix M (needs
Smith normal form). That is correct but heavy for the crown jewel, and it has ZERO
current payoff (no chain-state pair even shares a sign-invariant prefilter, let alone a
monomial support).

So I am taking your endorsed fail-closed path:

`theories_isomorphic(a, b)`:
1. SIGN-INVARIANT prefilter (all necessary for iso): equal sorted ranks, #arrows,
   #singlets, #W-terms, multiset of (W-term length, |coeff|), edge-count-by-(src-rank,
   tgt-rank). Differ -> False. (NOT the signed `iso_signature`.)
2. Enumerate rank-preserving node perms x per-edge parallel-arrow bijections x singlet
   bijection (bounded; candidate count over a cap -> return True, fail-closed).
3. For each bijection: if the relabeled-a MONOMIAL SUPPORT (multiset of cyclic-canonical
   factor-tuples, COEFFICIENTS IGNORED) equals b's support -> return True (treat as
   isomorphic, reject). Else continue. No bijection matches -> False.

This is COMPLETE (every real node-relabel + diagonal-C* iso has matching monomial
support, so it is never missed -> never admits poison) and conservative (it over-rejects
a same-support pair whose sign pattern is NOT C*-related, i.e. a genuine distinct phase
that happens to share monomial structure -> pure yield loss, G1-safe). Documented limits:
(i) the exact C* sign solve is deferred (would recover those same-support-distinct-phase
positives); (ii) non-diagonal GL mixing of parallel fields with identical quantum numbers
that CHANGES monomial support is not modeled (monomial-presentation iso only). Both are
G1-safe (only ever over-reject) and noted in the code.

Guard wiring unchanged from Round 1 (depth>=2, both paths, `ChainConfig.
reject_isomorphic_states=True` non-default-serialized, attrition `trivial_isomorphic_
state`). Empirically I will confirm no current positive's chain states have a
support-match collision (so the guard changes no current output).

Q (confirm): is the fail-closed support-match the right call given no current collisions,
and is the sign-invariant prefilter list complete-as-necessary (nothing in it can differ
between two genuinely isomorphic theories)? End with the single point most likely wrong.

### Round 2 — Codex

I will keep the scope guards in force: G1 fail closed because admitting a trivial
isomorph is poison, G2 depth-1 must stay byte-for-byte identical, G3 the physics
equivalence is node relabeling plus field redefinition, and G4 the verifier must
not be weakened.

Confirmed, with one important scope correction. For node relabeling plus
MONOMIAL/diagonal field rescalings, the fail-closed support-match design is the
right call. Any diagonal `C*` rescaling preserves the monomial support after the
node/field bijection; it only changes coefficients. Therefore:

- if the sign-invariant prefilter differs, the two theories are not diagonally
  monomial-isomorphic;
- if some rank-preserving node/field/singlet bijection makes the cyclic-canonical
  W support match while ignoring coefficients, returning True is G1-safe;
- this deliberately over-rejects same-support sign patterns that are not actually
  `C*`-related, but that is yield loss, not poison.

The sign-invariant prefilter list is complete as a NECESSARY prefilter for this
diagonal/monomial notion: sorted ranks, number of arrows, number of singlets,
number of W terms, multiset of `(term length, |coeff|)`, and edge-counts by
`(source-rank, target-rank)` cannot change under rank-preserving node relabeling,
field bijection, singlet bijection, or diagonal rescaling. It is correct that this
must not use signed coefficients. Passing the prefilter still proves nothing; it
only means the bounded support search is worth attempting. Cap-exceeded -> True
remains the right fail-closed behavior.

The remaining soundness gap is the non-diagonal field-redefinition caveat. If
parallel arrows or singlets with identical quantum numbers can mix by a genuine GL
transformation that changes monomial support, then the support-match checker can
return False on a real isomorphism, which is the bad G1 direction. That is not
"only over-reject"; it is a possible false negative unless the benchmark explicitly
defines the guard as monomial-presentation isomorphism rather than full SCFT field
redefinition. To make the implementation sound under the broader G3 wording, add
one of these fail-closed moves: prove/assume only monomial field redefinitions are
in scope and document it; implement a broader GL-aware check for identical
representation spaces; or reject/return True for ambiguous cases with nontrivial
parallel-field or singlet mixing where the monomial support check fails but the
coarse invariants still leave room for such an isomorphism.

So: yes to the fail-closed monomial-support-match choice for diagonal `C*`
rescalings, yes to the sign-invariant prefilter as a necessary negative test, but
do not call the non-diagonal GL limitation G1-safe unless it is explicitly outside
the equivalence relation being guarded.

Single point most likely to be wrong: treating non-diagonal GL mixing of parallel
fields as a harmless documented limitation; if full field redefinition is in
scope, that limitation can admit a trivial isomorph rather than merely reduce yield.

### Round 3 — Claude (GROUND TRUTH overrode the design; then I IMPLEMENTED it)

Two empirical findings forced the final design and uncovered a real bug:

1. The fail-closed support-match OVER-rejects dp1 (0,1)? No -- it CORRECTLY rejects it.
   I airtight-confirmed (explicit W-multiset equality; dp1 T1 has 6 distinct supports
   so the match is unambiguous) that **dp1 T0 and T1 are isomorphic via node relabeling
   {0->2,1->0,2->3,3->1} + REAL sign flips on 3 fields**. Physics: dP_1 has a UNIQUE
   toric phase, so dualizing the rank-preserving node 0 is a self-duality. So the
   COMMITTED dp1 (0,1) "depth-2" positive has a trivial first step (T0~T1) and is really
   mutation-distance-1. The old signed `iso_signature` guard missed it (T0,T1 differ in
   sign -> different signature). The C* solve and a 4th-root brute force agree.
2. Of all depth-2 positives, ONLY dp1 (0,1) is trivial; dp0/f0/spp/dp2 are genuine
   (no node-relabel+phase iso among their states, checked to 4th roots). And dp1 HAS
   genuine depth-2 sequences (2,0) and (3,1) (start with a rank-CHANGING node that leaves
   the toric phase).

IMPLEMENTED (user approved fixing it): `theories_isomorphic` = `_iso_prefilter` (sign-
INVARIANT) + rank-preserving node perms + parallel-arrow/singlet bijections + W MONOMIAL-
SUPPORT match (coeffs ignored), cap-exceeded -> True. `ChainConfig.reject_isomorphic_
states=True` (non-default-serialized). Wired into `generate_mutation_chain` (depth>=2,
candidate-vs-every-earlier-state, attrition `trivial_isomorphic_state`) AND replacing the
signed-signature pairwise check in generation `_attempt_consistent_chain`.

RESULT: dp1's generated depth-2 positive is now the GENUINE (2,0); dp0/f0/spp/dp2 depth-2
unchanged; depth-1 byte-identical (guard gated depth>=2); the 4 stub composition tests
disable the guard (stub states encode identity in r_charge, which the iso notion ignores).
496 fast tests pass. New tests: `theories_isomorphic` contract (relabel/sign-flip iso ->
True, distinct -> False), and `dp1_node0_self_dual_is_rejected_as_trivial`.

Please review the ACTUAL code: `theories_isomorphic` / `_iso_prefilter` / `_w_support` in
chains.py, the guard insertion in `generate_mutation_chain`, and the replacement in
generation `_attempt_consistent_chain`. Questions: (a) is the guard faithful + free of a
correctness bug (esp. the cap fail-closed and the prefilter being sign-invariant-necessary)?
(b) is gating depth>=2 + per-step pairwise sound for G2 and equivalent to all-pairs? (c) any
way the now-admitted dp1 (2,0) or the unchanged dp0/f0/spp/dp2 positives are still trivial?
End with the single point most likely to be wrong.

### Round 3 — Codex

I will keep the scope guards in force: G1 fail closed because admitting a trivial
isomorph is poison, G2 depth-1 must remain byte-for-byte identical, G3 the intended
equivalence here is node relabeling plus diagonal `C*` field redefinition with
`+/-1` coefficients, and G4 the verifier must not be weakened.

(a) Faithfulness/correctness. `theories_isomorphic`, `_iso_prefilter`, and
`_w_support` implement the converged fail-closed monomial-support guard for the
diagonal `C*` notion. `_iso_prefilter` is sign-invariant and necessary: sorted
ranks, arrow count, singlet count, W-term count, `(length, |coeff|)` multiset, and
edge-counts by endpoint ranks cannot change under rank-preserving node relabeling,
field/singlet bijection, or diagonal rescaling. Returning False when this prefilter
differs is safe under G3. `_w_support` compares cyclic-canonical factor tuples with
coefficients ignored, so any diagonal `C*` isomorphism is caught once the right
node/field bijection is tried. Cap exceeded -> True is correctly fail-closed.

I do see one faithfulness/config bug: `generate_mutation_chain` honors
`cfg.reject_isomorphic_states`, but `_attempt_consistent_chain` in `generation.py`
applies `theories_isomorphic` unconditionally. With the default `True` this is the
desired G1 behavior, and it is not a poison risk. But if the flag is meant to be a
real kill switch wired into both paths, the consistent-R check should be guarded by
`if config.chain.reject_isomorphic_states and any(...)`. As written, setting the
flag False disables the standard-path guard but not the fallback guard.

(b) Depth gating/pairwise soundness. The standard path gates on requested
`depth >= 2`, which is right for G2: depth-1 calls do not run the new guard, while
depth-2+ rejects a trivial first step such as `T0 ~ T1`. Candidate-vs-every-earlier
checking is equivalent to all-pairs for the standard path because the accepted
prefix has already been checked; only pairs involving the new candidate are new.
The consistent-R fallback uses an all-pairs check over `cc.theories`, which is also
sound. The check happens before verifier calls, but that only saves work; it does
not weaken verification of admitted chains.

(c) Remaining admitted trivial? Under the narrowed G3 equivalence
node-relabeling + diagonal `C*` monomial field redefinition, I do not see a route
for an admitted depth-2 chain to still be trivial: relabeled returns, sign-flip
returns, phase-rescaling returns, and non-adjacent periodic subloops all have a
support-matching node/field bijection and are rejected. Same-support but
coefficient-distinct genuine phases are over-rejected, which is G1-safe yield loss.

The remaining caveat is outside the narrowed G3 but should stay documented: a full
non-diagonal GL change of parallel fields or singlets can change monomial support.
This implementation will not catch such an isomorphism unless it also happens to
have a support match. If full GL field redefinition comes back into scope, this is
a possible false negative, not just over-rejection.

Single point most likely to be wrong: the unconditional `theories_isomorphic` check
in `_attempt_consistent_chain` may violate the intended `reject_isomorphic_states`
configuration contract, even though the default fail-closed behavior is physically
the right one for the benchmark moat.

### Round 4 — Claude (converged; folded)

Accepted the config-faithfulness bug: `_attempt_consistent_chain` now gates on
`config.chain.reject_isomorphic_states` too, so the flag is a real kill switch on BOTH
paths (default True = the G1 behavior, unchanged). Everything else confirmed faithful:
sign-invariant necessary prefilter, coefficient-ignoring support match (catches every
diagonal-C* isomorph incl. sign/phase-flip self-dualities), cap-exceeded -> True
fail-closed, depth>=2 gating sound for G2, candidate-vs-earlier == all-pairs. The
non-diagonal GL caveat stays documented in the `theories_isomorphic` docstring (G1-safe
for the deterministic engine, which emits only diagonal/permutation-related returns).
CONVERGED. 496 fast tests pass; re-verifying the gating fix.
