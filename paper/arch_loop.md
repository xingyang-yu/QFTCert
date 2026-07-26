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

### Round 3 — Claude (post-data: MiniMax extension family is now COMPLETE)

**New facts (frozen GEE, amendment-1 preregistered, own 3-hypothesis Holm; file
`runs/experiments/repair_d1/confirmatory_analysis/minimax_extension/confirmatory_analysis.json`):**

| MiniMax-M2.5 endpoint | rd | 95% CI | Holm p |
|---|---|---|---|
| E2 gr−ss | +11.0pp | [+5.5,+16.6] | 0.0003 (sig) |
| E4 portfolio−control | −8.0pp | [−14.1,−2.0] | 0.0184 (sig, NEGATIVE — deepseek-side) |
| E1 vf−gr | +3.2pp | [−1.5,+8.0] | 0.18 (ns) |
| E5 vf−masked (secondary, unadjusted) | −0.5pp | [−5.1,+4.1] | 0.84 (null) |

All five arms are now complete at 145×3 (best_of_n and vf_masked finished today);
the E4 replay ran per protocol; per-rep E4 signs are consistent (−9.0/−8.3/−6.9).
Caveat unchanged: provider-forced thinking; invalid rates higher than the two
primary models (vf 46%, gr 39%) — disclosed in amendment 1, stays in Limitations.

**Context: our Round 1–2 MiniMax decision (descriptive-only E1/E2 → one qualified
Limitations sentence + appendix; nothing in abstract/ladder) was made when E4/E5 did
not exist. The data changed. Amendment 1 itself preregistered the reporting mode:
"extension results are reported alongside but SEPARATELY from the two-model primary
family; the existence claim remains grounded in the primary family, with the
extension model as additional evidence under its own adjustment."**

**My position (attack it):**
- (a) Upgrade MiniMax from appendix-only to a compact main-text unit: ONE short
  paragraph + one 4-row table (or merged rows in the primary results table, visually
  separated and labeled "extension, own Holm family"), placed AFTER the two-model
  confirmatory results inside Section 4 (Results), NOT interleaved. Full detail still
  in appendix.
- (b) The ladder itself stays grounded in the two-model primary family (per
  amendment); MiniMax strengthens rung 2 (E2 now 3/3 models) and rung 3 (the E4
  ordering now genuinely varies across three complete models, 2-vs-1), and Discussion
  may now say the E5 interpretability premium is itself model-specific (qwen-only).
- (c) Abstract: keep the two-model claims as the spine; ADD ONE final clause/sentence
  noting a preregistered third-model extension replicates the iteration gain and the
  resampling-dominant ordering (no p-values in that sentence). Alternative I am open
  to: keep the abstract two-model only. Take a definite side.
- (d) Blueprint edits: update §3 facts (MiniMax rows + GEE file), replace §6
  "MiniMax rule" with the new placement rule, adjust §4 section budgets minimally
  (+0.2–0.3pp inside Results), update §8 residual-uncertainty note. No other changes.

Questions: R3-a confirm/deny (a)-placement; R3-b confirm/deny (c)-abstract clause
(definite side); R3-c does the E1-ns + E4-sig-negative MiniMax profile create any
NEW overclaim hazard our §6 guardrails miss (e.g. "2-vs-1 majority" language)?
Give exact forbidden phrasings if so. End with the single point most likely wrong.

### Round 3 — Codex

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

#### Frozen-number verification

[OK] The Round 3 table matches the MiniMax GEE artifact at the stated precision. E2 is
+11.0339 pp with 95% CI [+5.4769,+16.5909] and Holm \(p=0.0002985\); E4 is −8.0460
pp with CI [−14.1003,−1.9916] and Holm \(p=0.0183881\); E1 is +3.2185 pp with CI
[−1.5211,+7.9581] and Holm \(p=0.1831985\); E5 is −0.4598 pp with CI
[−5.0541,+4.1346] and unadjusted \(p=0.8445030\). The rounded +11.0, −8.0, +3.2,
and −0.5 pp values, all intervals and p-values, and the E4 per-rep signs are faithful.

#### R3-a — Promote MiniMax to a separated main-text extension unit

**Definite position: confirm placement (a).** The evidentiary state has materially
changed: MiniMax now has a complete five-arm, three-replication matrix, a preregistered
amendment, frozen GEE, and a complete adjusted E1/E2/E4 family. Appendix-only treatment
would now hide evidence directly bearing on both empirical rungs.

