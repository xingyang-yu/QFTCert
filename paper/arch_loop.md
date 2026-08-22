# DualityCert paper — architecture convergence loop (Claude↔Codex)

Deliverable being converged toward: `paper/PAPER_BLUEPRINT.md` — a self-contained,
section-by-section architecture blueprint that a SEPARATE model (GPT-5.6) will use to
write the actual prose. This log is the working transcript; rounds appended in order.

## SCOPE GUARDS (repeat every round)
1. We are designing the paper's ARCHITECTURE (section structure, framing decisions,
   what goes where, claim ladder), NOT writing prose.
2. Target venue: NeurIPS AI4Science **workshop** + arXiv. Workshop norms: content must
   outweigh vision; ~4–9 pages + appendix; a concrete, self-contained contribution.
3. RED LINE: the paper must stand on its own foundation. \textsc{DualityCert} (the
   Seiberg-duality verifier) + the repair-loop findings must be a complete paper even
   if a reader ignores the larger \textsc{QFTCert} vision entirely. The vision is
   framing + outlook, never a substitute for results.
4. Do NOT alter frozen experimental facts (protocol, GEE analysis, numbers). We only
   decide how to PRESENT them. Faithfulness to the numbers is mandatory.
5. Deliverable must be self-contained enough that GPT-5.6 can write from it without
   this conversation.

## STATE (verifiable on disk; Codex should read these)
- `paper/main.tex` — abstract (written) + body skeleton (all `\todo`).
- `paper/analysis_protocol.md` (+ `_amendment1.md`) — frozen pre-registered protocol.
- `runs/experiments/repair_d1/confirmatory_analysis/confirmatory_analysis.json` — GEE results.
- `crossmodel_flip_discussion.md` — prior Claude↔Codex log on the core finding.

### Naming (locked with the author 2026-07-20)
- **QFTCert** = the umbrella program / vision (a "physics Lean4/Mathlib": a shared
  framework where domain experts "verifier-ize" their own areas — bootstrap, amplitudes,
  SUSY localization/resurgence, string field theory, …).
- **DualityCert** = what actually exists now (4d N=1 Seiberg-duality verifier; matches
  the code package name `dualitycert`). It is QFTCert's **first cert / instantiation**.

### Experimental facts (the ground truth the framing must stay faithful to)
- Benchmark: n=145 depth-1 verifier-gated repairable fixtures, byte-identical across
  models (seed 20260715). 4 perturbation classes: drop_w_term(38), flip_w_sign(13),
  r_charge_perturb(52), rank_perturb(42). Seed families: dP0, dP1, dP2, F0, SPP, C3/Z2×Z2.
- Verifier obligations (duration-specific): anomaly matching (’t Hooft), superpotential
  R-charges, central charges (a), bounded chiral-ring consistency. Final check is
  STRICTER than feedback-time (chiral-ring L=5 vs L=3) — anti-gaming.
- Arms: single_shot_repair (ss), generic_retry (gr, K≤5, content-free "wrong, try again"),
  verifier_feedback (vf, category-level obligation feedback), vf_masked (E5 control:
  structurally identical but positional placeholders), best_of_n (E4 control: 2·K+1
  independent draws, stop at first cert), + E4 stop-first portfolio (ss→gr→vf).
- Pre-registered, frozen before data; primary analysis = GEE (exchangeable), Holm across
  a 6-hypothesis family. R=3 reps/arm.
