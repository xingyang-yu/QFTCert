# DualityCert paper — architecture blueprint (for the writing model)

**Purpose.** This is the self-contained writing brief for the DualityCert workshop
paper. It is the converged output of a Claude↔Codex (GPT-5.6 Sol, xhigh) architecture
loop; the full transcript is `paper/arch_loop.md`. Write the prose from THIS file plus
the repo; you should not need the originating conversation.

**Venue.** NeurIPS AI4Science **workshop** + arXiv. Norms: content outweighs vision;
~4–9 pages main + appendix; one concrete, self-contained contribution.

**Red lines (non-negotiable).**
- DualityCert (the Seiberg-duality verifier) + the repair-loop findings must be a
  COMPLETE paper on their own. A reader who stops before the final paragraph must
  already have a finished paper. The QFTCert program is framing/outlook ONLY.
- Every number is frozen. You may change claim *ordering and scope*, never a value.
- Do not overclaim beyond the two confirmatory models (see §Claim-scope language).

---

## 1. Naming (use consistently)
- **DualityCert** — the implemented 4d N=1 Seiberg-duality verifier (matches code
  package `dualitycert`). Use this name in the **title, abstract, intro, system
  section, all figures/tables, and results**. This is the paper's subject.
- **QFTCert** — the umbrella program/vision (a "physics Lean4/Mathlib": domain experts
  verifier-ize their own areas). Appears **once**, in the final outlook paragraph, as
  the prospective program of which DualityCert is the first implemented cert. NOT in
  the abstract, contribution list, or results.

## 2. The three-rung claim ladder (the spine of the whole paper)
The abstract, intro contribution list, results ordering, and discussion must all use
this same ladder, in this order:

1. **Substrate.** DualityCert supplies cheap, machine-checkable *consistency
   certificates* (explicitly: certificates of consistency, NOT proofs of duality) and
   a verifier-gated repair environment for LLM agents.
2. **E2 anchor (robust, both models).** Verifier-gated iteration beats single-shot on
   both confirmatory models: **+8.3 pp deepseek-chat, +7.1 pp qwen-plus, Holm p<0.002**.
3. **E4 reversal (the central surprise).** Under an equal 11-call cap, the ordering of
   the two tested verifier-exploitation policies **reverses across the two models**
   (deepseek −10.3 pp, qwen +14.7 pp). E1 (**+8.7 pp qwen; −1.8 pp, ns, deepseek**) and
   E5 (**+6.4 pp qwen**) are *narrower supporting evidence* about feedback content, NOT
   a population-level typology.

The invariant across both regimes is the cheap machine-checkable certificate itself.

## 3. Frozen experimental facts (faithful; lift numbers from here)
- **Benchmark:** n=145 depth-1 verifier-gated *repairable* fixtures, byte-identical
  across models (seed 20260715). Perturbation classes: drop_w_term(38), flip_w_sign(13),
  r_charge_perturb(52), rank_perturb(42). Seed families: dP0, dP1, dP2, F0, SPP, C3/Z2×Z2.
- **DualityCert obligations:** ’t Hooft anomaly matching; superpotential R-charges;
  central charge a; bounded chiral-ring consistency. **Anti-gaming:** the final
  acceptance check is STRICTER than the feedback-time check (chiral-ring L=5 final vs
  L=3 at feedback). A "certificate" = passing all obligations; it certifies CONSISTENCY,
  not a proof of duality.
- **Arms:** single_shot_repair (ss); generic_retry (gr; K≤5; content-free "wrong, try
  again"); verifier_feedback (vf; category-level obligation feedback); vf_masked (E5
  control: structurally identical feedback with positional placeholders); best_of_n (E4
  control: 2K+1=11 independent draws, stop at first cert); E4 stop-first portfolio
  (ss→gr→vf under the same 11-call cap).
- **Analysis:** pre-registered, frozen before data. Primary = GEE (exchangeable working
  correlation), Holm across a 6-hypothesis family, R=3 reps/arm, n_obs/arm=435.
- **Confirmatory results (deepseek-chat + qwen-plus, complete) — exact GEE values:**

  | Endpoint | deepseek rd (Holm p) | qwen rd (Holm p) |
  |---|---|---|
  | E1 vf−gr | −1.8 pp (0.45, **ns**) | +8.7 pp (0.0016) |
  | E2 gr−ss | +8.3 pp (0.0015) | +7.1 pp (0.0016) |
  | E4 portfolio−control | −10.3 pp (0.0016) | +14.7 pp (<0.0001) |
  | E5 vf−masked | +0.0 pp (1.00, ns) | +6.4 pp (0.0065) |
  | E3 vf@1−gr@1 | +0.5 pp (0.81, ns) | +1.8 pp (0.23, ns) |

  Note the asymmetry that drives the framing: **E1 is significant on only one model**
  (qwen), so E1 alone is NOT a two-sided reversal. **E4 is the clean reversal** (both
  sides significant, opposite sign). E4 carries "opposite directions," not E1.
- **Extension — MiniMax-M2.5 (amendment 1, separate Holm family, DESCRIPTIVE ONLY):**
  E1 vf−gr = +3.2 pp (vf 26.0% / gr 22.8%); E2 gr−ss = +11.0 pp (ss 11.7%). No full GEE
  yet; best_of_n(E4) and vf_masked(E5) NOT run (deferred to v2). Invalid rate high
  (vf 46% / gr 39%), a forced-thinking artifact. Appendix + one Limitations sentence only.