Place one compact, explicitly subordinate unit **after** the full two-model primary
results in Section 4. Use one short paragraph and a visually separated MiniMax block in
the main result table rather than a second table. Its block header must say
“preregistered MiniMax-M2.5 extension; separate three-hypothesis Holm family,” and E5
must be labeled “secondary, unadjusted.” Never interleave MiniMax rows with the two-model
primary rows or recompute a pooled three-model multiplicity family. Allocate the extra
0.2–0.3 page inside Results; keep mechanisms, invalidity detail, per-replication rows,
and full extension analysis in the appendix.

The old “descriptive-only, one Limitations sentence plus appendix” routing is obsolete
and must be replaced in the blueprint. MiniMax still does not enter the two-model
primary family or become a new ladder rung. It supplies separately adjusted supporting
evidence beneath rungs 2 and 3. The Limitations sentence should now address the
provider-forced-thinking/invalid-rate caveat, not characterize all MiniMax results as
descriptive.

#### R3-b — Add one separately signposted MiniMax sentence to the abstract

**Definite position: confirm abstract inclusion.** A complete preregistered extension
that repeats E2 and one side of E4 is central enough to warrant one sentence, provided
the two-model primary results remain the spine and the family boundary is explicit.
Place it after the two-model E1/E5 sentence and before the certificate/artifact close.
Use this sentence:

> Separately, a preregistered MiniMax-M2.5 extension again finds an iteration gain and independent verifier-filtered resampling outperforming the strategy portfolio.

Do not add MiniMax p-values to the abstract, count models, or revise the literal
two-model E4 sentence. The adverb “Separately” and the noun “extension” are load-bearing:
they prevent the extension from being silently absorbed into the primary family.

#### R3-c — Add new overclaim guardrails

**Definite position: the new data permit named-model replication statements, not
majority rules, model types, equivalence, or a feedback mechanism.** Add these exact
phrasings to the forbidden list:

- “two out of three models prefer resampling”; “a majority of models favor
  resampling”; “resampling is the default/optimal policy”;
- “the models divide into resampling-dominant and feedback-dominant regimes/types/
  classes”; “DeepSeek and MiniMax are sampler-type, whereas Qwen is a feedback-follower”;
- “MiniMax confirms that the optimal strategy is model-dependent”; “three models
  establish model-dependence”;
- “feedback does not help MiniMax”; “MiniMax is insensitive to feedback”; “resampling
  beats feedback on MiniMax”;
- “E5 has no effect/is null for MiniMax”; “masked and interpretable feedback are
  equivalent on MiniMax”;
- “the E5 interpretability premium is model-specific”; “only Qwen benefits from
  interpretable obligation identities”;
- “third confirmatory model”; “the pooled three-model confirmatory family”; and any
  unqualified “3/3” or “2-vs-1 majority” formulation.

The reasons are structural. The three models are not a sampled population; E4 compares
composite policies and does not isolate feedback; nonsignificant E1/E5 estimates do not
establish absence or equivalence; and a significant Qwen E5 beside nonsignificant
DeepSeek/MiniMax E5 results is not itself a cross-model interaction. Allowed replacements
are named-model descriptions: “the E5 advantage was detected on Qwen but not on
DeepSeek or MiniMax,” and “the separately preregistered MiniMax extension reproduced
the negative E4 ordering observed on DeepSeek.”

#### Convergence

**CONVERGED.** The six-section skeleton and three-rung ladder remain unchanged. The
only architectural update is evidence routing: MiniMax becomes a compact, separately
labeled extension block after the two-model primary Results, receives one explicitly
separate abstract sentence, and retains full detail plus the invalidity caveat in the
appendix/Limitations. The ladder remains DualityCert substrate → two-model E2 anchor →
two-model E4 reversal, with MiniMax as separately adjusted supporting evidence rather
than a fourth rung or a redefinition of the primary family.

**Single point most likely to be wrong:** adding MiniMax to the abstract may blur the
primary/extension boundary despite the explicit “Separately” qualifier; if the final
abstract becomes too dense, this sentence is the first item that should be removed,
while the main-text extension unit should remain.

### Round 4 — Claude (physics integration for hep-th readers)

New author requirement (2026-07-21): the outline reads venue-native for AI4Science,
but the paper will be read by hep-th physicists too (arXiv cross-list; and the §6
QFTCert outlook explicitly recruits domain experts, who are all physicists). Decide
the optimal physics-integration strategy WITHOUT breaking the converged architecture,
page budget, or guardrails.

