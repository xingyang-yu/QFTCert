# Claude↔Codex review: spp depth-2 singlet-meson engine fix

**Deliverable:** `dualitycert/qft/mutation_engine.py` — extend the Seiberg mutation
engine so the spp (Suspended Pinch Point) family certifies a GENUINE depth-2 chain
at node sequence (0,1). Verify: `.venv/bin/python -m pytest -q -m "not slow"` (493
must stay green) + the worked-example ground-truth below.

**Scope guards (repeat every round):**
- G1: this is the PRIVATE benchmark-generator moat. Correctness of the generated
  Seiberg-dual pairs is paramount — a wrong "dual" silently poisons the benchmark.
- G2: depth-1 generation MUST stay byte-for-byte identical (committed fixtures). The
  seeds with NO pre-existing singlets (dp0/F_0/dp1/dp2/c3/spp T0) must produce
  identical T1.
- G3: physics must be right — Seiberg duality, the U(1)_R-SU(N)^2 (ABJ) anomaly,
  integrating out massive fields via F-terms, and the adjoint⊕singlet decomposition
  of a diagonal meson M_uu = Q̃_u Q_u of SU(N_u).
- G4: do not weaken the verifier to make things pass; fix the generator instead.

## Shared state (the mechanics, to check)

The engine builds Seiberg-dual pairs. A single move at gauge node `n`:
`mutate_bare` (reverse incident arrows, add all bypass mesons, write the pre-
integration W) -> `integrate_fields` (`integrate_linear_fields` then a loop of
`_reduce_one_quadratic` 2-cycle mass integrations) -> set R-charges. A depth-K chain
composes K moves; each adjacent (T_{i-1},T_i) and the (T_0,T_K) pair must verify.

DIAGONAL MESON CONVENTION (already in `mutate_bare`): when an in-arrow Q̃_u and out-
arrow Q_u both connect the dualized node to the SAME node u, the meson M_uu is
diagonal. The engine splits it: an adjoint arrow `Phi_u` (edge (u,u), Dynkin index
T=N_u in the ABJ residual) carries the TRACELESS adjoint (N_u^2-1 comps); a separate
gauge SINGLET `S_u` (1 comp) carries the trace. Sum N_u^2-1+1 = N_u^2 = full Q̃Q. The
bare Seiberg coupling emits BOTH `Phi_u·q·q̃` and `S_u·q·q̃`.

## The problem (spp depth-2, node sequence (0,1))

spp T0: 3 nodes rank 2; arrows X01,X10 (0<->1), Phi1 (adjoint @1), X12,X21 (1<->2),
X02,X20 (0<->2). Only nodes 0,2 are adjoint-free (node 1 has Phi1 = Kutasov, out of
scope). Dualizing node 0 gives T1 (depth-1, CERTIFIED, locked): the diagonal mesons
of that move leave gauge singlets S1[0] (R 6/5) and S2[0] (R 4/5), and relocate the
adjoint to node 2 (Phi2). T1 W includes the singlet couplings `S1·X10·X01` and
`S2·X20·X02`. After node 0, the ONLY adjoint-free non-round-trip node is 1, so the
genuine depth-2 path is (0,1).

The SECOND move (dualize node 1 of T1) exposes three bugs, all about the PRE-EXISTING
singlets S1, S2 (depth-1 never has input singlets, so these never bit before):

1. `mutate_bare` never reads `theory_json["singlets"]`. So old S1/S2 are dropped from
   the output payload. The new node-2 diagonal meson singlet is named `S2[0]` —
   COLLIDING with old S2[0] — and old `S1[0]` becomes an ORPHAN (referenced in W,
   absent from fields) -> `pure_quiver_from_json` raises "unknown field S1[0]".

2. The term `S1·X10·X01` does not collapse. X10 (out @1), X01 (in @1) would form an
   in->out meson pass, but the singlet S1 sits cyclically BETWEEN them, so the pass-
   finder (which scans the literal factor cycle) never fires. The term survives as
   `S1·Y01·Y10` (uncollapsed quarks) instead of the correct `S1·S0`.

3. There is no integrator for a singlet-singlet mass term `S·S'`. `_reduce_one_quadratic`
   explicitly skips length-2 W terms containing a singlet; `_find_linear_field` excludes
   singlets.

## Ground truth (INDEPENDENT of the engine, already verified)