- CONFIRMATORY (deepseek-chat + qwen-plus, complete):
  - E2 (iteration > single-shot): +8.3pp deepseek, +7.1pp qwen, Holm p<0.002. Robust, same sign both.
  - **E1 (vf vs gr) — the flip**: deepseek rd −1.8pp (Holm p=0.45, NOT significant);
    qwen rd +8.7pp (Holm p=0.0016, significant). Opposite behavior, confirmatory.
    [corrected from +10.4pp — Codex bootstrap caught this; matches GEE JSON + abstract.]
  - E4 (portfolio vs control): deepseek −10.3pp (independent resampling DOMINATES the
    ss→gr→vf portfolio, p=0.0016); qwen portfolio +14.7pp the other way.
  - E5 (vf vs masked, qwen): interpretable obligation identities worth +6.4pp over
    structurally identical masked feedback.
  - Net headline: the *optimal verifier-exploitation strategy is model-dependent*, with
    confirmatory significance in OPPOSITE directions. Invariant across both regimes: the
    cheap machine-checkable certificate itself.
- EXTENSION (MiniMax-M2.5, amendment 1, own Holm family, reported separately):
  E1 vf−gr = +3.2pp (vf 26.0% / gr 22.8%), E2 gr−ss = +11.0pp (ss 11.7%). Descriptive
  only so far (no full GEE yet); best_of_n(E4)/vf_masked(E5) NOT yet run (deferred, v2).
  invalid rate high (vf 46% / gr 39%) — MiniMax forced-thinking artifact, goes in limitations.
- EXPLORATORY: depth-2 axis (deepseek, single-rep) — difficulty dial; all strategies
  collapse to the floor. glm/gemini scout runs = provider noise, excluded.

---

### Round 1 — Claude

**Position: proposed section architecture + the framing decisions I most want stress-tested.**

Working title direction (not final wording): lead with the *method* ("a symbolic
verifier as an interaction environment for LLM repair"), with Seiberg duality as the
first instantiation. NOT "QFTCert: a universal physics verifier" (overclaim; only one
domain exists).

Proposed sections:
1. **Abstract** — keep the existing draft's spine (two-model existence claim + the flip
   + the certificate-as-invariant). Add ONE sentence naming DualityCert as the first
   cert of a QFTCert program. Rename system → DualityCert throughout.
2. **Introduction** — raise the altitude one level: (a) LLMs doing physics derivations
   lack ground-truth feedback the way math has proof assistants; (b) general recipe:
   build a symbolic verifier for a physics domain + use it as an LLM interaction/repair
   environment; (c) this paper instantiates it for Seiberg duality (DualityCert);
   (d) layered contribution claim: [general recipe + system] and [the repair-loop
   findings]. Existence claim explicitly scoped to the two confirmatory models.
3. **Related work** — verifier-in-the-loop AI4Math (AlphaProof, LeanDojo lineage);
   formal/'symbolic-oracle' methods; LLM+tools/agents.
4. **DualityCert: system** — present the verifier with an EXPLICIT generic-vs-domain
   split: generic layer (claim representation, obligation–verifier interface,
   certificate format, LLM-repair environment protocol) vs duality-specific obligations
   (anomaly matching, R-charges, central charges, chiral-ring). This section doubles as
   the "how to verifier-ize a domain" template.
5. **Experimental design** — benchmark (families, perturbation classes, verifier-gating),
   arms, pre-registered protocol + GEE + Holm. Anti-gaming (L=5 final vs L=3 feedback).
6. **Results** — (i) E2 iteration>single-shot both models; (ii) THE FLIP as headline
   (E1+E4 opposite confirmatory directions, deepseek vs qwen); (iii) E5 interpretability
   premium (qwen); (iv) MiniMax E1/E2 as a third-model data point (descriptive, honest
   about missing E4/E5); (v) depth-2 collapse as difficulty dial.
7. **Discussion / Limitations** — what model-dependence means; the certificate as the
   invariant; invalid-rate caveat (MiniMax thinking); two-model ⇒ existence claim only,
   NO strategy typology; masked-feedback caveat.
8. **Outlook — the QFTCert program** — future certs (bootstrap/amplitude/localization/
   SFT), how the generic layer is reused, contribution path, open-source. Clearly future/vision.
9. **Reproducibility / artifact** — GitHub, frozen manifest/protocol, exact commands.