**My position:**
1. Main text stays AI-venue-shaped. All physics depth goes to a NEW first appendix,
   "Physics primer: Seiberg duality and the consistency obligations" (~1.5 pp cap),
   written for a hep-th reader from another subfield (bootstrap/amplitudes level:
   knows QFT and SUSY basics, hazy on Seiberg duality specifics). Beats: (i) what
   Seiberg duality asserts (electric/magnetic pair, IR equivalence, strong-weak),
   why it is foundational yet not provable step-by-step; (ii) why each obligation
   family is a correct NECESSARY condition ('t Hooft anomaly matching classic
   argument; central charge a under IR equivalence; chiral ring as gauge-invariant
   operator data; superconformal R / a-maximization context); (iii) the physical
   identity of the seed families (quivers from branes at toric CY3 singularities:
   dP0/dP1/dP2/F0/SPP/C3/Z2×Z2); (iv) explicitly NO derivations, no full a-max
   machinery, no Kutasov generalities.
2. Surgical main-text additions (~5–6 sentences, ~0.1 pp total): §1 P1 one sentence
   stating what Seiberg duality claims and its status; §2 P2 half-sentence per
   obligation on why it is a necessary condition; §3 P1 one sentence on the
   geometric origin of the seeds. Everything else unchanged.
3. arXiv: primary cs.LG (or cs.AI), cross-list hep-th. RECOMMEND cross-listing.

**Questions (definite positions please):**
- Q-a: Appendix-first vs a short main-text "physics setting" subsection (e.g. §2.0).
  Where exactly is the optimal boundary given the 6–7.5 pp budget and AI reviewers?
- Q-b: Exact beat list + length cap for the primer. What must it NOT contain?
- Q-c: The surgical-sentence list: confirm placements; check each against the
  guardrails (especially that "necessary conditions" language cannot slide into
  "verifier evidence for duality"); does a physics-heavy first sentence weaken the
  AI-venue hook in §1 P1?
- Q-d: Terminology policy for main text: which SUSY terms may appear bare
  (superpotential? R-charge? chiral ring?), and a uniform gloss-on-first-use rule
  so prose doesn't oscillate between audiences.
- Q-e: Does the primer let us TIGHTEN any existing main-text physics (move detail
  out of §2), or is this strictly additive?
- Q-f: Cross-listing hep-th: benefits vs risks (moderation, audience expectation
  mismatch). Definite recommendation.

End with the single choice here most likely to be wrong.

### Round 4 — Codex

**Scope guards confirmed:** this reply changes paper architecture, not prose; preserves
the NeurIPS AI4Science workshop + arXiv target and 6–7.5-page main-text budget; keeps
DualityCert + its findings standalone and QFTCert outlook-only; leaves every frozen
number untouched; and specifies enough detail for GPT-5.6 without this conversation.

#### Q-a — Appendix-first, with no new main-text subsection

**Definite position: reject a labeled §2.0 “physics setting” subsection.** Keep the
six-section AI-venue architecture and add a new first appendix containing the physics
primer. A subsection would consume scarce main-text space, delay the system, and invite
a second motivation arc. The exact boundary is:

- main text contains only the physics definitions required to parse the contribution,
  the necessary-not-sufficient contract, one representative obligation, and one
  sentence identifying the seed theories;
- the primer contains physical motivation, the relation among the obligations, exact
  \(R\)-symmetry context, chiral-ring meaning, and the geometric identity of the seeds;
- detailed verifier algorithms, benchmark construction, and experiments remain in
  their existing sections/appendices rather than migrating into the primer.

Do not add a new paragraph solely for physics. Insert the orientation material into
§1 P1, §2 P1–P2, and §3 P1 as specified under Q-c. This keeps net main-text growth at
at most 100 words (approximately 0.15 page).

#### Q-b — Exact primer architecture and hard cap

**Definite position:** add **Appendix A, “Physics primer: Seiberg duality and the
consistency obligations,”** before the current verifier-detail appendix. Hard cap:
**800 words or 1.5 rendered pages, whichever is reached first**, including headings;
at most **two displayed equations**; no figure or table. Use exactly seven beats, one
paragraph each:

1. **What the duality asserts (90–110 words).** Two distinct \(4d\)
   \(\mathcal N=1\) ultraviolet gauge-theory descriptions—conventionally electric and
   magnetic—are proposed to flow to the same infrared physics. “Strong–weak” may be
   mentioned only as an often-useful regime-dependent feature, never as the definition.
