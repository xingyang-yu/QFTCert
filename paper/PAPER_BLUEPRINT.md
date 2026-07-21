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

**MiniMax's role in the ladder:** the preregistered MiniMax-M2.5 extension family
(complete, own Holm adjustment — see §3) supplies *separately adjusted supporting
evidence beneath rungs 2 and 3*. It is NOT a fourth rung, never enters the two-model
primary family, and is never pooled into a three-model multiplicity family.

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
- **Extension — MiniMax-M2.5 (amendment 1, COMPLETE; preregistered; own 3-hypothesis
  Holm family; frozen GEE at
  `runs/experiments/repair_d1/confirmatory_analysis/minimax_extension/confirmatory_analysis.json`):**

  | MiniMax endpoint | rd (p: Holm-adjusted for E1/E2/E4; unadjusted for E5) | 95% CI |
  |---|---|---|
  | E2 gr−ss | +11.5 pp (0.0002, sig) | [+5.9, +17.1] |
  | E4 portfolio−control | −9.0 pp (0.009, sig; reproduced the negative E4 ordering observed on DeepSeek) | [−15.2, −2.7] |
  | E1 vf−gr | +2.8 pp (0.26, ns) | [−2.0, +7.5] |
  | E5 vf−masked (secondary, unadjusted) | −0.7 pp (0.77, ns — no detected difference) | [−5.3, +3.9] |

  All five arms 145×3; E4 per-rep signs consistent (−11.0/−9.7/−6.2 pp). Caveat
  (goes in Limitations): provider-forced thinking; invalid rates higher than the two
  primary models (vf 45%, gr 38%). Reported alongside but SEPARATELY from the
  two-model primary family, per the amendment's preregistered claims language.

  **Contamination cleaning (appendix material; full transcript
  `minimax_data_audit.md`, artifacts `runs/experiments/repair_d1/
  quarantine_preclean_20260721/`):** 45 fixture-reps total (43 in the initial scan
  + 2 recurrences during reruns) contained exogenous API-transport errors
  (APIConnectionError/APITimeoutError) and were quarantined and replaced under the
  frozen filter-and-resume rule; selection was outcome-independent; deepseek/qwen
  contain 0 such rows. Two converged disclosure sentences for the appendix:
  (i) "All MiniMax contamination-cleaning reruns, including the third rerun of
  `spp_N2_d1_node2_rank_perturb_00`, retained the pre-data-recorded 300-second
  client timeout; rows containing exogenous transport timeouts were quarantined and
  replaced under the unchanged filter-and-resume rule." (ii) "For pass 3 and any
  subsequent contamination-cleaning reruns, requests to `dashscope.aliyuncs.com`
  bypassed the shell's local HTTP(S) proxy via `NO_PROXY`, while the frozen
  300-second client timeout, provider endpoint, model, prompts, fixtures, policies,
  and sampling parameters remained unchanged."
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
4. **Confirmatory results** (2.2–2.6 pp). Order: **E2 anchor → E4 reversal → E1/E5
   narrower feedback evidence → MiniMax extension unit → certificate-as-invariant
   synthesis.** ONE primary table + ONE policy/result figure — not parallel result
   threads. **MiniMax extension unit spec:** one short paragraph + a visually
   separated MiniMax block INSIDE the main results table (not a second table), placed
   AFTER the full two-model primary results, never interleaved. Block header must say
   "preregistered MiniMax-M2.5 extension; separate three-hypothesis Holm family"; the
   E5 row must be labeled "secondary, unadjusted". No pooled three-model family.