**The 6 decisions I most want you (Codex) to attack:**
- Q1 (headline risk): Is "model-dependent optimal strategy, opposite confirmatory
  directions" defensible as the HEADLINE on n=2 models, or will referees read it as
  over-reaching from two points? Should E2 (robust, both-model) be co-headline as the
  safe anchor? Is there a statistically honest phrasing that avoids "we characterize
  model-dependence" (which n=2 cannot support) while still centering the flip?
- Q2 (framing vs red line): does raising the intro to "verifier-as-environment recipe"
  risk an overclaim the single-domain content can't cash, and how do we keep §4's
  generic/domain split from reading as post-hoc narrative rather than real architecture?
- Q3 (MiniMax honesty): best_of_n/vf_masked not yet run. Is a third model with only
  E1/E2 an asset or a liability in v1? Include as descriptive third point, or cut to
  appendix, or omit until v2?
- Q4 (scope/length): §4 system + §5 design + §6 five result threads + §8 vision — does
  this fit a workshop page budget? What MUST drop to appendix?
- Q5 (E4 interpretation): the deepseek E4 result is that independent resampling BEATS
  the ss→gr→vf portfolio (−10.3pp). Is "feedback can hurt / resampling can dominate" a
  finding we want foregrounded, or does it muddy the verifier-is-useful message?
- Q6 (naming): introducing DualityCert (concrete) vs QFTCert (program) — cleanest way to
  do this without confusing a reader who just wants the result?

End your reply with the single architectural choice above most likely to be wrong.

### Round 1 — Codex

**Scope-guard confirmation (kept verbatim):**

1. We are designing the paper's ARCHITECTURE (section structure, framing decisions,
   what goes where, claim ladder), NOT writing prose.
2. Target venue: NeurIPS AI4Science **workshop** + arXiv. Workshop norms: content must
   outweigh vision; ~4–9 pages + appendix; a concrete, self-contained contribution.
3. RED LINE: the paper must stand on its own foundation. \textsc{DualityCert} (the
   Seiberg-duality verifier) + the repair-loop findings must be a complete paper even
   if a reader ignores the larger \textsc{QFTCert} vision entirely. The vision is
   framing + outlook, never a substitute for results.
4. Do NOT alter frozen experimental facts (protocol, GEE analysis, numbers). We only
   decide how to PRESENT them. Faithfulness to the numbers is mandatory.
5. Deliverable must be self-contained enough that GPT-5.6 can write from it without
   this conversation.

#### Overall verdict: revise the nine-section architecture

[BLOCKER] The proposed Results section collapses three evidence tiers into one apparent
claim ladder: confirmatory E1/E2/E4/E5, the incomplete descriptive MiniMax extension,
and exploratory depth-2 collapse. They must not be sibling result threads. Otherwise a
workshop reader will reasonably infer that all five receive comparable inferential
weight.

[BLOCKER] “Optimal verifier-exploitation strategy” is too broad. The experiment
compares a frozen set of policies under specified call caps; it does not optimize over
all policies. The defensible object is the **ordering of the tested policies under the
frozen budget**.

[ERROR] E1 alone does not show two statistically significant opposite directions:
DeepSeek is −1.8 pp with Holm-adjusted \(p=0.45\), whereas Qwen is **+8.7 pp** with
Holm-adjusted \(p=0.0016\). E4 is the clean confirmatory reversal: −10.3 pp for
DeepSeek and +14.7 pp for Qwen. Therefore E4, not E1, must carry the “opposite
directions” architecture. The prior +10.4 pp value is stale and must not be
propagated; the corrected STATE value of +8.7 pp matches the frozen GEE result.

[WEAKNESS] A separate early Related Work section delays the concrete contribution,
while separate Outlook and Reproducibility sections give framing and artifact logistics
too much surface in a 4–9-page workshop paper. Fold related work into the Introduction;
make reproducibility a compact main-text artifact statement plus appendix; reduce
QFTCert to the final outlook paragraph.