- **Exploratory — depth-2 axis:** deepseek, single-rep; a difficulty dial on which all
  strategies collapse to the floor. Appendix. glm/gemini scout runs = provider noise, excluded.

## 4. Six-section main-text architecture (target 6–7.5 pp)
1. **Introduction + compact related work** (0.8–1.0 pp). Problem: LLMs doing physics
   derivations lack the ground-truth feedback math gets from proof assistants. Concrete
   gap → DualityCert. State the 3-rung contribution ladder. Fold related work in here
   (verifier-in-the-loop AI4Math: AlphaProof, LeanDojo lineage; symbolic-oracle methods;
   LLM+tools). Scope the existence claim to the two confirmatory models explicitly.
2. **DualityCert: certificates and repair interface** (1.2–1.5 pp). Concrete-to-general:
   (a) claim + certificate semantics ("consistency certificate, not proof of duality");
   (b) the four duality-specific obligation families + the L=3/L=5 anti-gaming split;
   (c) the repair interface / obligation-feedback contract the experiments exercise;
   (d) THEN a compact mapping table extracting reusable roles (claim schema, obligations,
   certificate, feedback projection, strict final judge). Call this a reusable **design
   pattern**, NOT a validated framework (no second implementation/conformance test exists).
3. **Benchmark and preregistered experiment** (1.1–1.3 pp). 145 fixtures, four
   perturbations, verifier-gating; the arms; E1/E2/E4/E5; GEE/Holm; frozen protocol;
   L=3/L=5 safeguard.
4. **Confirmatory results** (2.0–2.3 pp). Order: **E2 anchor → E4 reversal → E1/E5
   narrower feedback evidence → certificate-as-invariant synthesis.** ONE primary table
   + ONE policy/result figure — not five parallel result threads.
5. **Discussion and limitations** (0.7–0.9 pp). Two-model scope ⇒ existence/
   non-universality only, NO typology; what E4 does and does NOT identify (it bundles
   feedback content + sequential dependence + call-cap allocation); masked-feedback
   caveat; certificate-vs-proof limit; the single qualified MiniMax sentence (see §6 rules).
6. **Conclusion, artifact statement, and QFTCert outlook** (0.3–0.5 pp). Release +
   reproduction pointer FIRST; then ONE final paragraph introducing QFTCert as the
   prospective umbrella program (future certs: bootstrap, amplitudes, SUSY localization/
   resurgence, string field theory), with DualityCert as its first implemented instance.

**Appendix:** full obligation definitions + certificate schema; seed-family &
perturbation generation; full prompts/policy pseudocode; GEE specification; per-rep &
per-class tables; MiniMax subsection; depth-2; provider-noise exclusions; invalid-output
decomposition; full costs, manifests, hashes, exact commands.

## 5. Abstract spec (rewrite the current one)
The current abstract centers E1 as the flip and says "optimal verifier-exploitation
strategy is model-dependent" — both now disallowed. Rewrite to this architecture:
(1) DualityCert + certificate scope; (2) the 145-fixture preregistered experiment;
(3) E2 as the cross-model iteration anchor; (4) E4 as the tested-policy reversal, using
the **literal sentence below verbatim**; (5) E1 and E5 as narrower feedback-content
evidence; (6) the certificate as the invariant + artifact availability. Keep QFTCert,
MiniMax, depth-2, and any typology OUT of the abstract.

**E4 abstract sentence — use verbatim (converged wording):**
> Under an equal 11-call cap, the frozen strategy portfolio underperformed independent
> verifier-filtered resampling by 10.3 percentage points on deepseek-chat but
> outperformed it by 14.7 points on qwen-plus, reversing the ordering of the two tested
> verifier-exploitation policies across the two confirmatory models.

## 6. Claim-scope language (hard guardrails)
**Allowed:** "the best-performing tested policy differed between the two named models";
"non-universality across the two evaluated models"; "the ordering of the two tested
policies under the frozen 11-call budget reverses"; "consistency certificate".
**Forbidden:** "the optimal strategy is model-dependent"; "we characterize model-
dependence"; any sampler-vs-follower or model-class typology; "feedback content flips
sign" (E4 does NOT isolate feedback content — E1/E5 are the narrower feedback claims);
any population-level or "physics-general framework" claim; "proof of duality".

**MiniMax rule:** exactly ONE Limitations sentence carrying all three qualifiers
(descriptive-only, incomplete policy coverage, excluded from the confirmatory family),
using +3.2 pp with NO significance implication and NO model-class validation claim;
plus one appendix subsection. Nowhere else.

## 7. Existing assets
- `paper/main.tex` — current abstract (REWRITE per §5) + `\todo` skeleton to fill.
- `paper/analysis_protocol.md` (+ `_amendment1.md`) — frozen protocol (cite, don't alter).
- `runs/experiments/repair_d1/confirmatory_analysis/confirmatory_analysis.json` — GEE source of truth for every number.
- `paper/tables/*.tex` — artifact-generated tables (primary, per_rep, cost).
- `crossmodel_flip_discussion.md` — background on the finding (context, not for citation).

## 8. Open uncertainty flagged at convergence
Codex's residual doubt: even one MiniMax sentence in the main text may lend an
incomplete descriptive extension more evidentiary weight than intended; pure-appendix
placement would enforce the hierarchy more mechanically. Author's call. Current
decision: keep the single qualified Limitations sentence.
