# QFTCert — next-step decision (Claude↔Codex loop)

**Goal of this loop:** converge on the single highest-value next step for QFTCert, plus a concrete plan for it. Decision artifact only — no code changes during the loop.

**Scope guards (repeat every round):**
- This is a PLANNING/DECISION loop. Do NOT edit any project source files, tests, or configs. Only edit THIS log file (`next_step_discussion.md`).
- Stay within QFTCert scope. The decision is about the next research/engineering step, given the state below.
- Be concrete and adversarial. End each round with the single point most likely to be wrong.

---

## Shared state (read this first)

- **Project:** QFTCert = an auditable verifier ("certificates, not proofs") for AI-generated claims about Seiberg/IR dualities of SQCD-like quiver gauge theories. Propose→check→repair. NOT a benchmark/eval (that's an explicit non-goal); the eval work is the *diagnosis* side, QFTCert is the *verification substrate*.
- **Verifier capability (current):** certifies duality claims across **6 seed families** — dP_0 toric, F_0 phase II, C^3/(Z_2×Z_2), dP_1, dP_2 phase I, SPP. Obligations include gauge & gauge-global mixed anomaly cancellation, global anomaly matching, magnetic superpotential consistency, central-charge (TrR^3) matching, and a bounded chiral-ring consistency check (length- or R-graded). Irrational-superconformal-R seeds (dP_1, dP_2) certify via a consistent-R propagation path (no a-maximization).
- **Generation harness (experiments pkg):** `generate-fixtures` builds verifier-gated (electric, candidate) pairs per (depth × perturbation-class) cell. Perturbation classes: positive, drop_w_term, flip_w_sign, r_charge_perturb, rank_perturb, trivial_rank, wrong_pair. Negatives are kept only if the verifier actually FAILS them (silent misses → attrition). **Only depth=1 mutation is implemented**; depth≥2 cells route to attrition.
- **Just built + committed:** an all-seed **depth-1 smoke** (`configs/smoke.json`): 68 fixtures = 14 positives (all 6 families, incl. dp1/dp2) + 54 negatives across all classes. Dryrun single-shot loop verified end-to-end offline.
- **Headline empirical finding (Exp 1 pilot, Sonnet 4.6, depth-1 blind detection, 30-fixture MVP, dP_0+F_0 only):** the model collapsed to a **degenerate constant "not_dual" policy** — overall accuracy 80% = the negative-class prior; positives 0/6; negatives 24/24. Interpretation so far: blind depth-1 detection with sanitized provenance is structurally too hard for the bare model → motivates verifier-in-the-loop scaffolding.
- **LLM-eval harness status:** single-shot detection AND diagnosis are both wired (`run-single-shot --tasks detection,diagnosis`); a repair-loop (v2) exists in plan. Diagnosis = model predicts which obligation failed, scored vs the verifier's `failed_obligations`.
- **Constraints/values:** the FP job offer is in hand, so work proceeds at a relaxed but **high-quality, paper-oriented** pace. The user is a hep-th physicist with deep domain command but does not write code (Claude-Code-driven). Token/compute is not the binding constraint; scientific value + paper-readiness is.

## Candidate next steps (the menu)

1. **Phase 2c-b diagnosis loop** — LLM predicts which verifier obligation failed on a not-dual pair, scored vs `failed_obligations`. Reuses fixtures + harness (already wired). Adds a second scientific axis ("can it explain *why* not, not just *whether*").
2. **depth≥2 mutation chains** — compose multiple single-node Seiberg moves to generate "unfamiliar but genuinely dual" positives, to defeat LLM memorization and harden the anti-memorization claim.
3. **Real-API run of the all-seed smoke** — fresh signal: does the degenerate-policy finding generalize from 2 families to 6? Cheap (~$1–3, 68 fixtures).

---

### Round 1 — Claude

**Position: sequence = (A) a cheap "is the headline finding real?" measurement pass FIRST, then (B) Phase 2c-b diagnosis as the main build. Defer depth≥2.**

Reasoning:

1. **De-risk before you build on it.** The whole motivation for scaffolding (2c-b/2c-c) rests on ONE finding: bare-model detection is degenerate. But that finding is currently from a single model (Sonnet 4.6), a single prompt/format, and 2 families. Building a diagnosis layer on top of a headline that might be a *prompt/format/model artifact* is the classic mistake. So step #1 is a small ablation pass that does double duty:
   - Run the **all-seed smoke through a real API** (candidate #3) — hardens the empirical base from 2→6 distinct geometries. "Degenerate across 6 families" is a far stronger paper claim than "degenerate on dP_0+F_0," and rules out a 2-family artifact.
   - Add **2–3 cheap ablations** in the same pass: (a) a stronger model (Opus) to check it's not a Sonnet-specific weakness; (b) a reasoning-allowed / chain-of-thought prompt variant to check the degeneracy isn't induced by the forced single-shot structured schema; (c) optionally a variant that hands the model the explicit obligation list to check, to separate "doesn't know what to check" from "can't check it."
   - Outcome: either the finding survives (now paper-grade and robust) or it partially breaks (which would *redirect* the whole next phase — far better to learn that now than after building 2c-b).

2. **Then build 2c-b diagnosis as the main next step.** It is the highest-value BUILD because: it reuses the entire fixture set + harness (`--tasks diagnosis` already wired), it adds an *independent* scientific axis (failure-mode classification vs binary detection), and it directly feeds the project's thesis (verifier-as-teacher / propose→check→repair). Diagnosis is also a richer, more publishable signal than a second binary number.

3. **Defer depth≥2.** It's rigor armor for the anti-memorization claim, but it's premature: the model already fails the *depth-1* case. Making positives harder while the easy case is unsolved adds benchmark difficulty without new signal. Build it when the paper's benchmark section needs anti-memorization robustness, not now.

**Targeted questions for Codex:**
- Q1. Is "de-risk the finding via a cheap ablation pass" genuinely the right #1, or is it over-caution — should we treat detection-degeneracy as settled and go straight to building 2c-b? Where's the line between due diligence and stalling?
- Q2. 2c-b diagnosis design: how do we avoid the confound that failure-mode classification is trivially pattern-matchable from surface features (e.g., "a dropped W term" is visually obvious)? And how should we score fixtures with *multiple* failed obligations fairly (multi-label vs single-label)? What's the cleanest scoring that maps to verifier ground truth?
- Q3. Is depth≥2 actually more valuable than I'm giving it credit for — e.g., is the depth-1 degeneracy itself suspect *because* depth-1 positives might be memorized/guessable, so that only depth≥2 gives an honest detection signal? (i.e., could depth≥2 be a *prerequisite* for trusting the headline, not just armor?)
- Q4. Am I missing a higher-value option not in the menu — e.g., jumping to the 2c-c repair loop, a multi-model panel as the primary result, or strengthening the verifier's coverage/soundness itself (the substrate) rather than more LLM experiments?

### Round 1 — Codex

**Q1. Cheap de-risk pass first? Yes, but keep it narrower than proposed.**  
Run the all-seed smoke live before building more story on the 2-family pilot. The harness makes this cheap and low-risk: `configs/smoke.json` is already depth `[1]`, all seven fixture classes, `n_per_cell=1`, six families via `default_seed_specs()`, and `run-single-shot --tasks detection,diagnosis` is wired. This is not stalling if the acceptance rule is predeclared: one live Sonnet run, optionally one stronger-model run, then decide. Correction: prompt/CoT ablations are not as "cheap" as model/config ablations because the detection/diagnosis prompts and structured schemas are code-level artifacts; doing them immediately risks turning a measurement pass into benchmark redesign.

**Q2. Diagnosis confound / scoring.**  
The clean primary target is already the right one: verifier obligation categories from `failed_obligations`, collapsed by `gold_categories()` into a multi-label set over `anomaly`, `superpotential`, `r_charge`, `chiral_ring`. Score exact set match as the harsh primary metric and macro-F1 as the forgiving secondary metric; do not force single-label, because one perturbation can fail multiple verifier obligations. To reduce surface-pattern confounding, separate reporting sharply: primary = obligation category; secondary = `suspected_cause` / perturbation class. The current diagnosis prompt asks for both in one call, so a model may anchor on visible edits like dropped W terms. For paper claims, emphasize primary category performance and stratify by perturbation class/source; treat suspected cause as diagnostic color, not headline evidence.

**Q3. Depth>=2 value.**  
Depth>=2 is not a prerequisite for trusting the current degenerate-policy headline. If a model predicts `not_dual` for every depth-1 pair, the immediate failure is base-rate exploitation, not memorization. Harder positives will not fix that inference. Depth>=2 becomes important when claiming robustness against memorized Seiberg moves or when positives start being solved. Correction to the shared-state framing: `generation.py` now attempts `depth >= 2` chains through `_attempt_chain()` with retries and later enforces empty-cell completeness/attrition; it is not simply a hard route-to-attrition path from the code inspected. The practical question is empirical yield, not whether the code path exists.

**Q4. Missing higher-value option?**  
Do not jump to repair yet. Repair is the thesis endpoint, but without hardened detection and diagnosis baselines it is harder to interpret whether verifier feedback adds intelligence or just patches obvious corruptions. A broad multi-model panel is also premature beyond one stronger-model sanity check. Verifier soundness work is always valuable, but current next-step value is empirical: confirm the blind-detection failure across the all-seed smoke, then run/report diagnosis on the same manifest. That gives a coherent paper arc: blind detection collapses; verifier-grounded diagnosis is measurable; repair is motivated next.

**Recommended sequence:** live all-seed smoke detection+diagnosis on Sonnet; optional one stronger model; freeze a short result memo; then build/iterate Phase 2c-b reporting, not depth>=2.

Most likely wrong: I may be underweighting depth>=2 if reviewers would reject any depth-1-only LLM result as too close to memorized textbook dualities, even when the observed failure mode is constant `not_dual`.

### Round 2 — Claude

Strong convergence. I accept three of your corrections and add one independent check that sharpens the depth≥2 verdict.

**Accept (Q1):** narrow the de-risk pass to *measurement, not redesign*. First pass = model/config ablations only: one live Sonnet run + one stronger-model (Opus) run on `configs/smoke.json` as-is. Prompt/CoT and "hand it the obligation list" variants are benchmark *redesign* (code-level prompt/schema artifacts) → split off into a separate follow-up study, only if the finding survives. Good catch.

**Accept (Q2):** diagnosis scoring = primary obligation-category multi-label via `gold_categories()` over {anomaly, superpotential, r_charge, chiral_ring}, **exact-set-match (harsh primary) + macro-F1 (secondary)**, never single-label; report `suspected_cause`/perturbation-class as *secondary color*; stratify by perturbation class + family so visually-obvious edits (drop_w_term) are separated from subtle ones (r_charge_perturb).

**Add — reporting fix for the headline (this is the real Q1 risk):** the "80% accuracy" framing is itself the artifact. The smoke set is 14 pos / 54 neg (79% negative), so a constant `not_dual` policy scores ~79% by construction. Predeclare the live-run reporting as **positive recall, negative recall, balanced accuracy, per-family positive recall, and an explicit constant-policy flag** — never raw accuracy. Decision rule for the pass: if both models stay ~zero positive recall across all 6 families → headline robust → proceed to diagnosis reporting (B). If positive recall is non-trivial for some model/family → that *redirects* the phase.

**Q3 — independent check run (not just our agreement):** I generated depth=2 and depth=3 offline. **Both yield ZERO certified positives** — every cell routes to attrition (`single_step_mutation_failed` ~9, `adjacent_verifier_failed` ~5). So your "code path exists, question is yield" correction is right, and the yield is currently *nil*. This upgrades my verdict: depth≥2 is not "defer because premature," it's **blocked** — making it produce any data is a separate mutation-engine project (compose a 2nd Seiberg step that survives adjacent-step verification). It cannot be the next step regardless of its paper value.

**This also dissolves your "most likely wrong":** reviewers can't demand depth≥2 results that don't exist, and the constant-`not_dual` failure is model-*internal* — the model recognizes *no* dual (memorized textbook ones included), so "depth-1 positives are too close to memorized dualities" doesn't bite: it isn't getting the memorizable ones right either. depth≥2 only starts to matter once positive recall is non-zero.

**Q4 — accept:** no repair, no broad panel, no verifier-soundness detour now. The arc "blind detection collapses → verifier-grounded diagnosis is measurable → repair motivated" is the right spine.

**Converged plan:**
- **A. De-risk pass (measurement):** live `run-single-shot --tasks detection,diagnosis` on `configs/smoke.json` with Sonnet, then Opus. Report balanced-accuracy / positive-recall / per-family / constant-policy flag. Freeze a short "Exp 2 all-seed" memo. (No prompt/schema changes.)
- **B. Phase 2c-b diagnosis reporting:** score the diagnosis outputs from A (primary obligation-category multi-label, stratified). Publishable contrast either way.
- **Defer:** depth≥2 (blocked — zero yield; separate engine project), 2c-c repair, prompt/CoT study, multi-model panel beyond the one Opus sanity run.

Question: do you confirm convergence, or does the *cost ordering* change anything — should A run Opus-only (skip Sonnet, since Sonnet's degeneracy is the prior finding) to save a call, or is the Sonnet re-run on the new 6-family set load-bearing for the "generalizes across families" claim?

### Round 2 — Codex

Converged. My only remaining correction is wording, not sequence: say depth>=2 is **blocked in the current generator/harness**, not intrinsically impossible or scientifically unnecessary. The offline result you report (depth 2/3 yield zero certified positives, attrition via `single_step_mutation_failed` / `adjacent_verifier_failed`) makes it non-actionable as the next step. But paper language should frame this as an engineering limitation/next robustness project, not as something reviewers "cannot demand."

**Cost ordering: run Sonnet + Opus, not Opus-only.**  
Sonnet is load-bearing because the prior headline is specifically "Sonnet 4.6 collapsed on dP0/F0." To claim the finding generalizes from 2 families to 6, you need the same model/prompt/schema on `configs/smoke.json`; Opus-only changes two variables at once (model and family coverage), so it cannot answer that question cleanly. Opus is the stronger-model sanity check: if Sonnet stays constant-`not_dual` but Opus gets positive recall, the story becomes model-capability-sensitive rather than universal. Given 68 fixtures and cost not binding, saving the Sonnet rerun is false economy. Order: Sonnet first; score; then Opus unless Sonnet already produces a surprising redirect that warrants stopping.

**CONVERGED — agreed plan**
- Pass A is measurement only: no prompt/schema/config redesign.
- Run live `run-single-shot --tasks detection,diagnosis` on `configs/smoke.json` with Sonnet first.
- Report positive recall, negative recall, balanced accuracy, per-family positive recall, and a constant-policy flag; raw accuracy is secondary.
- Then run the same smoke pass with Opus as the stronger-model sanity check.
- Decision rule: near-zero positive recall across models/families hardens the blind-detection-collapse claim.
- If positive recall appears for a model/family, pause and redirect around that signal before building more.
- Reuse the same outputs for Phase 2c-b diagnosis scoring.
- Diagnosis primary metric: verifier obligation-category multi-label exact set match; macro-F1 secondary.
- Treat `suspected_cause` / perturbation class as secondary analysis, not the headline.
- Defer depth>=2, repair, prompt/CoT ablations, and broad model panels.

Most likely wrong: Opus may be too different from Sonnet to serve as a clean "stronger-model sanity check" rather than opening a broader multi-model design question.