#### Q1 — Make E2 the anchor and E4 the surprise; do not headline a two-model taxonomy

**Recommendation:** use a three-rung headline ladder, in this order:

1. DualityCert supplies cheap machine-checkable consistency certificates and a gated
   repair environment.
2. E2 is the cross-model anchor: verifier-gated iteration beats single shot on both
   confirmatory models (+8.3 pp DeepSeek, +7.1 pp Qwen; Holm \(p<0.002\)).
3. E4 is the central surprise: under the equal 11-call cap, the portfolio loses to
   independent verifier-filtered resampling on DeepSeek (−10.3 pp) but wins on Qwen
   (+14.7 pp). E1 (+8.7 pp on Qwen, −1.8 pp nonsignificantly on DeepSeek) and E5
   (+6.4 pp on Qwen) explain how feedback content contributes within that reversal.

The abstract, Introduction contribution list, Results ordering, and Discussion must all
use this same ladder. The inference is **non-universality among the two evaluated
models**, not characterization of model populations and not a sampler-versus-follower
typology. “Best-performing tested policy differed between the two named models” is the
maximum defensible claim; “the optimal strategy is model-dependent” is not.

#### Q2 — Ground the paper in DualityCert; present reuse as an extracted design pattern

**Recommendation:** retain the verifier-as-environment idea as motivation and design
implication, but do not list a domain-general recipe as an independently validated
contribution. Section 2 should proceed concrete-to-general:

1. claim and certificate semantics, including the boundary “consistency certificate,
   not proof of duality”;
2. the four duality-specific obligation families and the L=3/L=5 anti-gaming split;
3. the repair interface and obligation-feedback contract actually exercised by the
   experiments;
4. only then, a compact mapping table that extracts reusable roles—claim schema,
   obligations, certificate, feedback projection, strict final judge—from the concrete
   implementation.

This order prevents a post-hoc generic layer from masquerading as a demonstrated
multi-domain framework. Call it a reusable **design pattern** unless the artifact has a
genuine domain-independent API with a second implementation or conformance test. Do not
make “how to verifier-ize a domain” a section-level contribution that the present
single-domain evidence cannot cash.

#### Q3 — Put MiniMax in the appendix as an exploratory extension

**Recommendation:** remove MiniMax from the main Results claim ladder. Give it one
appendix subsection with E1/E2 point estimates, the separate amendment status, missing
E4/E5 cells, and forced-thinking invalid rates; allow one main-text cross-reference in
Limitations. Do not mention it in the abstract or contribution list. An incomplete
third-model matrix is useful external-validity context, but placing it beside the two
complete confirmatory models weakens rather than strengthens the evidentiary hierarchy.

#### Q4 — Replace nine peer sections with six main-text units

**Recommendation:** target a 6–7.5-page main paper with this architecture:

1. **Introduction + compact related work** (0.8–1.0 pp): problem, concrete gap,
   DualityCert, contribution ladder, closest verifier-in-the-loop precedents.
2. **DualityCert: certificates and repair interface** (1.2–1.5 pp): semantics,
   obligations, anti-gaming, repair contract, extracted design-pattern table.
3. **Benchmark and preregistered experiment** (1.1–1.3 pp): 145 fixtures, four
   perturbations, arms, E1/E2/E4/E5, GEE/Holm, frozen protocol.
4. **Confirmatory results** (2.0–2.3 pp): E2 anchor; E4 reversal; E1 and E5 feedback
   evidence; certificate-as-invariant synthesis. Use one primary table and one policy/
   result figure rather than five parallel result threads.
5. **Discussion and limitations** (0.7–0.9 pp): two-model scope, no typology, what E4
   does and does not identify, masked-feedback caveat, certificate-versus-proof limit.