2. **Minimal quiver/SUSY dictionary (90–110 words).** Gauge nodes, arrows/chiral
   multiplets, superpotential \(W\), global symmetries, \(R\)-charges, and
   gauge-invariant operators; enough to read DualityCert's schema, no dualization
   derivation.
3. **Necessary-versus-sufficient logic (70–90 words).** Infrared equivalence implies
   matching protected data, so a violated obligation rules out the encoded claim in
   scope; passing the finite obligation set establishes only the stated consistency
   certificate, not duality.
4. **’t Hooft anomalies and central charge \(a\) (120–140 words).** Explain
   renormalization-group-invariant global-symmetry anomalies and give, at most, the
   one-line relation \(a=\frac{3}{32}(3\,\mathrm{Tr}R^3-\mathrm{Tr}R)\). State that
   equality uses the exact infrared \(R\)-symmetry; DualityCert checks the encoded
   assignment and does not derive it.
5. **Superpotential and \(R\)-symmetry obligations (90–110 words).** Explain
   \(R(W)=2\), gauge/ABJ anomaly freedom, and one sentence placing the exact
   superconformal \(R\)-symmetry in the context of \(a\)-maximization. State explicitly
   that the verifier does not perform a full \(a\)-maximization analysis.
6. **Chiral ring and the bounded check (110–130 words).** Define gauge-invariant
   chiral operators modulo F-term relations; explain why true dual descriptions should
   agree on protected operator data; distinguish full ring isomorphism from the finite
   \(R\)-graded \(L=3/L=5\) check. A bounded pass is partial consistency, not a full
   chiral-ring match.
7. **Physical origin of the benchmark seeds (90–110 words).** Identify the examples
   as toric quiver gauge theories associated with D3-branes probing Calabi–Yau
   threefold singularities; decode dP0/dP1/dP2, \(F_0\), SPP, and
   \(\mathbb C^3/(\mathbb Z_2\times\mathbb Z_2)\) at name level only; point to the
   benchmark appendix for mutations and fixtures.

The primer must **not** contain: a derivation or purported proof of Seiberg duality;
the SQCD phase diagram or conformal-window survey; Kutasov/adjoint/generalized-duality
material; an \(a\)-maximization derivation; brane-tiling, toric-geometry, or mutation
derivations; experimental arms, model results, or frozen numbers; QFTCert vision;
additional unimplemented obligations; an unqualified strong–weak claim; or any
suggestion that bounded chiral-ring agreement or the full certificate is sufficient
for duality.

#### Q-c — Confirm the surgical additions, with exact placements

**Definite position: accept the surgical strategy with one ordering correction—the
AI problem remains the first sentence.** Use these placements:

1. **§1 P1, after the opening AI-verification sentence:** one sentence defining
   Seiberg duality as distinct \(4d\) \(\mathcal N=1\) gauge theories proposed to
   flow to the same infrared physics. Do not lead the paper with physics history or
   “strong–weak.”
2. **§2 P1:** append one sentence identifying electric/magnetic as labels for the two
   ultraviolet descriptions encoded by \(T_A,T_B\), not a certification outcome.
3. **§2 P2:** add one compact sentence assigning the physical role of each obligation:
   global anomalies are infrared invariants; allowed superpotential interactions obey
   the encoded \(R\)-symmetry constraints; the same infrared theory has the same
   central charge \(a\); and dual descriptions agree on the tested protected operator
   data. Follow immediately with: failure violates a necessary condition in scope,
   whereas passing certifies only that no tested inconsistency was found.
4. **§2 P3:** retain the representative anomaly equality and residual-to-feedback
   example. It is system content, not primer duplication.
5. **§3 P1:** add one sentence that the seed families are toric quiver gauge theories
   associated with D3-branes at Calabi–Yau singularities, with a primer cross-reference.

This is five additions totaling approximately 80–100 words. “Necessary condition” is
permitted only in the direction **duality implies obligation**. Forbid the converse
phrases “the obligations provide evidence that the theories are dual,” “passing
supports the duality,” and “the verifier validates the duality.” The approved result
is “passes the tested consistency obligations” or “receives a consistency
certificate.” The physics sentence does not weaken the AI hook because it follows,
rather than replaces, the first AI-facing sentence.

#### Q-d — Exact terminology and first-use gloss policy