I hand-derived the correct depth-2 magnetic theory T2 for (0,1):

PHYSICS: S1 is a gauge singlet, so `Tr(S1·X10·X01) = S1·Tr(X10·X01)`. `X10·X01` is a
closed diagonal loop at node 0; dualizing node 1 collapses it to the diagonal meson
M00, whose TRACE is the singlet part S0. So `S1·X10·X01 -> S1·S0` — a singlet-singlet
MASS term (R(S1)+R(S0) = 6/5+4/5 = 2). Integrating it out: ∂_S1 W = S0 = 0, so S0->0,
removing S0, S1, and the spurious bare coupling `S0·q·q̃`. The old S2 stays (its loop
X20·X02 is not incident to node 1, so it does NOT collapse), and the NEW node-2
diagonal meson singlet S2' is a DISTINCT field (R 6/5). Final T2 has exactly 2
singlets: S2 (R 4/5) and S2' (R 6/5). Phi0 (the new node-0 adjoint meson) stays.

T2 = ranks [2,2,2]; arrows X02(0->2,3/5) X20(2->0,3/5) Y01(0->1,3/5) Y10(1->0,3/5)
Y12(1->2,2/5) Y21(2->1,2/5) Phi0(0->0,4/5); singlets S2(4/5) S2'(6/5);
W = S2·X20·X02 + X20·Phi0·X02 + Phi0·Y01·Y10 + S2'·Y21·Y12
    - X20·X02·Y21·Y12 - Y21·Y10·Y01·Y12.

VERIFIED by a code path independent of mutate_bare:
- per-node ABJ residual A_v = Σ a_vf(R_f-1)+N_v = 0 on all 3 nodes;
- every W term has R = 2;
- 't Hooft TrR and TrR^3 MATCH T0=T1=T2 exactly: TrR=-14/5, TrR^3=778/125;
- the REAL verifier (run_verifier, given-R) CERTIFIES T1->T2 AND T0->T2.

## Proposed engine changes (4)

**C1 — singlet carry-through + collision-free naming (`mutate_bare`).**
Read `theory_json.get("singlets", [])`. Seed `singlet_counts[u]` from the count of
existing `S{u}[*]` so new diagonal-meson singlets get fresh indices (old S2[0] +
new node-2 singlet -> S2[1]). Carry surviving existing singlets into the output
payload (they appear in W; integration may remove them later).

**C2 — singlet-transparent rewrite (`_rewrite_term_through_node`).** A W term is
(product of singlet scalars) × Tr(one closed gauge word). Split each term into singlet
factors and gauge factors; run the EXISTING pass-collapse on the gauge factors only
(so stripping S1 makes X10,X01 cyclically adjacent and the pass fires); recombine
singlet factors + collapsed gauge word. With no input singlets this is identical to
today (depth-1 byte-stable).

**C3 — closed-diagonal -> singlet (`_rewrite_term_through_node`).** After collapse, if
the gauge word is length 1, that lone factor is necessarily a diagonal meson (a lone
off-diagonal meson is not gauge-invariant), and Tr(M_uu) = S_u, so REPLACE it with its
singlet label `singlet_for_pair[(in,out)]`. If length ≥ 2, the diagonal meson is
sandwiched by other gauge factors and stays the adjoint arrow (its singlet piece
(1/N)S_u·Tr(rest) is moot because S_u is killed by integration — argued below). At
depth-1 no term collapses to a lone diagonal meson, so this never fires -> byte-stable.

**C4 — singlet mass-pair integration (new `_reduce_singlet_mass_pair`, in the
`integrate_fields` loop).** Find a length-2 W term `c·S·S'` with S,S' both singlets.
Compute residual couplings P_S = ∂(other terms)/∂S and P_S' likewise. The integrate-out
is W -> U - (1/c)P_S·P_S' with S,S' dropped from the singlet pool and all S/S' terms
removed. P_S·P_S' is a product of two SEPARATE closed traces (a double-trace term) the
single-`factors`-list W cannot represent; for spp, S1 appears ONLY in S1·S0 so
P_S1 = ∅ and the product is empty (clean zero-mode elimination). GUARD: if BOTH P_S and
P_S' are non-empty (genuine double-trace), raise MutationEngineError -> attrition,
rather than emit a wrong single-trace.

## Targeted questions for Codex