6. **Conclusion, artifact statement, and QFTCert outlook** (0.3–0.5 pp): release and
   reproduction pointer first; one final paragraph for the prospective program.

Move to the appendix: full obligation definitions and certificate schema; seed-family
and perturbation-generation detail; full prompts/policy pseudocode; GEE specification;
per-replication and per-class tables; MiniMax; depth-2; provider-noise exclusions;
invalid-output decompositions; full costs, manifests, hashes, and exact commands. Keep
in the main text the L=3/L=5 safeguard, arm definitions, frozen hypothesis families,
all headline effect sizes, and the limitations needed to interpret them.

#### Q5 — Foreground E4, but never label it “feedback can hurt”

**Recommendation:** make E4 the second Results subsection, immediately after E2. Its
negative DeepSeek result is not a threat to the paper: both sides of E4 rely on
DualityCert as the exact acceptance filter, so the comparison isolates how to exploit
the verifier rather than whether the verifier is useful. It is the strongest evidence
that no single tested exploitation policy dominates.

Do not infer “feedback hurts.” E4 compares an ordered ss→gr→vf portfolio with
independent best-of-11 resampling; the contrast bundles feedback, dependence between
sequential attempts, and allocation of the call cap. State only that independent
resampling dominated that frozen portfolio for DeepSeek, with the reverse ordering for
Qwen. Use E1/E5 separately for the narrower value-of-feedback-content question.

#### Q6 — Use DualityCert everywhere substantive; introduce QFTCert only at the end

**Recommendation:** title, abstract, Introduction contribution list, system section,
figures, tables, and Results should name **DualityCert** only. Delete the proposed
QFTCert sentence from the abstract. Introduce **QFTCert** once in the final outlook
paragraph as the prospective umbrella program for future certs, explicitly identifying
DualityCert as its first implemented instance. A reader who stops before that paragraph
must already have received a complete paper.

**Single architectural choice most likely to be wrong:** relegating MiniMax entirely to
the appendix may sacrifice a useful third-model signal; if workshop reviewers strongly
prioritize breadth over matched confirmatory completeness, a one-row, explicitly
descriptive main-text placement could be preferable.

### Round 2 — Claude

Accepting your Round 1 corrections: E4 (not E1) carries the "opposite directions" reversal (E1 is nonsignificant on DeepSeek — agreed); claim narrowed to "the ordering of the tested policies under the frozen call budget" and "non-universality across the two evaluated models" (drop "optimal strategy is model-dependent" and any sampler/follower typology); the 6-section skeleton; concrete-to-general Section 2 ending in a design-PATTERN table (not a validated framework); related work folded into the intro; QFTCert only in the final outlook paragraph; MiniMax/depth-2 to the appendix.

Three points to close:

- R2-a (MiniMax middle path): rather than pure-appendix, I propose ONE external-validity sentence in Limitations ("a third model, MiniMax-M2.5, descriptive-only, moves the same direction as Qwen on E1, +3.2pp; full data in App. X"), plus the full appendix subsection — but NOT in the Results ladder, contribution list, or abstract. Does this preserve your evidentiary hierarchy while not discarding the third-model signal? Confirm or reject with a reason.

- R2-b (E4 headline wording): E4 is the cleanest reversal but bundles feedback-content + sequential dependence + call-cap allocation. Give the EXACT one-sentence framing of the E4 reversal, suitable for the abstract, that is punchy yet does NOT imply "feedback content flips sign" (that narrower claim is E1/E5's job). I want your literal sentence.

- R2-c (abstract rewrite): the current abstract centers E1 as the flip and says "optimal verifier-exploitation strategy is model-dependent" — both now flagged. Confirm the abstract MUST be rewritten to the E4-carries-reversal ladder + narrowed claim, and that this is a framing change (not a frozen-number change), permissible under guard 4.

Confirm convergence on the 6-section skeleton + 3-rung claim ladder, or name the remaining disagreement.

### Round 2 — Codex

**Scope-guard confirmation (kept verbatim):**

1. We are designing the paper's ARCHITECTURE (section structure, framing decisions,
   what goes where, claim ladder), NOT writing prose.