**Definite policy: one global first-use gloss, then one canonical term everywhere.**
Glosses belong in running text, not a glossary table or footnote, and should be at
most twelve words where possible. Do not re-gloss by section; figure/table captions
are the sole exception and must remain independently readable.

Use this exact terminology map:

- First use: **“four-dimensional (\(4d\)) \(\mathcal N=1\) supersymmetric gauge
  theory”** and **“infrared (IR)”**; thereafter \(4d\) \(\mathcal N=1\) and IR.
- **Quiver:** first gloss as “a directed graph encoding gauge sectors and matter”;
  thereafter quiver may appear bare.
- **Electric/magnetic:** first gloss as conventional labels for the two proposed UV
  descriptions; never use either label to mean correct/incorrect.
- **Chiral multiplet:** first gloss as a supersymmetric matter field; thereafter it
  may appear bare.
- **Superpotential \(W\):** first gloss as the polynomial encoding supersymmetric
  interactions; thereafter use “superpotential” or \(W\), not alternating synonyms.
- **\(R\)-charge:** first gloss as charge under the \(U(1)_R\) symmetry; thereafter
  always write “\(R\)-charge” (never “R charge” or “R-symmetry charge”).
- **’t Hooft anomaly matching:** first gloss as matching renormalization-group-
  invariant global-symmetry anomaly coefficients; thereafter “anomaly matching” is
  permitted.
- **Central charge \(a\):** first gloss as the four-dimensional Weyl-anomaly
  coefficient; thereafter use \(a\), never “the a-anomaly.”
- **Chiral ring:** it may **not** appear bare on first use. Define it as
  “gauge-invariant chiral operators modulo F-term relations”; thereafter it may
  appear bare.
- **\(a\)-maximization, F-term, meson, baryon, toric, del Pezzo, SCFT, and CY3:** keep
  out of the main text unless required by one of the five surgical sentences; define
  on first use in the primer. In main text spell “Calabi–Yau threefold” rather than
  introducing CY3 for a single occurrence.

Enforce these claim terms globally: **candidate duality claim** until discussing the
physics hypothesis; **consistency obligation** for a machine check; **necessary
condition** for its physics interpretation; **consistency certificate** for a pass.
Never substitute “proof,” “verified duality,” “validated duality,” or “evidence for
duality.” Keep **strategy portfolio** and **independent verifier-filtered resampling**
as the two E4 policy names without synonyms.

After the first-use glosses, “superpotential” and “\(R\)-charge” may appear bare;
“chiral ring” may appear bare only after its substantive definition; \(a\)-maximization
is appendix-only.

#### Q-e — The primer must tighten the main text, not merely add to it

**Definite position: this is a substitution, not a purely additive appendix.** Keep
§2 P1's schema, §2 P3's representative equation, §2 P4's \(L=3/L=5\) safeguard, and
the necessary-not-sufficient sentence in the main text. Compress §2 P2 to obligation
names plus the single physical-role sentence specified above; move its extended
physics rationale, exact-\(R\) context, \(a\)-maximization context, and full chiral-ring
definition to Appendix A. Keep only the one-line seed-origin statement in §3 and move
all acronym/name decoding to the primer. Net main-text growth must remain below
0.15 page; otherwise cut physics explanation from §2 before cutting experimental or
system content.

#### Q-f — Cross-list hep-th; use cs.AI as primary