5. **Discussion and limitations** (0.7–0.9 pp). Two-model primary scope ⇒ existence/
   non-universality only, NO typology; what E4 does and does NOT identify (it bundles
   feedback content + sequential dependence + call-cap allocation); masked-feedback
   caveat; certificate-vs-proof limit; MiniMax Limitations sentence now addresses the
   provider-forced-thinking / invalid-rate caveat (NOT "descriptive-only" — that
   routing is obsolete).
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
the **literal E4 sentence below verbatim**; (5) E1 and E5 as narrower feedback-content
evidence; (5b) ONE separately signposted MiniMax sentence — the **literal MiniMax
sentence below verbatim** — placed after the E1/E5 sentence and before the
certificate/artifact close, with NO p-values and NO model counting; (6) the
certificate as the invariant + artifact availability. Keep QFTCert, depth-2, and any
typology OUT of the abstract. (If the final abstract runs too dense, the MiniMax
sentence is the FIRST item to cut; the main-text extension unit stays regardless.)

**MiniMax abstract sentence — use verbatim (converged wording):**
> Separately, a preregistered MiniMax-M2.5 extension again finds an iteration gain
> and independent verifier-filtered resampling outperforming the strategy portfolio.

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

**MiniMax rule (updated post-data, Round 3 converged):** MiniMax appears in exactly
four places — (i) the compact extension unit inside Results (spec in §4.4); (ii) the
single verbatim abstract sentence (§5); (iii) the Limitations forced-thinking /
invalid-rate caveat; (iv) the appendix (full extension analysis, per-rep rows,
invalidity decomposition). The words "Separately" and "extension" are load-bearing
wherever MiniMax is named next to the primary results.

**Additional forbidden phrasings (MiniMax-specific, converged Round 3):**
- "two out of three models prefer resampling"; "a majority of models favor
  resampling"; "resampling is the default/optimal policy";
- "the models divide into resampling-dominant and feedback-dominant regimes/types/
  classes"; "DeepSeek and MiniMax are sampler-type, whereas Qwen is a feedback-follower";
- "MiniMax confirms that the optimal strategy is model-dependent"; "three models
  establish model-dependence";
- "feedback does not help MiniMax"; "MiniMax is insensitive to feedback"; "resampling
  beats feedback on MiniMax" (E4 does not isolate feedback);
- "E5 has no effect / is null for MiniMax"; "masked and interpretable feedback are
  equivalent on MiniMax" (ns ≠ absence/equivalence);
- "the E5 interpretability premium is model-specific"; "only Qwen benefits from
  interpretable obligation identities";
- "third confirmatory model"; "the pooled three-model confirmatory family"; any
  unqualified "3/3" or "2-vs-1 majority" formulation.

**Allowed replacements (named-model language only):** "the E5 advantage was detected
on Qwen but not on DeepSeek or MiniMax"; "the separately preregistered MiniMax
extension reproduced the negative E4 ordering observed on DeepSeek".

## 7. Existing assets
- `paper/main.tex` — current abstract (REWRITE per §5) + `\todo` skeleton to fill.
- `paper/analysis_protocol.md` (+ `_amendment1.md`) — frozen protocol (cite, don't alter).
- `runs/experiments/repair_d1/confirmatory_analysis/confirmatory_analysis.json` — GEE source of truth for the two-model primary numbers.
- `runs/experiments/repair_d1/confirmatory_analysis/minimax_extension/confirmatory_analysis.json` — GEE source of truth for the MiniMax extension numbers.
- `runs/experiments/repair_d1/confirmatory_analysis/e4_minimax_r{1,2,3}/` — MiniMax E4 replay per rep.
- `paper/tables/*.tex` — artifact-generated tables (primary, per_rep, cost).
- `crossmodel_flip_discussion.md` — background on the finding (context, not for citation).

## 8. Open uncertainty flagged at convergence
(Round 3, post-data) Codex's residual doubt: the MiniMax abstract sentence may blur
the primary/extension boundary despite the explicit "Separately" qualifier. Agreed
mitigation: if the final abstract becomes too dense, that sentence is the first item
to remove, while the main-text extension unit remains. (The Round 1–2 doubt about
descriptive-only appendix placement is obsolete — the extension family is complete
and preregistered-analyzed.)
