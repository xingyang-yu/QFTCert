# DualityCert paper — paragraph-level outline (v3; physics integration CONVERGED; for author confirmation)

Derived from `paper/PAPER_BLUEPRINT.md` (converged architecture, final clean numbers).
Two Codex rounds folded: outline critique (arch-loop, pre-fold verdict NOT READY, all
edits incorporated) + physics-integration plan (arch-loop Rounds 4–5, CONVERGED).
Granularity: one bullet = one paragraph (or one float). Writing starts at §1
(author's preference), abstract written LAST per blueprint §5.

**arXiv categories (converged, Round 6):** primary **cs.AI**, cross-list **cs.LG**
and **hep-th** (author's three-category request, Codex CONFIRMED: agent/system
contribution → cs.AI primary; preregistered LLM-policy evaluation → cs.LG;
Seiberg-duality domain content + primer → hep-th). Main text stays an AI-venue paper.

**Title (FINAL, author decided 2026-07-24):**
"DualityCert: Verifier-Gated Language-Model Repair of Broken Duality Claims in
Quantum Field Theory" — name+colon system format (AI-native); QFT concept in the
description half per author preference (Seiberg moves to abstract/§1);
"Language-Model" kept as the venue/routing signal. Supersedes the earlier T2.

**Main-text budget:** ~6–7.5 pp, 6 sections, ONE table (Table 1) + TWO figures:
Figure 1 = system-overview diagram in §2 (TikZ, added per author 2026-07-24; AI-venue
convention), Figure 2 = the E4 forest plot in §4. No second table in the main text.

---

## §1 Introduction (incl. compact related work) — 0.8–1.0 pp, FIVE paragraphs
- **P1 (problem + gap; epistemic-contrast beat added by author 2026-07-24;
  typographically SPLIT into three paragraphs at "However, this approach" and "A
  substantial part" per author 2026-07-24 — beats unchanged, zero added words).**
  FIRST sentence = the AI problem (LLMs produce plausible-but-unchecked physics
  derivations; math has proof assistants, AlphaProof/Lean line, now research-level).
  THEN the epistemic contrast (author's framing): mathematics rests on an axiomatic
  substrate (statement settled by proof); formal QFT/string theory, though unusually
  rigorous for physics, advances through structures that outrun available
  axiomatizations, and absent experiment practitioners judge proposals chiefly by an
  accumulating web of consistency checks. Seiberg duality (one-sentence definition:
  two distinct 4d N=1 gauge theories flowing to the same IR physics) as the
  paradigmatic case: no proof assistant formalizes it, and the ORIGINAL evidence was
  precisely such checks ('t Hooft anomaly matching among them). Design consequence:
  build not a physics imitation of a proof assistant but a verifier native to the
  discipline's own standard of evidence. Then: a substantial layer of those checks
  is exactly mechanizable: anomaly matching, superpotential R-charges, central
  charges, bounded chiral-ring data; cheap, symbolic, exact *within its encoded
  scope* (no "ground truth for physics generally" claim; no unsupported "first"
  claim; strong–weak never as the definition).
- **P2 (DualityCert).** The system: symbolic verifier for 4d N=1 Seiberg-duality
  claims; emits consistency CERTIFICATES (explicitly not proofs of duality);
  doubles as a verifier-gated repair environment for LLM agents. Scope sentence
  (quiver gauge theories; four obligation families).
- **P3 (experiment in one paragraph).** 145 depth-1 perturbed claims, 4 perturbation
  classes, byte-identical across models; pre-registered frozen protocol; two
  confirmatory models (deepseek-chat, qwen-plus); GEE + Holm. (NO MiniMax here —
  four-place rule.)
- **P4 (contribution ladder, verbatim scope guards).** Three rungs: (i) substrate
  (certificates + repair environment); (ii) E2 anchor (iteration gain, both
  confirmatory models, +8.3/+7.1 pp); (iii) E4 reversal — the ordering of the TWO
  TESTED exploitation policies under the frozen 11-call cap reverses across the two
  named models (−10.3 vs +14.7 pp) — with E1/E5 as narrower feedback-content
  evidence. Named-model language only.
- **P5 (related work + roadmap).** Verifier-in-the-loop AI4Math (AlphaProof,
  LeanDojo lineage, AlphaGeometry); symbolic-oracle / tool-grounded LLM methods;
  LLM agents with execution feedback (code-repair line). Positioning via closest
  precedents; NO primacy ("first") claim unless the literature search later
  supports one. Ends with a one-sentence roadmap.

## §2 DualityCert: certificates and repair interface — 1.2–1.5 pp
- **P1 (claim representation).** A claim = ordered theory pair (T_A "electric",
  T_B candidate "magnetic") in a serializable quiver schema: gauge nodes/ranks,
  chiral matter with representations, superpotential terms, R-charges; what the
  verifier consumes. Plus one converged sentence: electric/magnetic are LABELS for
  the two encoded UV descriptions, not a certification outcome.
- **P2 (obligation families + judge semantics — COMPRESSED per Q-e substitution).**
  Name the four obligation families ('t Hooft anomaly matching; superpotential
  R-charge consistency; central charge a; R-graded bounded chiral-ring consistency)
  + ONE compact physical-role sentence covering all four (global anomalies are IR
  invariants; allowed superpotential interactions obey the encoded R-symmetry
  constraints; the same IR theory has the same central charge a; dual descriptions
  agree on the tested protected operator data), followed immediately by the
  contract sentence: failure violates a necessary condition in scope; passing
  certifies only that no tested inconsistency was found. Judge semantics:
  CERTIFIED / FAILED / invalid / out-of-scope; what the certificate records.
  Extended physics rationale, exact-R/a-maximization context, and the full
  chiral-ring definition live in Appendix A (the primer), NOT here.
- **P3 (one obligation, concretely — NEW per Codex).** Show one representative
  obligation mathematically: an anomaly-matching equality (e.g. matching a
  't Hooft anomaly polynomial coefficient across the pair), and how a FAILED
  residual is projected into the category-level feedback string the repair loop
  shows the model. This is the "what the verifier actually computes" beat.
- **P4 (anti-gaming).** Feedback-time verifier runs chiral ring to L=3; the FINAL
  acceptance judge runs L=5 (stricter than anything the model saw). Rationale:
  the feedback channel cannot be gamed into the final check.
- **P5 (repair interface).** The edit contract (full-theory JSON edit), K≤5 rounds,
  what each arm's feedback projection exposes (category-level identities / masked
  positional placeholders / content-free retry), copy-cheat guard (identity pair
  rejected).
- **P6 (extracted design pattern — INLINE list, no float).** Reusable roles: claim
  schema; obligation set; certificate; feedback projection; strict final judge.
  Explicitly a design PATTERN extracted from one implementation, not a validated
  multi-domain framework.

## §3 Benchmark and preregistered experiment — 1.1–1.3 pp
- **P1 (fixtures).** Seed families (dP0, dP1, dP2, F0, SPP, C3/Z2×Z2 + node
  choices) + one converged sentence: these are quiver gauge theories associated
  with D3-branes at toric Calabi–Yau threefold singularities (primer
  cross-reference; "toric" modifies the geometry, per author 2026-07-25); depth-1 perturbations in 4 classes with counts (drop_w 38,
  flip_w 13, r_charge 52, rank 42); verifier-gated repairability (n=145);
  byte-identical regeneration (seed 20260715); attrition to appendix.
- **P2 (arms + collection discipline).** ss; gr (content-free retry, K≤5); vf
  (category-level feedback); vf_masked (structurally identical, positional
  placeholders); best_of_n (11 independent draws, stop at first cert). State
  explicitly: ss/gr/vf components are collected COMPLETELY, and the E4 portfolio
  (ss→gr→vf under the same 11-call cap) is constructed by deterministic stop-first
  REPLAY over those complete components, paired against best_of_n. Inline list,
  no float.
- **P3 (endpoint map — NEW per Codex).** E1 = vf−gr; E2 = gr−ss; E4 = portfolio −
  best-of-11; E5 = vf−masked (secondary); E3 = vf@1−gr@1 (descriptive). One
  compact paragraph so Table 1 reads without back-references.
- **P4 (models, reps, preregistration + analysis).** deepseek-chat + qwen-plus
  (confirmatory, R=3); protocol frozen before data (commit hash); GEE (logit,
  exchangeable, fixture clusters, robust sandwich, standardized marginal risk
  differences); Holm across the 6-hypothesis primary family; E5 secondary (own
  family), E3 descriptive; exogenous-contamination rule (transport errors:
  filter + resume) with pointer to appendix. (NO MiniMax here; sampling/config
  minutiae — temperature, token cap, client timeout — live in Appendix H.)

## §4 Confirmatory results — 2.2–2.6 pp
- **TABLE 1 (the only main-text table).** Two-model primary block (E1/E2/E4/E5 ×
  {deepseek, qwen}: rd, 95% CI, Holm p) + visually separated MiniMax extension
  block (header: "preregistered MiniMax-M2.5 extension; separate three-hypothesis
  Holm family"; E5 row labeled secondary/unadjusted). Numbers verbatim from the
  two frozen GEE artifacts.
- **P1 (two-model E2 anchor).** Verifier-gated iteration beats single shot on both
  confirmatory models (+8.3 deepseek / +7.1 qwen, Holm p<0.002). TWO-MODEL ONLY.
- **P2 + FIGURE 2 (two-model E4 reversal — the surprise).** FIGURE 2 = horizontal
  FOREST PLOT of the E4 risk difference (portfolio − independent resampling, pp):
  vertical zero line; left annotation "resampling higher", right "portfolio
  higher"; DeepSeek and Qwen grouped as the primary family; visible divider before
  the MiniMax extension row; large GEE point ±95% CI per model; three faint
  per-replication points behind each estimate. Text: deepseek −10.3 pp (portfolio
  loses to resampling, p=0.0016); qwen +14.7 pp (portfolio wins, p<1e-4); per-rep
  signs consistent. Strictly named-model phrasing. TWO-MODEL TEXT (the figure's
  extension row is referenced only in P4).
- **P3 (two-model E1/E5: narrower feedback-content evidence).** E1: qwen +8.7
  (p=0.0016); deepseek −1.8 (ns). E5: interpretable obligation identities worth
  +6.4 over masked feedback on qwen (p=0.0065); not detected on deepseek (0.0,
  ns). "Detected on Qwen but not on DeepSeek" phrasing.
- **P4 (MiniMax extension unit — DEDICATED paragraph, after the complete two-model
  results).** Header language: separately preregistered MiniMax-M2.5 extension,
  own three-hypothesis Holm family (amendment introduced HERE, not in §3).
  Contents: E2 +11.5 (p=2e-4) — "E2 was positive in both primary models and,
  separately, in the MiniMax extension"; E4 −9.0 (p=0.009) — "reproduced the
  negative E4 ordering observed on DeepSeek" (points to the extension row of
  Figure 1 below the divider); E1 +2.8 (ns); E5 −0.7 (ns, secondary/unadjusted).
  Forced-thinking + invalid-rate caveat pointer to §5/Appendix F.
- **P5 (synthesis: certificate as the invariant).** In every case the
  higher-performing of the two E4 policies consumes the same cheap certificate;
  verifier-gated selection lifts success far above raw single shot in both primary
  models and, separately, in the extension. NO "all three models" phrasing. 2–4
  sentences, no new claims beyond Table 1.

## §5 Discussion and limitations — 0.7–0.9 pp (four SHORT beats)
- **P1 (what E4 does/doesn't identify).** Composite policies under a frozen
  budget: reversal bundles feedback content + sequential dependence + call
  allocation; no mechanism attribution; ordering claims restricted to the tested
  policies and named models; no typology.
- **P2 (masked-feedback + interpretability caveats).** E5 placeholder-attention
  caveat (protocol wording); interpretability premium is a named-model finding.
- **P3 (extension caveats).** Provider-forced thinking; invalid rates are
  substantial for EVERY model (vf 35/32/45, gr 34/44/38; MiniMax vf highest;
  corrected 2026-07-25 from the earlier higher-than-primary claim);
  transport-error cleaning under the preregistered exogenous rule (one sentence,
  appendix pointer).
- **P4 (scope + verifier-scope disclosures, expanded per prose-review 2026-07-24).**
  Two-model primary family ⇒ existence/non-universality only; single physics
  domain; depth-2 exploratory collapse (difficulty dial) one sentence with
  appendix pointer; certificate-vs-proof boundary restated. PLUS the four
  code-truth disclosures (already stated in §2, recapped here as limitations):
  (i) SU(2) cubic condition = chirality-balance convention (SU(2)³ anomaly
  vanishes identically; Witten Z₂ anomaly not checked; 70/145 fixtures have an
  SU(2) node); (ii) CERTIFIED = "no tested obligation fails" (unknown /
  not-applicable / not-implemented obligations recorded, not blocking);
  (iii) chiral-ring check = bounded classical single-trace proxy (no baryons /
  multi-trace / quantum relations; word length not duality invariant);
  (iv) L=3/L=5 separation applies to the 111 singlet-free fixtures; the two
  configurations coincide for the 34 singlet-containing ones.

## §6 Conclusion, artifact statement, and outlook — 0.3–0.5 pp
- **P1 (conclusion + artifact).** Recap ladder in 2 sentences. Artifact:
  open-source release (GitHub), frozen fixture manifest + protocol + amendment,
  per-run JSONL artifacts, quarantine/audit trail, exact reproduction commands.
- **P2 (outlook — the only QFTCert paragraph).** QFTCert program: DualityCert as
  first cert; candidate future certs (bootstrap, amplitudes, SUSY localization /
  resurgence, string field theory); the EXTRACTED DESIGN PATTERN as the reuse
  surface (not an implemented generic layer); invitation to domain experts.
  Clearly prospective.

## Abstract — written LAST, per blueprint §5 spec
Six-element architecture + the two verbatim converged sentences (E4 sentence;
MiniMax "Separately, …" sentence, first-to-cut rule).

## Appendices
- **A. Physics primer: Seiberg duality and the consistency obligations (NEW,
  converged Rounds 4–5).** Audience: a hep-th reader from another subfield.
  HARD CAP: 800 words or 1.5 rendered pages (whichever first), ≤2 displayed
  equations, no figure/table. EXACTLY seven beats, one paragraph each, with word
  budgets: (1) what the duality asserts, 90–110 w (IR equivalence of two UV
  descriptions; strong–weak only as regime-dependent feature; enumerate the
  ORIGINAL evidence properly here: anomaly matching, chiral-operator/moduli
  matching, mass-deformation consistency — deliberately NOT enumerated in §1); (2) minimal
  quiver/SUSY dictionary, 90–110 w (nodes, arrows/chirals, W, global symmetries,
  R-charges, gauge invariants — enough to read the schema, no dualization
  derivation); (3) necessary-vs-sufficient logic, 70–90 w; (4) 't Hooft anomalies +
  central charge a, 120–140 w (may include a = (3/32)(3TrR³ − TrR); equality uses
  the exact IR R-symmetry; DualityCert checks the encoded assignment, does not
  derive it); (5) superpotential + R-symmetry obligations, 90–110 w (R(W)=2,
  ABJ-freedom; one sentence placing exact R in a-maximization context; verifier
  does NOT perform a-maximization); (6) chiral ring + the bounded check, 110–130 w
  (gauge-invariant chirals mod F-terms; full ring isomorphism vs the finite
  R-graded L=3/L=5 check; bounded pass = partial consistency); (7) physical origin
  of the seeds, 90–110 w (D3-branes at toric CY3 singularities; name-level
  decoding of dP0/dP1/dP2/F0/SPP/C3/Z2×Z2; pointer to benchmark appendix).
  MUST NOT contain: any derivation/proof of the duality; SQCD phase diagram or
  conformal-window survey; Kutasov/adjoint material; a-maximization derivation;
  brane-tiling/toric/mutation derivations; experimental arms/results/numbers;
  QFTCert vision; unimplemented obligations; unqualified strong–weak claims; any
  suggestion that a certificate is sufficient for duality.
- **B. Verifier detail.** Obligation definitions, certificate schema, R-graded
  chiral-ring bounds, L=3/L=5 judge split.
- **C. Benchmark construction.** Seed catalog, mutation/perturbation generation,
  verifier-gating, attrition table, byte-identical regeneration.
- **D. Prompts + policies.** Full prompts, arm pseudocode, copy-cheat guard,
  invalid/abstain definitions.
- **E. Statistical specification.** GEE estimator details, Holm procedure, E3
  results, per-rep tables.
- **F. Per-class descriptive tables.** Per-perturbation-class outcomes per model
  (descriptive only; no inferential claims).
- **G. MiniMax extension detail.** Amendment summary, full clean GEE table,
  invalid decomposition, forced-thinking disclosure, contamination cleaning: 45
  fixture-reps, quarantine artifacts, the two converged disclosure sentences
  (300 s timeout retained; NO_PROXY direct connection).
- **H. Exploratory depth-2 + excluded scouts.** Depth-2 collapse; glm/gemini
  provider-noise exclusions.
- **I. Reproduction + configuration.** Costs, manifests, hashes, exact commands;
  sampling/config minutiae (temperature = provider default, max_tokens 8192,
  client timeout 300 s frozen).

## Cross-cutting rules while writing (blueprint §6 + outline round + physics round)
- Named-model language only; forbidden-phrasings list applies everywhere;
  never "all three models" unqualified.
- MiniMax appears ONLY: Table 1 extension block, Figure 2 extension row (below
  divider), §4 P4 extension unit, §5 P3, abstract sentence, Appendix G, AND (Round 7
  amendment) one §1 P3 design-transparency sentence, verbatim: "Separately,
  \mmcode{} is evaluated under a preregistered extension with its own
  three-hypothesis Holm family (Section 4)." Never "a third model" (invites tier
  flattening); no numbers in §1.
- Every number traced to one of the two frozen GEE artifacts (or e4_summary files).
- §1 is a contract later sections must cash: no framework promises, no taxonomy,
  no primacy claims, "two tested policies under the frozen 11-call cap" wording.
- **Terminology policy (converged Round 4).** Global claim terms, no synonyms:
  "candidate duality claim" (the object), "consistency obligation" (a machine
  check), "necessary condition" (its physics interpretation), "consistency
  certificate" (a pass). NEVER "proof", "verified duality", "validated duality",
  "evidence for duality". E4 policy names fixed: "strategy portfolio" and
  "independent verifier-filtered resampling". Gloss-on-first-use, then
  "superpotential" and "R-charge" may appear bare; "chiral ring" bare only after
  its substantive definition; a-maximization is appendix-only.
- **Physics-integration budget.** Net main-text growth from all surgical physics
  additions ≤100 words (~0.15 pp); if over, cut physics explanation from §2 before
  cutting experimental or system content.
- **Post-draft check (recorded most-likely-wrong).** If a rendered draft reads
  opaque to a hep-th test-reader despite the surgical additions, a compact boxed
  orientation may REPLACE main-text material — never augment it.