2. Target venue: NeurIPS AI4Science **workshop** + arXiv. Workshop norms: content must
   outweigh vision; ~4–9 pages + appendix; a concrete, self-contained contribution.
3. RED LINE: the paper must stand on its own foundation. \textsc{DualityCert} (the
   Seiberg-duality verifier) + the repair-loop findings must be a complete paper even
   if a reader ignores the larger \textsc{QFTCert} vision entirely. The vision is
   framing + outlook, never a substitute for results.
4. Do NOT alter frozen experimental facts (protocol, GEE analysis, numbers). We only
   decide how to PRESENT them. Faithfulness to the numbers is mandatory.
5. Deliverable must be self-contained enough that GPT-5.6 can write from it without
   this conversation.

#### R2-a — Accept the MiniMax middle path

**Definite position: accept.** One sentence in Limitations plus a full appendix
subsection preserves the evidence hierarchy because MiniMax remains outside the
abstract, contribution list, and Results ladder. The sentence must carry all three
qualifiers locally: descriptive-only, incomplete policy coverage, and excluded from
the confirmatory family. Use +3.2 pp exactly, without a significance implication or a
claim that MiniMax validates a model class. Structurally, MiniMax is an exploratory
external-validity check, not a fourth rung in the claim ladder.

#### R2-b — Literal E4 abstract sentence

**Definite position: use this sentence verbatim:**

> Under an equal 11-call cap, the frozen strategy portfolio underperformed independent verifier-filtered resampling by 10.3 percentage points on deepseek-chat but outperformed it by 14.7 points on qwen-plus, reversing the ordering of the two tested verifier-exploitation policies across the two confirmatory models.

This assigns the reversal to the two composite policies actually tested. It does not
attribute the reversal specifically to feedback content, sequential dependence, or
call allocation.

#### R2-c — Rewrite the abstract around the corrected claim ladder

**Definite position: the abstract must be rewritten.** Its present E1-centered
“optimal strategy is model-dependent” architecture conflicts with the agreed
inferential scope. This is a permissible framing correction under guard 4: every
number remains frozen; only the ordering and scope of the claims change.

The abstract architecture must be: (1) DualityCert and its certificate scope; (2) the
145-fixture preregistered experiment; (3) E2 as the cross-model iteration anchor; (4)
E4 as the tested-policy reversal, using the literal sentence above; (5) E1 and E5 as
the narrower evidence about feedback content; (6) the certificate as the invariant
plus artifact availability. QFTCert, MiniMax, depth-2, and any model typology stay out
of the abstract.

#### Convergence

**CONVERGED** on the six-section skeleton and three-rung claim ladder. No architectural
disagreement remains:

1. Introduction + compact related work.
2. DualityCert certificates and repair interface, concrete-to-general, ending in a
   design-pattern mapping rather than a universal-framework claim.
3. Benchmark and preregistered experimental design.
4. Confirmatory results ordered E2 anchor → E4 reversal → E1/E5 narrower feedback
   evidence → certificate-as-invariant synthesis.
5. Discussion and limitations, including the single qualified MiniMax sentence.
6. Conclusion, artifact statement, and one final QFTCert outlook paragraph.

The three rungs are: DualityCert supplies the auditable certificate substrate; E2
shows verifier-gated iteration improves on single shot in both confirmatory models;
E4 shows that the ordering of the two tested exploitation policies reverses across
those named models, with E1/E5 providing narrower supporting evidence rather than a
population-level typology.

**Single point most likely to be wrong:** even one MiniMax sentence in the main text
may lend an incomplete descriptive extension more evidentiary weight than intended;
pure appendix placement would enforce the hierarchy more mechanically.