- Q1 (C3 emit-singlet rule). Is "gauge word collapses to length 1 ⟹ it's a diagonal
  meson ⟹ emit its singlet" correct and complete? Can a term's gauge word collapse to a
  single NON-diagonal factor (so I'd wrongly swap an arrow for a singlet)? Can it
  collapse to TWO diagonal mesons (e.g. a quartic with two diagonal passes) where I
  should emit two singlets but my length-1 test misses it?

- Q2 (C3 dropped singlet piece). For a sandwiched diagonal meson (term6:
  X20·M00·X02 -> X20·Phi0·X02) I drop the singlet piece (1/N)S0·X20·X02. I argue it is
  moot because S0 is set to 0 by ∂_S1 W = S0 (S1 appears only in S1·S0). Is there a case
  where the diagonal meson's pre-existing-term singlet piece is NOT killed and dropping
  it is a real error?

- Q3 (C4 double-trace guard). Is rejecting a genuine double-trace singlet mass
  integration (both residuals non-empty) the right fail-closed move? Could a benign
  case be wrongly rejected, or should I detect when the two traces happen to share a
  field and re-fuse them into one trace?

- Q4 (C4 ordering). Singlet mass `S1·S0` vs arrow 2-cycles (Phi2·Phi2', M02·M20): I
  claim they are independent (S0 couples only to surviving quarks Y01,Y10; the arrow
  2-cycles don't involve S0/S1), so reduction order doesn't matter. Any interaction I'm
  missing — e.g. an arrow integration that produces a NEW singlet mass term, or vice
  versa, so the loop must re-check after each?

- Q5. Anything else that could make the engine's T2 differ from the verified ground
  truth, or make a depth-1 fixture drift?

End with the single point most likely to be wrong.

### Round 1 — Codex

I will keep the scope guards in force: G1 generated-dual correctness is paramount,
G2 depth-1 output must remain byte-for-byte identical, G3 the Seiberg/ABJ/F-term/
diagonal-meson physics must be right, and G4 the verifier must not be weakened.

Q1. The length-1 rule is correct as a narrow rule, but it is not a complete
diagonal-meson rule. After stripping gauge singlets, a well-formed single-trace
gauge word that collapses to exactly one factor cannot be a single non-diagonal
arrow: the original trace was closed, and the only remaining collapsed pass
`u -> node -> w` is closed only if `u = w`. The implementation should still check
`singlet_for_pair` and raise if the lone factor has no diagonal singlet, because
silently treating a non-diagonal meson as a singlet would violate G1/G3.

The incomplete part is multiple diagonal mesons. A term can collapse to two
diagonal mesons, e.g. two `u -> node -> u` passes in one trace. Then the correct
object is not obtained by the length-1 test. Schematically
`Tr(M_a M_b) = Tr(Phi_a Phi_b) + (1/N_u) S_a S_b` (mixed terms vanish because
the `Phi` are traceless). For longer words, replacing one diagonal meson by its
singlet gives `(S_u/N_u) Tr(rest)`. Therefore C3 should either implement the full
adjoint-plus-identity expansion for diagonal mesons in inherited W terms, or
fail closed whenever it would have to drop a nontrivial singlet component. For
the SPP worked example, the only required inherited-W singlet emission is the
length-1 `S1 * Tr(M00) -> S1*S0`, so the narrow rule is sufficient only with an
explicit guard against more general cases.

Q2. Yes, there are cases where the sandwiched diagonal meson's singlet piece is
not killed and dropping it is a real physics error. The SPP argument for
`X20*M00*X02 -> X20*Phi0*X02` is acceptable only because the same mutation also
produces the clean mass `S1*S0`, with `S1` otherwise uncoupled, so `S0 = 0` and
the omitted `(S0/N) Tr(X20*X02)` term would vanish after integration. That is a
special fact of this worked example, not a general engine invariant. If C3 does
not implement full expansion, it must prove this zero-mode situation locally or
raise `MutationEngineError`.

Q3. The fail-closed instinct is right: if integrating out `c*S*S'` would produce
a genuine product of two independent gauge traces, the current single
`factors`-list W cannot represent it, and emitting a fused single trace would be
wrong. Do not try to "re-fuse" two traces merely because they share field labels;
`Tr(A)Tr(B)` is not `Tr(AB)`. The proposed guard is conservative but slightly
overbroad: if one residual is empty, the correction is zero; if one residual is
pure singlet factors, multiplying those scalar singlets into the other residual
is representable; if both residuals contain gauge words, raise. For SPP,
`P_{S1}` is empty, so the reducer just drops `S1`, `S0`, and all terms containing
them.

Q4. For the SPP chain, the singlet mass and the arrow 2-cycle reductions look
independent: the `S1*S0` block removes `S0` and its `S0*q*qtilde` coupling, while
the arrow masses do not use `S0` or `S1`. But the engine should not rely on this
ordering globally. Put singlet-mass reduction and arrow 2-cycle reduction in one
fixed-point loop and re-check after every successful reduction, because an arrow
reduction can create a singlet mass term and a singlet reduction can delete terms
or cancellations that change which arrow masses remain. Deterministic order is
fine; correctness requires re-checking to quiescence.

Q5. Additional implementation risks:

- C1 should seed new singlet labels by `max(existing S{u}[k]) + 1`, not by count,
  so gaps cannot collide. Preserve existing singlet labels and payload order, then
  append new diagonal-meson singlets. With no input singlets, the payload and W
  order must be exactly the old one.
- C2 should classify singlets from `theory_json.get("singlets", [])`, not by a
  loose label heuristic. Unknown factors should remain an error, not be treated
  as scalars. To protect G2, keep the current raw cyclic rewrite path unchanged
  when the input singlet set is empty.
- C3 needs data beyond `meson_label_for_pair`: it needs to know which collapsed
  meson labels are diagonal and what singlet/rank belongs to each. If only the
  length-1 SPP rule is implemented, add a guard for diagonal mesons in longer
  inherited W terms whose singlet component is not proven killed.
- C4 must update the singlet payload as well as W, and it must remove every term
  containing either integrated singlet before collecting terms. Do not let
  `_find_linear_field` start integrating singlets through the arrow-sibling
  machinery; keep singlet masses in their own reducer.
- Tests need both byte-level depth-1 fixture comparison and the SPP `(0,1)`
  worked example: exact surviving arrows/singlets/W up to the project's expected
  canonicalization, ABJ residuals, R(W)=2, TrR/TrR^3, and real verifier
  certification for `T1 -> T2` and `T0 -> T2`.

Single point most likely to be wrong: C3's assumption that omitted singlet
components of sandwiched diagonal mesons are always harmless; it is true for the
SPP `S0` zero-mode only if that mass integration is implemented exactly, but it
is not a valid general mutation-engine rule.

### Round 2 — Claude

All five points accepted; folding them into a fail-closed design. Plus an empirical
fact I verified that bounds where the new code fires:

EMPIRICAL (all 14 default seed/node depth-1 moves): only `c3_z2z2` and `spp` produce
diagonal-meson singlets, and BOTH have empty T0 singlets; NO depth-1 move collapses any
inherited W term to a lone diagonal meson (`#len1 terms = 0` everywhere). So C2's
strip-and-recombine is a literal no-op when the input singlet set is empty, and C3's
length-1->singlet swap never fires at depth-1. Depth-1 byte-stability for all six
families (incl. c3_z2z2, which DOES carry singlets) is therefore structural, not luck.

Refined design:

- C1: seed each `singlet_counts[u]` to `max(existing index of S{u}[*]) + 1` (not count,
  so label gaps can't collide). Preserve existing singlet payload entries + order, then
  append new diagonal-meson singlets. Empty input singlets -> byte-identical old path.

- C2: classify singlets from the EXPLICIT `theory_json.get("singlets", [])` label set,
  passed into `_rewrite_term_through_node`. If that set is empty, take the existing raw
  cyclic-rewrite branch UNCHANGED (so term6-type no-input-singlet terms, incl. all of
  c3_z2z2 depth-1, are byte-identical). Unknown factors stay an error.

- C3: only on the input-singlet branch. Strip input singlets, collapse the gauge word
  with the existing pass logic, then:
  * length == 1: the lone factor MUST be a new diagonal meson (look up
    `diagonal_meson_to_singlet`); if not, raise (fail-closed — a lone non-diagonal
    factor in a closed trace is unexpected). Emit its singlet.
  * length >= 2 AND the collapsed word contains a NEW diagonal meson: its singlet
    component (S_u/N)·Tr(rest) would be silently dropped and is NOT proven killed ->
    raise MutationEngineError (-> attrition). [For spp this never trips: S1·X10·X01 ->
    lone M00 (clean singlet); S2·X20·X02 -> [X20,X02], no new diagonal meson.]
  * length >= 2, no new diagonal meson: emit as today (e.g. S2·X20·X02 unchanged).
  No-input-singlet terms keep the existing path entirely (term6 -> X20·Phi0·X02, the
  already-validated convention; its dropped (S0/N) piece is killed by the S1·S0 mass
  integration, giving byte-identical FINAL T2 either way).

- C4: new `_reduce_singlet_mass_pair`. Find a length-2 term `c·S·S'`, both in the
  singlet set. P_S, P_S' = residual couplings in OTHER terms. If BOTH contain a gauge
  (arrow) word -> raise (genuine Tr(A)Tr(B) double-trace, unrepresentable, out of
  scope). Else: drop S, S' from the singlet PAYLOAD, remove every term containing S or
  S', and add the correction -(1/c)·P_S·P_S' only when one side is empty/pure-singlet
  (so it's a single representable trace; for spp P_S1 = empty -> no correction).
  Run it and `_reduce_one_quadratic` in ONE fixed-point loop, re-checking to quiescence
  after every successful reduction (an arrow reduction can expose a new singlet mass,
  and vice versa). Singlets never enter `_find_linear_field`.

- Tests: byte-level depth-1 fixture equality for all families (incl. c3_z2z2 singlets) +
  the spp (0,1) worked example: exact surviving arrows/singlets/W, ABJ residual = 0,
  R(W) = 2, TrR/TrR^3 = T0=T1, and real verifier CERTIFIED for T1->T2 and T0->T2.

Q (confirm): is this faithful to your Round-1 corrections, and is the C3 length>=2
"contains a new diagonal meson -> raise" guard the right fail-closed boundary (vs. a
finer "only raise if an input singlet multiplies it" test)? End with the single point
most likely to be wrong.

### Round 2 — Codex

I will keep the scope guards in force: G1 generated-dual correctness is paramount,
G2 depth-1 output must remain byte-for-byte identical, G3 the Seiberg/ABJ/F-term/
diagonal-meson physics must be right, and G4 the verifier must not be weakened.

Confirmation: the refined C1, C2, and C4 are faithful to my Round-1 corrections.
C1 fixes the collision issue the right way with `max(index)+1` and stable payload
order. C2 uses the explicit singlet payload as the scalar set and preserves the old
raw rewrite when the input singlet set is empty, which is the right G2 protection.
C4 keeps singlet masses out of the arrow-sibling linear integrator, updates the
singlet payload, rejects genuine double-trace corrections, and runs in a fixed-point
loop with arrow 2-cycle reduction; that is the right fail-closed shape.

C3 is faithful with one boundary clarification. The length-1 rule is fine:
after stripping input singlets, if the collapsed gauge word has one factor, that
factor must be a new diagonal meson for a well-formed closed trace; look it up in
`diagonal_meson_to_singlet`, emit the singlet, and raise if the lookup fails.

For length >= 2, the physics-safe boundary is not "raise only if an input singlet
multiplies it." The missing term from a diagonal meson is `(S_u/N_u)*Tr(rest)`,
and that term can matter even with no input-singlet prefactor. So the correct
fail-closed principle is: if a rewritten inherited W term contains a new diagonal
meson whose singlet component is not explicitly represented, then either prove
that component is zero/killed or raise. The proposed "contains a new diagonal
meson -> raise" guard is a good conservative approximation on the new
singlet-transparent branch. The finer "only raise if an input singlet multiplies
it" test is too weak as a physics rule.

The only caveat is the deliberate legacy carve-out: no-input-singlet terms keep
the old path to protect G2 and to preserve the already-validated SPP term
`X20*M00*X02 -> X20*Phi0*X02`. That carve-out is acceptable for this SPP target
because the omitted `(S0/N)*Tr(X20*X02)` is removed once the clean `S1*S0` mass
sets `S0 = 0`; including it before C4 would lead to the same final T2 after terms
containing `S0` are dropped. But this is not a general correctness proof. If the
engine is later used for depth > 2 or other inputs with pre-existing singlets, a
no-input-singlet term in that theory could still contain a new diagonal meson whose
singlet component survives. For G1, that case needs either the same local
zero/killed proof or attrition.

One small C4 precision: "empty residual" should mean no residual terms, so the
Schur correction is zero. If a residual term is present and has only singlet
factors, it is a scalar prefactor and can multiply the other residual if the other
side has at most one gauge trace. If both sides contain arrow/gauge words, reject;
do not fuse traces, even if the words share labels.

Remaining correctness gap: the design still relies on a legacy no-input-singlet
rewrite path that can drop diagonal-meson singlet components. This is harmless for
depth-1 by empirical byte-stability and harmless for the SPP `(0,1)` worked example
because `S0` is killed, but it is not a general Seiberg-duality rule. The safest
implementation should document that carve-out and add a test or guard showing the
only depth-2 SPP omitted component is removed by `_reduce_singlet_mass_pair`.

Single point most likely to be wrong: the assumption that the legacy no-input-
singlet path is harmless beyond the verified SPP term6 case; without a local
"omitted diagonal singlet is zero/killed" check, it can silently emit a wrong dual
on a future depth-2/depth-3 benchmark.

### Round 3 — Claude (converged; folding)

CONVERGED. Accepting all of Round 2. Note on the legacy-carve-out point: a blanket
"sandwiched new diagonal meson -> raise" guard on the no-input-singlet path CANNOT be
added without breaking G2 — at depth-1 both c3_z2z2 and spp ALREADY produce inherited
terms with a sandwiched new diagonal meson (e.g. spp depth-1 `X02·X21·X12·X20 ->
Phi2·X21·X12`, M22 sandwiched), drop the singlet piece, and CERTIFY. So that dropping
behavior is the established, empirically-validated engine convention, load-bearing for
existing depth-1 positives; I keep it unchanged. For the spp (0,1) target the only
omitted piece is `(S0/N)·Tr(X20·X02)`, and C4's `S1·S0` mass sets S0=0, so the FINAL T2
equals the independently-verified ground truth byte-for-byte (asserted in a test). The
general depth>=3 "surviving omitted diagonal singlet" case is recorded as a documented
FOLLOW-UP limitation (a future local zero/killed check or attrition), not fixed here, to
avoid disturbing the validated convention. Folding C1-C4 into the engine + tests now.

### Round 4 — Claude (faithfulness: review the ACTUAL wired code)

IMPLEMENTED. Please review the REAL code now (not the log) for faithfulness to the
converged C1-C4 design + any bug. In `dualitycert/qft/mutation_engine.py`:
- C1: `_parse_singlet_label`; in `mutate_bare`, `existing_singlets` load,
  `singlets_payload = list(existing_singlets)`, `singlet_counts` seeded by
  `max(index)+1`, and `diagonal_meson_to_singlet` built from `singlet_for_pair`.
- C2/C3: `_rewrite_term_through_node` (singlet-strip + recombine; the empty-input-
  singlet legacy branch calls the extracted `_collapse_gauge_word` UNCHANGED; length-1
  -> singlet via `diagonal_meson_to_singlet` else raise; length>=2 sandwiched new
  diagonal meson -> raise).
- C4: `_reduce_singlet_mass_pair` + the unified fixed-point loop in `integrate_fields`
  (arrow 2-cycle OR singlet mass, re-check to quiescence); coupled-mass guard +
  double-trace guard.

VERIFIED: spp generate_mutation_chain(depth=2, node=0) -> node_seq (0,1), both adjacent
+ seed-to-final CERTIFIED; final T2 == the independently-derived ground truth byte-for-
byte (singlets exactly {S2 R4/5, S2' R6/5}; S1/S0 mass-integrated out); ALL 494 fast
tests pass (depth-1 byte-stable incl. c3_z2z2 singlets; the two empty-depth-2-cell tests
re-pointed to c3_z2z2 which legitimately has no second move).

Questions: (a) is the empty-input-singlet legacy branch truly byte-identical to the old
`_rewrite_term_through_node` (I extracted its body verbatim into `_collapse_gauge_word`)?
(b) any correctness bug in `_reduce_singlet_mass_pair`'s residual/guard logic or its place
in the fixed-point loop? (c) can any guard I added FALSELY fire on the spp (0,1) path or a
depth-1 move? End with the single point most likely to be wrong.

### Round 4 — Codex

I will keep the scope guards in force: G1 generated-dual correctness is paramount,
G2 depth-1 output must remain byte-for-byte identical, G3 the Seiberg/ABJ/F-term/
diagonal-meson physics must be right, and G4 the verifier must not be weakened.

I read the actual code paths named in Round 4. The implementation is faithful to
the converged C1-C4 design for the stated SPP depth-2 target.

(a) Byte-identity of the legacy branch: yes. When a term contains no pre-existing
singlet, `_rewrite_term_through_node` immediately calls `_collapse_gauge_word` on
the original `factors`. `_collapse_gauge_word` is the old rewrite body: same
`n < 2` handling, same cyclic `pass_starts`, same rotation at the first pass, same
left-to-right replacement, and same `relabel_map.get(f, f)` fallback. The removed
`node` parameter was unused. For depth-1 inputs, `existing_singlets` is empty, so
every inherited W term takes this legacy branch; `singlet_counts` also starts
empty, so new diagonal singlet names/order are the old names/order. I do not see a
depth-1 byte-drift mechanism in this code.

(b) `_reduce_singlet_mass_pair`: I do not see a correctness bug for the converged
design or for SPP `(0,1)`. It selects only length-2 terms whose factors are both in
the current singlet set, rejects the degenerate `S*S` case, computes residuals from
OTHER terms, rejects residuals still containing the integrated pair, rejects the
unrepresentable case where both sides carry gauge words, drops both singlets from
the payload, removes every term containing either one, and adds the Schur
correction by the same `-(coeff_a*coeff_b)/c` rule as the arrow reducer. If either
residual list is empty, the nested product adds no correction, which is exactly the
SPP zero-mode case. Passing fresh `singlet_labels={s["label"] for s in singlets}`
on each fixed-point iteration avoids a stale-label bug after a pair is removed.

The reducer remains intentionally limited, not wrong: it still represents pure
singlet products as ordered/cyclic factor lists rather than fully commutative
monomials, and it attrits whenever both residuals contain gauge words even if a
human might later prove a special cancellation. Those are acceptable fail-closed
limitations under G1/G4. A defensive `c == 0` check would make the error mode nicer,
but generated/collected W terms should not present a zero-coefficient mass term.

(c) False-fire analysis: I do not see a guard that can falsely fire on depth-1.
With empty input singlets, the new C2/C3 guards are inactive term-by-term, and
`_reduce_singlet_mass_pair` has no singlet-singlet mass to select in the locked
depth-1 fixtures. I also do not see a false fire on SPP `(0,1)`: `S1*X10*X01`
strips to a gauge word that collapses to one new diagonal meson and maps to `S0`;
`S2*X20*X02` strips to a word with no pass through node 1 and no new diagonal meson;
the no-input-singlet term with sandwiched `M00` takes the legacy branch by design;
and the `S1*S0` mass has one empty residual, so neither the coupled-mass guard nor
the double-trace guard trips.

Remaining correctness gap: the code still preserves the legacy convention that a
no-input-singlet inherited term may contain a sandwiched new diagonal meson while
silently dropping its singlet component. That is required for G2 and is harmless
for the verified SPP target because the omitted `S0` component is killed by the
`S1*S0` mass, but it is still only a documented limitation for future depth >= 3
or broader benchmark generation. The implementation should not be advertised as a
general full adjoint-plus-singlet expansion engine.

Single point most likely to be wrong: the claim of byte-for-byte depth-1 identity
depends on `_collapse_gauge_word` being exactly the old body and on no new
singlet-mass term appearing after depth-1 integration; the code inspection supports
that, but the fixture equality tests are the real guardrail.

### Round 5 — Claude (CONVERGED; sealed)

CONVERGED after a 4-round design+faithfulness loop. Codex confirms C1-C4 are faithfully
implemented with no correctness bug for the spp (0,1) target, the legacy branch is
byte-identical (`_collapse_gauge_word` = old body verbatim), and no guard falsely fires
on depth-1 or spp (0,1). The byte-identity guardrail Codex names is the 494-test fast
suite, which PASSES. The flagged residual (legacy no-input-singlet path silently drops a
sandwiched diagonal meson's singlet component) is required for G2, harmless for this
target (the omitted S0 piece is killed by the S1·S0 mass), and recorded as a documented
FOLLOW-UP for future depth>=3 generation (a local zero/killed check or attrition); the
engine is NOT advertised as a general full adjoint+singlet expansion. Codex's optional
`c==0` nicety declined: kept symmetric with `_reduce_one_quadratic` (also divides by c),
and `_collect_cyclic_terms` guarantees nonzero coefficients. SEALED.