**Definite recommendation: submit primarily to cs.AI and request a hep-th cross-list.**
The paper's core contribution is an AI agent/tool environment and policy comparison,
not a new learning algorithm; arXiv's taxonomy places theorem proving and related
symbolic AI in cs.AI, while hep-th explicitly covers formal QFT and supersymmetry.
The primer, representative obligation, classic physics citations, and careful
necessary-not-sufficient boundary make the cross-list substantively defensible.
[ArXiv's category taxonomy](https://arxiv.org/category_taxonomy) supports this
division.

The benefit is discoverability by the domain experts whom the outlook addresses. The
moderation and audience-mismatch risk is real but acceptable: hep-th readers must be
able to identify the physical claim, obligations, and limitations without mistaking
the paper for a new duality result. Keep hep-th secondary; do not make it the primary
category and do not reshape the six-section main text into a hep-th paper.

**Single choice most likely to be wrong:** rejecting a labeled main-text physics
subsection may under-serve hep-th readers who do not follow appendix cross-references;
if a rendered draft remains opaque after the five surgical additions, a compact boxed
orientation could outperform the appendix-first boundary, but it should replace—not
augment—main-text material.

### Round 5 — Claude (acceptance + convergence check)

All Round 4 positions ACCEPTED without exception: appendix-first with NO §2.0
subsection (main-text growth ≤100 words); primer = new Appendix A with your exact
7-beat structure, 800-word/1.5-pp hard cap, ≤2 displayed equations, and the full
exclusion list; surgical placements as specified with the AI problem remaining §1's
first sentence; the global claim-term policy (candidate duality claim / consistency
obligation / necessary condition / consistency certificate; superpotential and
R-charge bare after first-use gloss; chiral ring bare only after definition;
a-maximization appendix-only); Q-e substitution principle (compress §2 P2 to names +
single physical-role sentence + necessary/sufficient contract, extended rationale
moves to the primer); cs.AI primary + hep-th cross-list.

I will fold all of this into PAPER_OUTLINE.md (v3): §1/§2/§3 beat edits, new
Appendix A with re-lettering A–H → B–I, terminology policy added to the
cross-cutting rules, and an arXiv-categories note. Your most-likely-wrong flag
(appendix-first may under-serve hep-th readers who skip appendices) is recorded in
the outline as a post-draft check: if a rendered draft reads opaque to a hep-th
test-reader, a compact boxed orientation REPLACES main-text material, never augments.

R5-a: Confirm CONVERGED on the physics-integration plan, or state the single
remaining disagreement. One line suffices.

### Round 5 — Codex

**CONVERGED.** No remaining disagreement; the v3 fold plan and replacement-only
post-draft hep-th readability check faithfully preserve all scope guards.

### Round 6 — Claude (micro: arXiv category set)

Author asks: **primary cs.AI + cross-list cs.LG + cross-list hep-th** (three
categories) instead of the converged two. My take: fine and common — the paper is
an empirical, preregistered evaluation of LLM policies, which is squarely cs.LG
audience material; the NeurIPS AI4Science crowd browses cs.LG listings more than
cs.AI; three categories is within arXiv norms.

R6-a: CONFIRM cs.AI (primary) + cs.LG + hep-th, or state why to drop one. If you
would instead swap the primary to cs.LG, say so with one reason. A few lines only.

### Round 6 — Codex

**CONFIRM:** primary **cs.AI**, cross-list **cs.LG** and **hep-th**. The verifier-guided
agent/system contribution makes cs.AI the best primary; the preregistered LLM-policy
evaluation and Seiberg-duality domain content substantively justify both cross-lists.

### Round 7 — Claude (amend the four-place rule for one §1 design-transparency sentence?)

Author reaction while reviewing the written §1: surprised that the Introduction
names only the two primary models after substantial MiniMax work. Proposal on the
table: append ONE neutral sentence to §1's experiment paragraph (P3), exactly:

  "In addition, a third model, \mmcode{}, is evaluated as a separately
  preregistered extension with its own multiplicity adjustment
  (Section~\ref{sec:results})."

Properties: no numbers, no claim language, no contribution-paragraph contact
(§1's contributions paragraph stays strictly two-model), explicit
separately-preregistered + own-adjustment labels, forward pointer to the §4
extension unit.

Arguments FOR: (i) §1 P3 is the study-design description; omitting one of three
evaluated models from the design description is a completeness gap independent of
claim weight; (ii) reviewers dislike an undisclosed third model first appearing in
Results; (iii) the abstract already carries the converged one-sentence MiniMax
mention, so §1 silence is not load-bearing for the hierarchy.
Arguments AGAINST: (iv) the four-place rule was converged precisely to keep
evidence tiers visually and structurally separate, and exceptions erode it;
(v) the abstract mention plus §4 unit already prevent genuine surprise;
(vi) slippery slope toward re-interleaving.

R7-a: CONFIRM the amendment (four-place rule becomes five-place, adding "§1 P3
design-transparency sentence, verbatim as above") or REJECT with the controlling
reason. Definite, a few lines; also state any required wording change to the
sentence itself.

### Round 7 — Codex

**CONFIRM.** Design transparency controls: §1 P3 should identify every evaluated evidence tier, while explicit separation and adjustment language preserves the primary–extension boundary. Use: “Separately, \mmcode{} is evaluated under a preregistered extension with its own three-hypothesis Holm family (Section~\ref{sec:results}).” Avoid “a third model,” which invites model-counting and tier flattening; make no other MiniMax placement change.
