# Cross-model direction flip in per-class feedback effects — Claude↔Codex convergence loop

Deliverable: a converged decision on (a) paper narrative, (b) honest statistical
presentation, (c) which additional experiments/analyses are worth running.
This log is the working transcript. Rounds appended in order.

## Background (verifiable on disk)

QFTCert repair-loop experiment: an LLM must repair a deliberately broken 4d N=1
Seiberg-duality claim; a symbolic verifier (anomaly matching, W R-charge, central
charges, bounded chiral ring) judges every candidate. Success = final verifier
CERTIFIES (stricter final check: chiral-ring length L=5 vs feedback-time L=3,
anti-gaming). Fixture set: n=145 depth-1 repairable fixtures, byte-identical across
all models (deterministic regeneration, seed 20260715), 4 perturbation classes:

- drop_w_term (n=38): a superpotential term was deleted (model must reconstruct it)
- flip_w_sign (n=13): one W coefficient sign flipped
- r_charge_perturb (n=52): R-charges perturbed (rational values)
- rank_perturb (n=42): a gauge-node rank changed

Arms (all K<=5 rounds, full_theory edit mode, config configs/repair_d1_ft.json;
detailed-feedback variant configs/repair_d1_ft_detailed.json):

- single_shot_repair (ss): 1 attempt, no feedback
- generic_retry (gr): up to 5 attempts, only told "wrong, try again" (verifier used
  as a FILTER/judge but its content is hidden)
- verifier_feedback medium (vf): up to 5 attempts, told WHICH obligation category
  failed (e.g. "anomaly matching failed", "superpotential R-charge failed")
- verifier_feedback detailed (det): same but with detailed residual-level feedback

On-disk artifacts THIS session (per-fixture JSONL + summary.json, readable):
- runs/experiments/repair_d1/runs/qwen2_verifier_feedback/   (qwen-plus, clean)
- runs/experiments/repair_d1/runs/qwen2_generic_retry/       (qwen-plus, clean)
- runs/experiments/repair_d1/runs/qwen2_vf_detailed/         (IN FLIGHT, partial)
- runs/experiments/repair_d1/runs/glm5_single_shot_repair/   (glm-5.2, clean)
- runs/experiments/repair_d1/runs/glm5_verifier_feedback/    (IN FLIGHT, partial)
- runs/experiments/repair_d1/runs/qwen_single_shot_repair/   (qwen-plus ss, clean)
Older runs (glm_* = zai-glm-4.7 via Cerebras free tier: PROVIDER NOISE, do not use;
gemlite_* = gemini-flash-lite: 100% invalid, thinking-overflow suspected, do not use).

DeepSeek (deepseek-chat) d1 full_theory results were run 2026-07-15; the per-fixture
records were LOST to a tmp-cleaner wipe. Only aggregates survive (recorded in project
memory the same evening, before the wipe; trusted but not re-derivable):

- ss 13/145 = 9.0%; gr 32/145 = 22.1%; vf 23/145 = 15.9%; det 32/145 = 22.1%
- per-class success (vf% vs gr%): drop_w 16 vs 8; flip_w 23 vs 15; r_charge 17 vs 31;
  rank 12 vs 26
- det redistribution vs vf-med: r_charge 17->25, rank 12->31, drop_w 16->11,
  flip_w 23->15
- union: vf-med ∪ det = 47/145 (32.4%); ∪ gr = 59/145 (40.7%)
- det vs ss: Fisher p = 0.0016. gr(32) vs vf(23): one-sided p ≈ 0.07 (gr AHEAD).

qwen-plus (qwen2_*, this session, clean, per-fixture on disk):

- ss 13/145 = 9.0% (older qwen_single_shot_repair run; coincidentally same count as
  deepseek); vf 21/145 = 14.5%; gr 19/145 = 13.1%; det in flight
- Paired McNemar vf vs gr (n=145): both=10, vf_only=11, gr_only=9, neither=115,
  exact p = 0.82. success@1->@5 slopes IDENTICAL (+5.5pp both arms).
- Per-class paired (vf_only : gr_only discordants, exact McNemar):
  - rank_perturb:      vf 10/42 vs gr 3/42;  discordant 7:0,  p = 0.016
  - r_charge_perturb:  vf  8/52 vs gr 11/52; discordant 2:5,  p = 0.45
  - drop_w_term:       vf  2/38 vs gr  4/38; discordant 1:3,  p = 0.63
  - flip_w_sign:       vf  1/13 vs gr  1/13; discordant 1:1,  p = 1.0
- invalid-JSON rate: vf 36%, gr 46%.

glm-5.2 (Zhipu direct, thinking disabled): ss 7/145 = 4.8% (invalid 26%, abstain 7%,
verified clean: zero 429s). vf/gr/det arms INTERRUPTED by Zhipu account balance
exhaustion (429 "insufficient balance" mid-run): 52/145 genuine vf fixtures banked
(6 CERTIFIED among them; 93 poisoned records filtered out, will rerun via --resume
after the user tops up). Third-model adjudication is DELAYED, not hours away.

## The contradiction

The DeepSeek run suggested a tidy two-regime law we planned to feature: "parameter
errors (rank, R-charge: small-integer/rational values) are cheap to fix by blind
resampling diversity; W-structure errors need feedback to localize." qwen-plus breaks
it: rank_perturb flips HARD in the opposite direction (feedback 7:0 over blind retry,
p=0.016 unadjusted), drop_w_term flips the other way (gr ahead), flip_w washes out,
and only r_charge agrees (gr ahead in both). Even the OVERALL direction disagrees:
deepseek gr>vf (p≈0.07), qwen vf≈gr (p=0.82).

### Round 1 — Claude

My proposed resolution, for your attack:

**P1 (narrative).** Demote the two-regime law from claim to single-model observation.
The paper's robust claims become: (i) multi-round verifier loop >> single-shot for
every above-floor model (qwen vf 21 vs ss 13; deepseek det 32 vs ss 13, p=0.0016;
glm pending); (ii) the verifier powers BOTH rejection sampling (gr) and feedback (vf)
— which one wins, and on which error class, is MODEL-DEPENDENT; this heterogeneity
is itself a finding (feedback redistributes success across classes in a
model-specific way; coarse category feedback can anchor one model and guide another);
(iii) the robust exploitation of the heterogeneity is the verifier-gated ensemble
(run all strategies, keep anything the verifier certifies — deepseek 40.7% = 4.5x
single-shot; compute the qwen union once det lands). The original thesis sentence
"verifier feedback improves weak-model search" must be weakened to "verifier-gated
iteration improves weak-model search; the marginal value of feedback CONTENT over
blind iteration is heterogeneous across models and error classes."

**P2 (statistics).** (a) Primary endpoint per model: overall paired vf-vs-gr McNemar
+ vf-vs-ss; report exact p, discordant counts. (b) Class-level effects: present as an
exploratory forest plot (per model x class: success-rate difference with 95% CI,
paired where records exist), explicitly labeled exploratory, Bonferroni or
Benjamini-Hochberg within each model's 4 classes (qwen rank p=0.016 -> 0.064
Bonferroni; report both raw and adjusted). (c) The cross-model flip: test the
model x arm interaction per class formally where per-fixture data exists on both
sides. PROBLEM: deepseek per-fixture records are lost, so any deepseek-side paired or
interaction test is impossible today. Options: rerun deepseek d1-FT 3 arms (~¥2,
balance ¥18) to regain per-fixture records AND get a same-model replicate to
estimate run-to-run sampling variance (provider default temperature, so reruns are
not deterministic); OR present deepseek per-class numbers as unpaired 2x2 aggregates
with Fisher CIs and clearly say the interaction claim is qualitative. I propose the
rerun (it upgrades both the stats AND gives a variance anchor).
(d) Multiplicity honesty: the two-regime law was invented POST HOC on deepseek data;
any confirmation must be on fresh data (glm, minimax) with the hypothesis stated
first. Say this in the paper.

**P3 (experiments, priority order).** (1) glm-5.2 vf/gr/det (in flight, free):
third model; predict NOTHING, just report where its per-class pattern lands.
(2) deepseek d1-FT rerun x1 (possibly x2) for per-fixture records + variance anchor.
(3) qwen det (in flight) completes the qwen 4-arm table + qwen union number.
(4) MiniMax suite (planned) = 4th model. (5) Optional mechanism probe: per-round
instrumentation storing WHICH JSON paths each candidate edit touched, so "blind qwen
never edits ranks; category feedback makes it edit ranks" becomes measurable instead
of speculative. Add the instrumentation now, use it in all future runs; do NOT
retro-claim mechanism for existing runs.

**P4 (what I refuse to conclude).** I will not average the two models' per-class
effects into one number (masking a sign flip), and I will not pick whichever model
supports the nicer story. If glm lands a THIRD distinct pattern, the paper says
"model-specific" with three exhibits.

Questions for you:

**Q1.** Is P1's reframing the right level of retreat? Too timid (the qwen rank 7:0 is
strong; maybe feedback-helps-rank is real and deepseek is the outlier) or not
cautious enough (maybe ALL per-class signals at n=13-52 are noise and the paper
should drop class-level claims entirely)?

**Q2.** For the cross-model interaction with one side's per-fixture data lost: is the
deepseek rerun the right call, or is there a legitimate aggregate-only interaction
test (e.g. difference-in-differences on 2x2x2 counts with bootstrap over fixtures on
the qwen side only) that would let us skip it? Is ONE rerun enough, or do we need >=2
to say anything about run-to-run variance (single run per condition everywhere is a
weakness a referee will hit)?

**Q3.** Sample-size reality check: with per-class n in {13, 38, 42, 52} and success
rates 5-30%, what effect sizes are even detectable at alpha=0.05? Should the paper
pool the two parameter classes (r_charge+rank, n=94) and the two W classes (n=51) as
PRE-DECLARED families instead of 4 separate classes? Does the qwen rank 7:0 survive
any honest multiplicity treatment (it is 1 cell out of 4 classes x 3-4 pairwise arm
contrasts x >=2 models)?

**Q4.** The overall-direction disagreement (deepseek gr>vf p≈0.07 vs qwen vf>gr
p=0.82): the honest top line seems to be "feedback content ≥ blind retry is NOT
established at K=5; both are large lifts over single-shot." Do you agree, or is
there a defensible statistical statement that preserves a positive feedback-content
claim (e.g. via the detailed arm: deepseek det 32 ties gr 32; det front-loads
success@1=11.7%)?

**Q5.** Any additional CHEAP analysis on existing artifacts that would sharpen the
story? (We have per-fixture rounds logs with per-round action/apply_error/
feedback_status for qwen2 and glm5; edit_distance; verifier_calls; invalid rates.
E.g. rounds-to-success distributions, invalid-rate-by-class, whether vf's wins
concentrate in fixtures where gr produced INVALID (format rescue) vs VALID-but-wrong
(semantic rescue).)

End of Round 1. The single point I most expect you to attack: proposing a deepseek
rerun as "variance anchor" while planning to keep the ORIGINAL deepseek numbers in
the paper if the rerun disagrees with them — I have not decided what to do if the
rerun lands a different per-class pattern, and "keep both" invites cherry-picking
suspicion.

### Round 1 — Codex

Scope-guard confirmation: I read the full discussion, both permitted configs, the
full repair harness, and the relevant raw qwen JSONL/summary artifacts. I made no
API calls and ran no experiments; the computations below are analyses of existing
records. I treat every DeepSeek aggregate as an unverifiable input. This reply is
the only edit, and it replaces only the requested placeholder.

#### Independent qwen recomputation

[FLAG] I joined arms by `fixture_id`, rather than trusting either summary. Each of
vf, gr, and ss has 145 rows, 145 unique IDs, no duplicate IDs, identical ID sets,
and no cross-arm perturbation-class mismatches. In `repair.py`, `success=True` only
when the feedback verifier certifies and the stricter final verifier also certifies;
thus the raw `success` field is the endpoint. Summing it gives vf=21, gr=19, ss=13.
The class denominators are 38, 13, 52, and 42 as stated.

[FLAG] Here is my vf-vs-gr matched table. I used the two-sided exact McNemar value

\[
p=\min\left\{1,2\sum_{j=0}^{\min(b,c)}{b+c\choose j}2^{-(b+c)}\right\},
\]

where \(b\) is vf-only and \(c\) is gr-only.

| class | n | vf successes | gr successes | both | vf only \(b\) | gr only \(c\) | neither | exact p |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| all | 145 | 21 | 19 | 10 | 11 | 9 | 115 | 0.823803 |
| drop_w_term | 38 | 2 | 4 | 1 | 1 | 3 | 33 | 0.625000 |
| flip_w_sign | 13 | 1 | 1 | 0 | 1 | 1 | 11 | 1.000000 |
| r_charge_perturb | 52 | 8 | 11 | 6 | 2 | 5 | 39 | 0.453125 |
| rank_perturb | 42 | 10 | 3 | 3 | 7 | 0 | 32 | 0.015625 |

The log's qwen counts and McNemar values are therefore reproducible. The qwen
vf-vs-ss table is both=6, vf-only=15, ss-only=7, neither=117, giving exact
\(p=0.133801\); gr-vs-ss is 5,14,8,118, giving \(p=0.286279\). Therefore neither
qwen iterative arm has an individually established lift over ss at two-sided
alpha 0.05 in this single run.

[BLOCKER] The rank result cannot carry the proposed mechanistic or confirmatory
weight. First, four-class Bonferroni and BH both change 0.015625 to 0.0625. A
family of 4 classes x 3 arm contrasts x 2 models would change it to 0.375 by
Bonferroni; including a fourth arm makes the family larger. Second, the 42 rank
fixtures are nested within 14 theory/node bases. The seven vf-only wins occur in
only four bases, with cluster differences +2,+2,+2,+1; a crude exact sign test on
the four nonzero cluster differences is \(2/2^4=0.125\). Fixture-level McNemar
treats correlated perturbations from one base as independent. Third, 6/7 rank
vf-only wins have `gr.invalid=true`. This is evidence for an arm difference in
end-to-end success, but it does not identify “feedback teaches rank editing.”

[FLAG] Invalid-output decomposition strengthens that last point. Of the 11 vf-only
wins overall, 9 face an invalid gr record; of the 9 gr-only wins, 3 face an invalid
vf record. The rank split is 6/7 versus 0/0. Overall invalid counts are 52/145 for
vf (44 unparseable tool arguments, 8 schema-invalid theories) and 67/145 for gr
(57 unparseable, 10 schema-invalid). Calling this merely an “invalid-JSON rate” is
imprecise because it includes schema-valid JSON that is an invalid theory.

#### Attack on P1-P4

[BLOCKER] **P1(i)** overstates robustness. For qwen the observed absolute lifts are
only 8/145=5.5 pp (vf-ss) and 6/145=4.1 pp (gr-ss), with the paired exact p-values
0.134 and 0.286 derived above. The DeepSeek det-vs-ss claim and its reported
\(p=0.0016\) depend entirely on lost, unverifiable DeepSeek aggregates. “For every
above-floor model” is consequently not an inferentially supported result. The
defensible sentence is: “In the recorded qwen run, both K=5 arms had higher point
success than single shot; no arm difference was detected.”

[BLOCKER] **P1(ii)** turns an unresolved contradiction into a finding. A model x arm
interaction requires verifiable outcomes on both model sides plus repeated model
draws if the intended claim concerns models rather than these two run instances.
The DeepSeek side is an unverifiable aggregate, while qwen's apparent rank effect
fails the stated four-class correction, clusters in four bases, and is mostly an
invalid-output contrast. Use “patterns differed across the recorded model-runs” as
description; reserve “model-dependent” or “feedback anchors/guides” as hypotheses.

[BLOCKER] **P1(iii)** confounds coverage with budget. For qwen, vf union gr is
30/145; adding ss gives 34/145=23.4%, versus ss 13/145. But those three arms consume
1,071 model rounds and 2,917 verifier calls, versus 145 and 387 for ss: 7.39x the
model calls for 2.62x the successes. The DeepSeek 59/145 union and “4.5x” claim are
also unverifiable aggregates. An ensemble result needs an equal-budget baseline or
must be labeled a compute-scaled coverage result, not robust exploitation.

[BLOCKER] **P2(a-b)** cannot retroactively declare several discovered contrasts
“primary.” The design needs a hierarchy: gr-vs-ss estimates the package of extra
attempts plus the generic failure message; vf-vs-gr estimates feedback content;
vf-vs-ss mixes both. Report paired risk differences and intervals, not p-values
alone, and define one multiplicity family before fresh runs. Because fixtures share
14 theory/node bases, add a base-cluster bootstrap or randomization sensitivity
analysis; with only 14 clusters, label its uncertainty. A high-salience forest plot
is not made confirmatory merely by the word “exploratory.”

[FLAG] **P2(c-d)**: an aggregate-only logistic interaction or difference-in-
differences can be computed only by treating arms as independent binomials and
trusting the unverifiable DeepSeek marginals. That discards the matched-fixture
covariance and cannot be repaired by bootstrapping qwen alone. It is a sensitivity
analysis, not a substitute for records. The post-hoc origin of the two-family law
must be disclosed, and any confirmatory test must use a frozen hypothesis and fresh
complete runs.

[BLOCKER] **P3(2)**: one DeepSeek rerun is not a variance anchor. It yields one new,
auditable model draw; it does not estimate run-to-run variance. Two draws give only
one variance degree of freedom. If variance is part of the claim, use at least
three fresh complete repetitions per model x arm (more if affordable), including
qwen rather than replicating only DeepSeek. Freeze the rule now: lost-record
DeepSeek aggregates remain a legacy descriptive result; all fresh complete runs
enter the primary analysis regardless of agreement. This removes the proposed
option to retain whichever pattern is attractive.

[FLAG] **P3(1,3-5)**: do not analyze the interrupted glm prefix as though it were a
random 52-fixture sample; fixture order is structured, so interruption can induce
class/base selection. Resume to a complete run and record the interruption. Finish
qwen det before defining its role. Path instrumentation should store each round's
pre/post changed-path set, candidate validity, raw parse-failure category, token
usage, and provider sampling parameters. Existing `RepairRoundLog` stores no
candidate snapshot or changed paths, so final `edit_distance` cannot recover the
mechanism retrospectively.

[FLAG] **P4** is too absolute about averaging. A naive pooled class effect would
mask heterogeneity, but a prespecified hierarchical model with arm slopes by model
can estimate both an average and heterogeneity once enough models and repeated
runs exist. With two single run-instances, do neither. Even a third distinct glm
pattern would support only “heterogeneity among evaluated model-runs,” not the
population claim “model-specific.” Any statement involving the current DeepSeek
pattern remains dependent on unverifiable aggregates.

#### Answers to Q1-Q5

[BLOCKER] **Q1 — retreat further.** Keep the four class tables as descriptive,
exploratory diagnostics; drop class-level directional and mechanism claims from
the main conclusions. The qwen rank 7:0 is not strong after multiplicity,
base-clustering, and invalid-output decomposition. The cross-model heterogeneity
claim is a preregistered hypothesis for fresh runs, because its DeepSeek premise is
currently unverifiable.

[FLAG] **Q2 — rerun only if the interaction matters.** There is no aggregate-only
test that reconstructs the missing paired covariance. An independent-binomial
interaction is legitimate only for that changed sampling model and only if one
accepts the unverifiable DeepSeek counts; state it as sensitivity analysis. One
fresh rerun is enough to obtain auditable pairs for that new run, but not enough to
claim run variance. If budget precludes repeated runs across every model-arm, say
explicitly that inference is conditional on one stochastic draw rather than
calling a DeepSeek-only repeat a variance estimate.

[FLAG] **Q3 — current power is poor and pooling must be prospective.** For a paired
difference with discordance probability \(q\), an 80%-power normal approximation at
two-sided alpha 0.05 is
\(\mathrm{MDE}\approx(1.96+0.84)\sqrt{q/n}\). For \(q=0.10\) to 0.30, this gives
MDE ranges of 24.6-42.5 pp at n=13, 14.4-24.9 pp at n=38, 13.7-23.7 pp at n=42,
and 12.3-21.3 pp at n=52; exact low-count tests are more discrete. Pooling
parameter classes and W classes is defensible only as a scientifically fixed
family for fresh data. On current qwen data it does not rescue the law: parameter
classes have vf-only:gr-only=9:5, exact \(p=0.42395\), and W classes 2:4,
\(p=0.6875\). Rank's 0.015625 becomes 0.0625 across four classes and 0.375 across
the illustrative 24-test family, before clustering.

[BLOCKER] **Q4 — “greater than or equal” and “large lifts” are not established.**
Failure to reject vf=gr at \(p=0.824\) is neither equivalence nor noninferiority;
those require a prespecified margin. State “no detected qwen difference between
feedback content and blind retry at K=5.” Qwen's vf-ss and gr-ss exact values are
0.134 and 0.286, so call them observed increases, not established large lifts. A
DeepSeek detailed-arm tie and front-loaded success@1 cannot preserve a positive
content claim: those are unverifiable aggregates, and success@1 comes from a
separate stochastic call that already receives arm-specific feedback before its
first edit.

[FLAG] **Q5 — run these cheap existing-artifact analyses.** First, publish the
discordant-win invalid decomposition above; any both-valid subset analysis must be
labeled descriptive because validity is post-treatment. Second, report clustering
by theory/node and leave-one-base-out effects. Third, use competing-outcome curves
by round (certified, invalid termination, still at risk): qwen vf has 13 successes
at round 1 and 8 later; gr has 11 at round 1 and 8 later, while invalid terminations
are 52 versus 67. Fourth, stratify invalid output by class: vf/gr invalid counts are
drop 15/19 of 38, flip 6/8 of 13, R-charge 18/22 of 52, rank 13/18 of 42. Fifth,
budget-normalize unions using total model calls and total verifier calls. The
summary's `verifier_calls_per_success` is not that metric: `score_repair` sums calls
only over successful records and excludes wasted calls on failures.

[FLAG] **Single point in this reply most likely to be wrong:** I may be too severe
in treating the 14 shared theory/node bases as inferential clusters; if the intended
estimand is strictly the fixed 145 prompts and independent model-call randomness,
fixture-level McNemar is a reasonable finite-benchmark analysis, although it still
does not justify generalization to new fixtures or models.

### Round 2 — Claude

**Accepted (folding into the position):**

A1. qwen iterative-vs-ss is NOT established (your recomputed vf-ss p=0.134,
gr-ss p=0.286 accepted). "For every above-floor model" is retracted. Claims become
point estimates + CIs; nothing "established" from a single run per condition.

A2. The rank 7:0 is demoted to a descriptive diagnostic. Your decomposition is the
decisive part: 6/7 rank vf-only wins sit on gr-invalid records, so the honest
description is "under category feedback qwen stayed on-format where blind retry
collapsed", a validity-survival contrast, not "feedback teaches rank editing".
Base-clustering (7 wins in 4/14 bases, cluster sign test p=0.125) goes next to it.

A3. Ensemble reframed as compute-scaled coverage unless an equal-budget control
exists. I propose adding one (protocol E4 below) rather than dropping the claim.

A4. Your frozen-rule text is adopted verbatim: legacy lost-record DeepSeek
aggregates stay a descriptive exhibit; ALL fresh complete runs enter the primary
analysis regardless of agreement. No selective retention.

A5. No analysis of the interrupted glm 52-fixture prefix; it resumes to completion
after the account top-up and enters as a complete run with the interruption logged.

A6. Instrumentation spec adopted before any fresh run: per-round changed-JSON-path
set, candidate snapshot hash, parse-failure category, token usage, sampling params
(temperature/top_p as sent), provider request id where available.

A7. Harness metric fix queued: `verifier_calls_per_success` currently sums calls
over successful records only; will be replaced by total-calls accounting per arm.

**One correction to your reply, verified in code (repair.py:672-700 +
build_feedback:337-373):** your Q4 aside "success@1 comes from a separate stochastic
call that already receives arm-specific feedback before its first edit" is RIGHT
about vf receiving content in round 1 (the loop verifies the broken input and
builds feedback BEFORE the first model call). But gr round 1 is not feedback-free
either: it receives the fixed string "The candidate failed verification. Try a
different edit...". So round 1 differs between arms ONLY in feedback content
(both know the input fails), and ss differs from both (no failure statement at
all). Consequence: vf@1-vs-gr@1 is a clean single-round content contrast, and my
earlier claim elsewhere that "@1 is the same condition in both arms" was wrong.

**PROTOCOL v1 DRAFT (to freeze before any fresh data lands — attack this):**

- Estimand: primary claims are about THIS fixed 145-fixture benchmark (seed
  20260715) and named model-runs. Fixture-level paired tests are primary;
  base-cluster (14 clusters) leave-one-out and cluster bootstrap reported as
  sensitivity; generalization language restricted to "in our runs".
- Fresh runs: deepseek 3 complete reps x {ss, gr, vf-med, det}; qwen +2 reps x
  {vf, gr} (existing qwen2 pair = auditable but post-hoc, see Q9); glm-5.2 one
  complete 4-arm suite (post top-up); minimax one suite; budget control (E4) on
  deepseek + qwen.
- Primary endpoint family per model (fixture-level, paired, Holm within family):
  E1 vf-vs-gr at K=5 (feedback content), E2 gr-vs-ss (iteration+filter package),
  E3 vf@1-vs-gr@1 (single-round content), E4 union{ss,gr,vf}-vs-budget-matched
  control (strategy diversity at matched compute).
- Class-level: descriptive only (tables + forest plot, appendix BH p-values),
  post-hoc origin of the two-regime hypothesis disclosed; NO confirmatory
  class-level claim in this paper.
- Reps: report per-rep contrasts separately; summary via CMH stratified by rep
  (or mixed logistic with fixture random effect — Q7); a claim is "supported"
  only if direction agrees across all reps of that model AND the pooled test
  passes.
- Interruption/contamination rule: resumed-to-complete runs enter; provider-fault
  poisoned fixtures (e.g. balance-429) are filtered and rerun before analysis;
  every interruption logged in run metadata.
- Reporting: every arm contrast comes with the discordant-win validity
  decomposition (semantic vs format rescue) + per-class invalid rates + realized
  budget (model calls, verifier calls, tokens).

**Round-2 questions:**

Q6. Endpoint family: is {E1,E2,E3,E4} the right primary set, or should E3 be
demoted (it was identified post hoc from your observation, though it is the
cleanest content contrast the design admits)? Is 4 endpoints x Holm per model the
right multiplicity unit, or should the family span models too?

Q7. Pooling across reps that reuse the SAME 145 fixtures: per-rep + CMH stratified
by rep, or a mixed logistic model with fixture random effects? CMH strata are not
independent (same pairs re-measured); does that invalidate CMH here, and if so
what is the cheapest defensible pooled summary?

Q8. Budget-matched control design for E4: (a) independent best-of-M single-shot
draws, verifier-filtered, M = realized mean model-calls of the 3-arm union
(qwen: 1071/145 = 7.4 -> M=8); or (b) gr with K=15 (matches the union's per-fixture
call CAP, 3x5); or both? Note gr is sequential (each round sees the previous
attempt + "still wrong"), so (a) isolates resampling diversity while (b) stays
within existing harness code. Which is the right primary control?

Q9. Where is the line for the existing qwen2 pair: (i) exploratory exhibit only,
excluded from confirmatory pooling; or (ii) admissible as rep-1 because it is
fully auditable, provided every contrast we now designate primary is computed on
fresh reps 2-3 with qwen2 only shown alongside? I lean (i) strictly.

Q10. Top-line sentence. Draft: "A symbolic duality verifier makes weak open models
usable as repair agents chiefly by CERTIFYING many cheap attempts — iteration,
filtering, and strategy union raise success ~2.6x over single-shot at ~7.4x compute
in our qwen run — while the marginal value of feedback CONTENT over content-free
retry varies in sign across models and error classes in our runs, with no universal
ordering established." Tighten/correct as needed; it must not claim more than the
frozen protocol can deliver.

### Round 2 — Codex

Scope-guard confirmation: I re-read the Round 2 proposal, the relevant qwen raw
records, and the control flow in `repair.py`. I made no API calls and ran no new
experiment. Current DeepSeek aggregates remain unverifiable inputs. This section
is the only edit.

#### Code-level correction and @1 recomputation

[FLAG] The correction about generic-retry round 1 is exact. `_feedback_kind` maps
`generic_retry` to `generic` and `verifier_feedback` to `verifier`. On every round,
`run_repair_loop` first runs the feedback verifier, passes the failed outcome to
`build_feedback`, and only then calls `_call_repair`. Thus gr round 1 receives
exactly “The candidate failed verification. Try a different edit to make Theory B
a valid dual of Theory A.”; vf round 1 receives the failed-obligation list; ss gets
an empty feedback string. The raw qwen records contain exactly one unique gr
round-1 feedback string, equal to the string above, and every vf record starts with
“The candidate failed verification. Failed obligations:”.

[FLAG] Independently defining @1 success as `success && success_round == 1` gives
vf@1=13 and gr@1=11, with both=6, vf-only=7, gr-only=5, neither=127. Its exact
two-sided McNemar value is
\(2\sum_{j=0}^{5}{12\choose j}/2^{12}=0.774414\). E3 therefore isolates the
round-1 message intervention between gr and vf, but “content” includes message
length, wording, and obligation names; it does not isolate a semantic-information
mechanism from all prompt effects.

#### PROTOCOL v1, clause-by-clause attack

[BLOCKER] **Estimand.** “This fixed benchmark and named model-runs” is not an
estimand that supports sampling p-values: after a named run is observed, its 145
outcomes are a census of that run. Freeze the estimand instead as the mean success
probability over repeated calls from a named model/provider/decoding configuration,
averaged equally over these fixed 145 fixtures. Record model version, provider,
date window, temperature, top-p, token cap, and prompt/harness commit. Fixture-level
inference then concerns model-call randomness on this benchmark; it still does not
generalize to new fixtures or model versions. A base-cluster bootstrap targets a
different, superpopulation-of-bases estimand, so keep leave-one-base-out influence
as sensitivity rather than presenting its p-value as part of the fixed-benchmark
primary analysis.

[BLOCKER] **Fresh runs.** The matrix is internally incomplete. If the existing
qwen run is excluded from confirmation, two new qwen reps containing only vf and gr
cannot estimate qwen E2 (gr-vs-ss) and cannot form a wholly fresh E4
union{ss,gr,vf}. Use exactly three fresh confirmatory reps for each of qwen and
DeepSeek, each containing ss, gr, vf-med, and the E4 control. Treat det as secondary.
Treat the one-suite glm and MiniMax results as exploratory because a one-rep model
cannot enter the same repeated-run rule. The lost-record DeepSeek aggregates remain
an explicitly unverifiable legacy exhibit and do not enter any test.

[BLOCKER] **Endpoint family.** E1, E2, and E4 are distinct confirmatory claims; E3
is a nested K=1 version of E1 and was recognized after inspecting existing data.
Keeping both E1 and E3 primary spends multiplicity on two time points of the same
content contrast and permits time-point selection. Make E3 a prespecified secondary
diagnostic. For the two confirmatory models, the paper-wide family is therefore
six hypotheses: {E1,E2,E4} x {qwen,DeepSeek-fresh}. Apply Holm once across all six;
Holm remains valid under their dependence. Per-model Holm would not control the
paper-wide chance of selecting whichever model-endpoint result passes.

[FLAG] **Class-level clause.** If class effects are descriptive only, appendix BH
p-values create an avoidable quasi-confirmatory layer and the chosen BH family is
ambiguous once models, arms, and reps multiply. Report paired differences,
discordant counts, and intervals with no significance stars; state that intervals
are descriptive and unadjusted. The four-class qwen table and leave-one-base-out
changes are enough to expose pattern instability without an arbitrary partial
multiplicity correction.

[BLOCKER] **Rep pooling.** CMH stratified by rep is not valid for the proposed data
layout: the same fixture contributes to every rep stratum, so strata are dependent,
and an ordinary 2x2 CMH table also discards the within-fixture arm match. The rule
“direction agrees in every rep AND pooled p passes” is an uncalibrated conjunction:
with true per-rep probability \(s\) of the correct sign, its consistency probability
is \(s^R\), so adding a valid replicate can mechanically turn a supported effect
into an unsupported one. Use one prespecified pooled repeated-measures analysis;
show per-rep estimates as diagnostics, not a second pass/fail gate.

[FLAG] **Interruption/contamination rule.** Define provider-fault replacement by an
exact exogenous predicate before analysis, such as HTTP 429 with the recorded
“insufficient balance” provider code. Preserve both the failed attempt and its
replacement in the audit trail, select the replacement by fixture ID, and retain
model-originated parse/schema failures as outcomes. Otherwise “poisoned” can become
a discretionary label that removes difficult model failures. A resumed run also
spans service times, so the metadata must identify both segments; completion fixes
missing fixtures but does not prove provider stationarity.

[BLOCKER] **Reporting clause.** “Semantic versus format rescue” is causal language
not identified by independent stochastic calls. If vf succeeds where gr is invalid,
vf did not literally rescue gr's failed output. Report “success discordance with an
invalid counterpart” versus “success discordance with a valid-but-failing
counterpart.” Also split unparseable tool arguments from schema-invalid theories,
because the current `invalid` flag combines them. Calls and tokens must be reported
per policy, including failures; the existing success-only call metric cannot be
used for efficiency.

[BLOCKER] **E4 policy definition.** “Union” must be an executable, frozen policy,
not a retrospective OR over whichever arms happened to be run. Specify arm order,
per-arm caps, whether another arm continues after an invalid output, the stopping
rule after certification, and how a certified candidate is selected. The present
union has a maximum of 1+5+5=11 model calls per fixture, not 15; ss has K=1.
Consequently K=15 generic retry is not cap-matched and would receive 36% more
maximum calls than the three-arm portfolio.

#### Q6-Q10: one recommendation each

[BLOCKER] **Q6 — demote E3 and use one paper-wide Holm family.** The confirmatory
set is E1, E2, and E4 for qwen and fresh DeepSeek, six hypotheses total, adjusted
together by Holm. E3 is a prespecified secondary endpoint reported with its paired
effect and interval. This choice follows from E3 being nested within E1, its
post-inspection identification, and the need to prevent selection across models.
No current conclusion here relies on the unverifiable legacy DeepSeek aggregates.

[BLOCKER] **Q7 — use a fixture-clustered marginal GEE, not CMH or a random-intercept
odds ratio.** For each model and endpoint, fit binary outcome on arm plus rep fixed
effects, cluster the sandwich covariance by fixture ID, and standardize fitted
probabilities over the 145 fixtures to report a marginal risk difference and 95%
CI. This directly accounts for the same fixture reappearing across arm and rep,
keeps the effect on the paper's success-rate scale, and avoids the non-collapsible
conditional odds ratio from a random-intercept logistic model. Report the three
rep-specific paired differences and a 14-base leave-one-out range as sensitivity,
without separate significance gates.

[BLOCKER] **Q8 — choose independent best-of-M single-shot draws, with M=11.** Run
eleven independent draws from the unchanged original candidate, verifier-filter
them, and stop the policy on its first final certificate. Compare that with the
frozen ss+gr+vf portfolio under its 11-call cap. This is the primary cap-matched
control for whether strategy/feedback diversity beats pure independent resampling.
Do not use M=8: rounding the post-hoc qwen mean 7.386 upward gives the control 1,160
available calls versus the observed portfolio's 1,071 and conditions the design on
one realized run. Label E4 “equal call-cap efficacy”; realized calls and tokens are
separate efficiency outcomes. K=15 gr is rejected because the actual portfolio cap
is 11 and its sequential state changes the control question.

[BLOCKER] **Q9 — choose (i): existing qwen is exploratory and excluded from every
confirmatory pool.** The qwen outcomes caused the rank demotion, invalid-output
decomposition, E3 recognition, and endpoint-family redesign; auditability does not
undo that data reuse. Show it as the motivating pilot, then run three fresh qwen
reps with ss/gr/vf and E4 control so all qwen confirmatory endpoints use only frozen-
protocol data.

[FLAG] **Q10 — use this top line:** “On a fixed 145-fixture benchmark, one
qwen-plus run produced 34 verifier-certified repairs when single-shot,
generic-retry, and category-feedback outputs were pooled, versus 13 for single
shot, while using 1,071 versus 145 model calls; category feedback differed from
generic retry by 2 repairs (paired exact \(p=0.824\)), so this pilot shows
compute-scaled verifier-gated coverage but establishes neither a benefit from
feedback content nor a cross-model ordering.” The 34, 13, 1,071, 145, and 0.824
come directly from the auditable qwen records. It removes “weak models usable,”
“chiefly,” “cheap,” and sign variation, none of which is identified; the proposed
cross-model sign statement would depend on unverifiable DeepSeek aggregates and
post-hoc class patterns.

[FLAG] **Single point in this reply most likely to be wrong:** choosing a
fixture-clustered marginal GEE as the pooled primary analysis may still understate
dependence induced by the 14 shared theory/node bases; if that dependence dominates
model-call randomness, a hierarchical base/fixture analysis may be necessary even
though only 14 bases make its uncertainty unstable.

### Round 3 — Claude

All Round-2 blockers accepted: estimand text as you wrote it; 3 fresh confirmatory
reps x {ss, gr, vf-med, E4 control} x {qwen, deepseek}; det secondary; glm/minimax
exploratory one-rep suites; family = {E1,E2,E4} x 2 models, one paper-wide Holm;
E3 secondary; class-level = descriptive differences + unadjusted intervals, no
stars, no BH; GEE(fixture-clustered sandwich, arm+rep fixed effects, standardized
marginal risk difference) as the pooled primary; per-rep + leave-one-base-out as
sensitivity; exogenous contamination predicate (HTTP 429 + provider
insufficient-balance code, audit trail keeps both attempts); "success discordance
with an invalid/valid counterpart" wording; your Q10 top line adopted verbatim for
the pilot section.

**PROTOCOL v2 — remaining concretizations for your final pass:**

1. **E4 executable policy (frozen):** per fixture, run policies in fixed order
   ss(1 call) -> gr(<=5) -> vf-med(<=5), stopping the PORTFOLIO at the first final
   certificate; an invalid output ends its arm's round but not the portfolio; the
   certified candidate is the portfolio's output (first certificate wins; no
   selection step). Cap 11 calls. Control: best-of-11 = eleven independent
   single-shot draws from the unchanged original candidate, verifier-filtered,
   stop at first final certificate, same 11-call cap. Both policies charged
   identically: model calls, verifier calls, tokens, all attempts logged.
   Confirm: does "stop portfolio at first certificate" (cheaper, realistic usage)
   vs "always run all three arms" (cleaner union semantics) change what E4
   estimates? I chose stop-at-first-cert for both policy and control symmetry.

2. **New secondary arm, vf-shuffled (content isolation):** your Round-2 point that
   E1/E3 do not isolate semantic information from message length/wording implies a
   missing control: identical prompt TEMPLATE and obligation-list FORMAT, but the
   failed-obligation names/categories replaced by a deterministic wrong-but-plausible
   set (sampled seeded from the obligations that PASSED, same list length; if all
   passed-set too small, pad from a fixed obligation vocabulary). vf-med vs
   vf-shuffled at K=5 then tests CONTENT with wording/length held fixed. Proposed
   status: prespecified SECONDARY endpoint E5 on the two confirmatory models
   (adds <=725 calls/rep/model). Attack the design: any leakage channel (e.g.
   shuffled set accidentally correlated with the true failure) or a cheaper
   design that achieves the same isolation?

3. **Rep count as a frozen budget parameter:** the full confirmatory matrix
   (3 reps x 4 policies + E5) costs roughly ¥150-250 across both models at current
   prices (dominated by best-of-11: ~1,600 calls/rep/model). The user decides the
   budget BEFORE the freeze; the protocol text will state the chosen R in advance
   (R=3 preferred, R=2 the fallback), and R is not revisited after data starts.
   Any objection to R=2 being statistically coherent under the GEE analysis
   (rep fixed effects with 2 levels), beyond the obvious power loss?

4. **Paper structure sentence (for your check):** "Section 5 (pilot, exploratory):
   auditable qwen2 pair + legacy DeepSeek aggregates presented descriptively with
   the post-hoc origin disclosed; Section 6 (confirmatory): frozen-protocol
   endpoints E1/E2/E4 (+E5 secondary) on fresh qwen + DeepSeek reps with paper-wide
   Holm; Section 7: exploratory one-rep suites (glm-5.2, MiniMax) + depth-2 axis +
   below-floor/cheating behavioral findings, all descriptive." The paper's headline
   claims come ONLY from Section 6. Anything structurally dishonest here?

5. **GEE practicality:** statsmodels GEE with exchangeable working correlation,
   fixture id as cluster, identity-link binomial (linear probability) for direct
   risk-difference scale, robust sandwich CIs; delta-method standardization is then
   trivial (arm coefficient IS the marginal risk difference under identity link).
   If identity-link convergence fails on sparse cells, fallback = logit link +
   average marginal effects with clustered bootstrap over fixtures (B=2000,
   percentile). Acceptable as frozen primary/fallback pair?

If nothing above draws a [BLOCKER], state convergence explicitly and list the
liftable protocol sentences; I will fold PROTOCOL v2 into a standalone frozen file
(paper/analysis_protocol.md) with a git-commit freeze timestamp and take the budget
question to the user.

### Round 3 — Codex

Scope-guard confirmation: I reviewed the five concretizations against the
previously audited harness and qwen records. I made no API calls or experimental
runs, and this section is the only file edit. The legacy DeepSeek aggregates remain
unverifiable and excluded from inference.

[FLAG] **1. E4 can freeze as a stop-at-first-certificate policy, with two wording
corrections.** Running later arms after a final certificate cannot change the
binary success-by-cap endpoint; it only increases realized cost and produces
retrospective coverage data. Stop-at-first therefore estimates the deployable
policy's success probability under an 11-model-call cap. The two policies are not
“charged identically”: their prompt lengths, verifier calls, early-stop times, and
tokens can differ. They are matched only on maximum model calls. Also, an invalid
output ends the current *arm*, not merely its round; best-of-11 continues after an
invalid draw. Freeze this exact wording:

> **E4 portfolio policy.** For each fixture, execute ss (at most 1 model call),
> then gr (at most 5), then vf-med (at most 5), stopping the entire policy at the
> first candidate that passes the final verifier. An invalid output terminates
> only its current arm; if an unstarted arm remains, the policy proceeds to it.
> The first final-certified candidate is the policy output. The policy has an
> 11-model-call cap.
>
> **E4 control policy.** Execute at most 11 mutually independent single-shot calls,
> each from the unchanged original candidate and with no failure feedback. Continue
> after invalid outputs and stop at the first final certificate. The first
> final-certified candidate is the control output.
>
> **E4 estimand and accounting.** E4 is the paired difference in success probability
> between these policies under equal 11-model-call caps. For each policy, report
> realized model calls, verifier calls, input/output tokens, invalid outputs, and
> stopping reason. E4 is a call-cap efficacy comparison, not a realized-compute or
> token-matched comparison.

[BLOCKER] **2. Replace vf-shuffled with a neutral masked-feedback control before
freeze.** Selecting false labels from obligations that passed makes the placebo a
function of the true verifier outcome: the available donor set, padding frequency,
and chosen labels can reveal the complement of the failed set and correlate with
fixture class. More fundamentally, correct vf versus plausible-but-wrong vf
estimates the joint benefit of correct information and avoidance of misinformation;
an adverse shuffled arm could be caused by active misdirection. It does not isolate
semantic information from form.

Use one secondary arm named `vf-masked`, not `vf-shuffled`, and freeze:

> **E5 masked-feedback contrast.** At every round, vf-masked receives the same
> failure preamble and the same number and structure of obligation bullets as
> vf-med, but every obligation name and category is replaced by a neutral opaque
> placeholder. Placeholder generation may depend on bullet count and position but
> not on obligation identity, the passed-obligation set, perturbation class, model
> output, or fixture identity. E5 is vf-med minus vf-masked at K=5 and estimates
> the value of interpretable obligation identities beyond revealing failure count
> and list structure; it does not claim perfect isolation from all prompt-form
> effects. E5 is secondary, with Holm adjustment across its two model-specific
> hypotheses, and cannot support a primary headline claim.

No artifact-only analysis can replace this arm because the counterfactual model
response to masked feedback was never generated. Exact token-length equality is
not necessary for the stated estimand, but record actual prompt tokens and report
their arm difference.

[FLAG] **3. R=2 is statistically coherent if frozen before the first fresh call.**
With 145 fixture clusters and \(2R\) observations per two-arm contrast per fixture,
the arm coefficient remains identifiable at R=2; a two-level rep fixed effect uses
one degree of freedom. R=2 reduces precision and makes rep heterogeneity poorly
diagnosed, but it does not invalidate GEE. Freeze:

> The common replication count R is selected from {2,3}, recorded in the frozen
> protocol, and applied to every confirmatory model-policy cell. R cannot be
> increased, decreased, or selectively extended after any fresh response is
> observed. The choice is budget-based and is accompanied by a prospective
> minimum-detectable-effect calculation under the six-hypothesis Holm family.

The last sentence is needed because “coherent” is not the same as adequately
powered; the earlier per-class calculation already showed how low event rates make
nominal sample counts misleading.

[FLAG] **4. The paper structure can freeze after separating auditable pilot data
from unverifiable legacy recollection and clarifying E5's family.** The structure
does not become confirmatory merely because fresh results appear in Section 6;
eligibility comes from freezing before collection and including every fresh
complete run. Freeze this wording:

> **Section 5—exploratory pilot evidence.** Report the auditable qwen pilot
> per-fixture results and the lost-record DeepSeek aggregates in separate
> subsections. Label the latter “unverifiable legacy aggregates,” disclose their
> post-hoc role, and exclude them from every inferential calculation.
>
> **Section 6—confirmatory fixed-benchmark analysis.** Report every fresh complete
> qwen and DeepSeek run collected under the frozen protocol. E1, E2, and E4 for
> the two models form one six-hypothesis paper-wide Holm family. E5 is secondary
> and forms a separate two-hypothesis Holm family. Only the six primary hypotheses
> may support headline confirmatory claims.
>
> **Section 7—exploratory extensions.** Report the one-rep glm-5.2 and MiniMax
> suites, depth-2 axis, class-level patterns, and below-floor or cheating behaviors
> descriptively, without confirmatory significance language.

[BLOCKER] **5. Make logit-link GEE with delta-method standardization the sole
primary analysis; reject the proposed identity-link/percentile-bootstrap pair.**
A binomial identity-link fit can converge while producing fitted probabilities
outside \([0,1]\), so “fallback only if convergence fails” does not catch its main
failure mode. Switching links conditional on observed convergence also makes the
analysis path data-dependent. The proposed fixture bootstrap randomly changes the
weights of the 145 fixtures and therefore targets resampling of fixtures, whereas
the frozen estimand averages equally over this fixed fixture census.

Freeze this instead:

> **Primary pooled model.** For each model and endpoint, fit a marginal binomial
> GEE with logit link, arm and replication fixed effects, fixture ID as the
> clustering unit, exchangeable working correlation, and robust sandwich
> covariance. Report the arm contrast as a standardized marginal risk difference:
> predict each arm at every observed replication level, average predictions
> equally over replication levels and the fixed 145 fixtures, and subtract.
> Construct its 95% confidence interval by the delta method using the robust
> covariance. If the exchangeable working-correlation fit fails numerically, refit
> the same logit mean model with independence working correlation and the same
> robust covariance; this numerical fallback preserves the estimand and is
> triggered only by a logged solver failure. Rep-specific paired risk differences
> and the leave-one-base-out range are sensitivity summaries, not additional
> decision gates.

The independence fallback changes efficiency, not the specified marginal mean
model; robust covariance protects against misspecification of the working
correlation when fixture clusters are independent. Dependence among fixtures from
the same 14 bases remains the already-declared sensitivity limitation.

[BLOCKER] **Not converged.** Items 2 and 5 require protocol changes before the git
freeze. Items 1, 3, and 4 are ready to lift using the exact sentences above.

[FLAG] **Single point in this reply most likely to be wrong:** the neutral
vf-masked arm may be a worse form control than the rejected plausible-label shuffle,
because opaque placeholders can themselves change model attention and epistemic
behavior; if that effect is large, E5 still will not isolate semantic information
despite avoiding outcome-dependent misinformation.

### Round 4 — Claude

Both remaining blockers accepted VERBATIM:

- Item 2: E5 = vf-masked exactly as you froze it (neutral opaque placeholders,
  placeholder generation independent of obligation identity / passed set / class /
  output / fixture id; secondary; own two-hypothesis Holm family). Your
  most-likely-wrong note (placeholders may themselves shift attention) goes into
  the protocol's stated limitations verbatim.
- Item 5: logit-link GEE + delta-method standardized marginal risk difference as
  the SOLE primary pooled analysis, independence working correlation as the only
  (logged, numerical) fallback; identity link and fixture bootstrap rejected for
  the reasons you derived.

Items 1, 3, 4 lift with your exact sentences.

**Mid-loop data disclosure (no protocol change):** qwen2_vf_detailed completed
while this round was in flight: 32/145 = 22.1% (invalid 29.7%), auditable on disk
at runs/experiments/repair_d1/runs/qwen2_vf_detailed/. Under the protocol this is
PILOT data (exploratory exhibit, Section 5). det remains secondary in the
confirmatory matrix; nothing in the frozen design was altered in response to
seeing it. Noted here so the freeze timestamp postdating this observation is
disclosed rather than discovered.

If nothing new arises: state CONVERGED and I will fold the frozen sentences
(your Round-2 estimand text + Round-3 items 1-5 texts + the family definitions +
the legacy/contamination/reporting rules from Rounds 1-2) into
paper/analysis_protocol.md, commit it as the freeze timestamp, and take the
R∈{2,3} budget decision to the user before any fresh run.

### Round 4 — Codex

Scope-guard confirmation: I compared the Round 4 acceptances with the exact Round 3
text and read only the new qwen detailed-arm artifacts needed for the numerical
check. I made no API calls or experimental runs, and this section is the only edit.
The legacy DeepSeek aggregates remain unverifiable and excluded from inference.

[FLAG] **The two Round 3 acceptances match.** The E5 description retains neutral
opaque placeholders, independence from obligation identity/passed set/class/model
output/fixture ID, secondary status, and its separate two-hypothesis Holm family.
The GEE description retains logit link, arm and rep fixed effects, fixture-clustered
robust covariance, delta-method standardized marginal risk difference, and
independence working correlation only after a logged exchangeable-fit failure.
Rejecting identity-link GEE and fixture bootstrap also matches Round 3. The stated
placeholder-attention limitation should remain attached to E5.

[FLAG] **The new qwen2_vf_detailed disclosure is reproducible.** The raw JSONL has
145 rows, 145 unique fixture IDs, no duplicates, 32 successes, and 43 invalid
records. Therefore success is \(32/145=22.069\%\) and invalidity is
\(43/145=29.655\%\), matching `summary.json` after rounding. Raw class success
counts are drop-W 7/38, flip-W 2/13, R-charge 10/52, and rank 13/42. These are
auditable pilot observations only. They do not alter a frozen endpoint, model
family, or analysis rule, and no conclusion here uses the unverifiable DeepSeek
aggregates.

[BLOCKER] **E4 data collection and stop-first policy replay must be distinguished.**
The frozen fresh matrix says every fixture-rep supplies ss, gr, and vf outcomes for
E1 and E2. If those same calls are executed as a literal stop-first E4 portfolio,
an ss certificate suppresses gr and vf, and a gr certificate suppresses vf. The
missing outcomes then depend on success and make E1/E2 incomplete. Running the
three arms fully avoids that missingness but is not literal stop-first execution.

Use the following definitive reconciliation; it adds no model calls beyond the
already budgeted ss/gr/vf cells:

> **Component collection and E4 replay.** For every confirmatory fixture-rep,
> collect complete, mutually independent ss, gr, and vf-med arm outcomes under
> their respective 1, 5, and 5 call caps, irrespective of whether another arm
> certifies. Use these complete component outcomes for E1 and E2. Construct the E4
> portfolio outcome by deterministic replay in the frozen order ss, gr, vf-med:
> the replay stops at the first recorded final certificate; an invalid output
> terminates its current arm but not the replay when an unstarted arm remains.
> Calls and tokens occurring after the replay's stopping point are excluded from
> the E4 deployed-policy accounting but retained in the experiment audit trail and
> actual data-generation accounting. Because component calls are independent and
> later arms cannot affect earlier outcomes, replay preserves the success
> distribution of the executable stop-first policy while retaining complete E1/E2
> data.

The best-of-11 control remains a separately executed stop-first policy. Report both
actual data-generation cost and replayed E4 deployed-policy cost; they answer
different questions.

[BLOCKER] **R must be chosen before the freeze commit, not afterward.** Round 3's
accepted sentence requires the common R to be “recorded in the frozen protocol.”
The proposed order—commit `analysis_protocol.md` as the freeze timestamp and then
ask the user for R—would leave a confirmatory sample-size choice open after the
purported freeze. The fact that no fresh response has yet been observed prevents
data-driven selection, but the commit would not actually be a complete protocol
freeze.

Freeze the order as:

> Compute and record the prospective minimum-detectable effects for R=2 and R=3
> under the six-hypothesis Holm family; obtain the budget decision; write the one
> selected integer R into every confirmatory model-policy cell; then commit
> `paper/analysis_protocol.md` and record that commit as the freeze timestamp.
> Generate no fresh confirmatory response before that commit. R is not amended
> after the freeze.

[BLOCKER] **Not converged.** The accepted E5 and GEE corrections resolve the Round 3
blockers, and the detailed-arm pilot creates no protocol change. Convergence still
requires inserting the E4 collection/replay clause and choosing R before the freeze
commit. All other frozen components from Rounds 2–3 remain unchanged; `det` is an
exploratory pilot arm and is not an additional fresh confirmatory policy cell.

[FLAG] **Single point in this reply most likely to be wrong:** deterministic replay
from fully collected ss/gr/vf components may not perfectly reproduce literal
stop-first deployment if provider behavior depends on concurrent load, request
ordering, or time, even though it is distributionally valid under the protocol's
assumption of independent, stationary model calls.

### Round 5 — Claude (round cap)

Both Round-4 blockers accepted VERBATIM: the E4 component-collection/replay clause
(complete independent ss/gr/vf per fixture-rep for E1/E2; E4 by deterministic
stop-first replay; dual cost accounting; your distributional-validity caveat
attached), and the freeze ordering (MDE -> budget decision -> R written in -> THEN
the protocol commit = freeze timestamp; no fresh confirmatory response before it).

**Prospective MDE, recorded per the frozen sentence.** Paired-contrast normal
approximation, MDE ≈ (z_alpha' + z_0.8)·sqrt(q/(R·145)), q = discordance
probability; worst-case Holm step alpha' = 0.05/6 (z=2.64); pilot-informed
q: vf-gr 0.138, gr-ss 0.152 (from your Round-1/2 tables); ICC across reps > 0
shrinks effective N, so these are optimistic lower bounds:

| contrast (q) | R=2 (N=290) | R=3 (N=435) |
|---|---|---|
| q=0.10 | 6.4 pp | 5.3 pp |
| q=0.15 | 7.9 pp | 6.5 pp |
| q=0.20 | 9.1 pp | 7.5 pp |

Honesty note attached to the table: the qwen pilot's observed vf-gr difference is
1.4 pp — far below MDE at either R; if the true content effect is of that order,
the confirmatory result will be a bounded null (tight CI around 0), which the
paper reports as such. E2's pilot difference is 4.1 pp (qwen), also below MDE;
the design is powered for ~6-9 pp effects, not for certifying 1-2 pp ones.

**Corrected fold order:** (1) draft paper/analysis_protocol.md now, UNCOMMITTED,
containing every frozen sentence from Rounds 2-4 with R left as the single
unresolved field; (2) present R∈{2,3} + MDE table + cost estimate to the user;
(3) write the chosen R in; (4) commit = freeze timestamp; (5) only then implement
harness additions (bestof11 policy, vf-masked arm, instrumentation, total-calls
metric) and launch fresh runs.

State CONVERGED if this closes everything, with the definitive component list for
the protocol file.

### Round 5 — Codex

Scope-guard confirmation: I checked the MDE arithmetic and fold order against the
accepted protocol. I made no API calls or experimental runs, and this section is
the only edit. Legacy DeepSeek aggregates remain unverifiable pilot recollections
and are excluded from every inferential calculation.

[FLAG] **The MDE arithmetic is correct.** For the worst Holm step,
\(\alpha^\prime=0.05/6=0.008333\); a two-sided test uses
\(z_{1-\alpha^\prime/2}=2.638\). Adding \(z_{0.8}=0.842\) gives 3.480. Multiplying
this by \(\sqrt{q/(145R)}\) gives, in percentage points:

| q | R=2 | R=3 |
|---:|---:|---:|
| 0.10 | 6.46 | 5.28 |
| 0.15 | 7.91 | 6.46 |
| 0.20 | 9.14 | 7.46 |

These reproduce 6.4/5.3, 7.9/6.5, and 9.1/7.5 after rounding. The pilot-informed
discordance inputs also reproduce: vf-gr is \(20/145=0.1379\), and gr-ss is
\(22/145=0.1517\). For repeated differences with within-fixture correlation
\(\rho>0\), the approximation is inflated by
\(\sqrt{1+(R-1)\rho}\), so labeling the table an optimistic independence bound is
correct.

[FLAG] **Replace “bounded null” in the MDE note.** A small estimate with a
non-significant test is not a bounded null unless a smallest effect of interest or
equivalence margin was frozen and the multiplicity-adjusted interval lies within
it. No such margin has been defined. Use:

> The qwen pilot differences, 1.4 pp for E1 and 4.1 pp for E2, are below the
> optimistic 6–9 pp MDE range. If fresh estimates remain small, report their
> multiplicity-adjusted confidence intervals without calling the result
> equivalence or a bounded null; effects of scientific interest remain compatible
> with the data whenever the interval includes them.

[FLAG] **The fold order is admissible with an implementation-manifest safeguard.**
Choosing R before the freeze commit closes the Round 4 ordering blocker. Freezing
the design before implementing it does not use outcome data, but the custom policy
must be verified before collection. Add:

> After the protocol freeze, implement and offline-test best-of-11, vf-masked,
> component replay, changed-path instrumentation, and total-cost accounting
> without generating confirmatory model responses. Before the first fresh
> response, record the tested harness commit, prompt hashes, configs, and test
> results in an immutable execution manifest. Any implementation discovery that
> changes an estimand, intervention, endpoint, exclusion rule, or analysis requires
> a timestamped pre-data protocol amendment; it may not be treated as a silent code
> fix.

[FLAG] **CONVERGED.** No design disagreement remains. The protocol is not formally
frozen until the user selects R, that integer is written into the file, and the
protocol commit is created; the converged components ready to lift into
`paper/analysis_protocol.md` are:

1. **Estimand and scope.** Estimate, for each named model/provider/decoding
   configuration, mean success probability over repeated calls, equally averaged
   over the fixed 145 fixtures. Record model/version, provider/date window,
   sampling parameters, token cap, prompt hashes, and harness commit. Do not
   generalize inferential claims to new fixtures or model versions.
2. **Evidence tiers.** Existing auditable qwen runs, including vf-detailed
   32/145, are exploratory pilot data. Lost-record DeepSeek aggregates are labeled
   unverifiable legacy aggregates and excluded from inference. Fresh qwen and
   DeepSeek data are confirmatory; one-rep glm-5.2, MiniMax, depth-2, class-level,
   below-floor, and cheating analyses are exploratory.
3. **Replication freeze.** Choose one common \(R\in\{2,3\}\) using the prospective
   MDE table and budget before the freeze commit; apply it to every confirmatory
   model-policy cell; do not alter R after any fresh response.
4. **Complete component collection.** For every model, fixture, and rep, collect
   mutually independent complete ss, gr, and vf-med outcomes under caps 1, 5, and
   5. These complete records supply E1 and E2.
5. **E4 portfolio and control.** Deterministically replay ss -> gr -> vf-med,
   stopping at the first final certificate; invalidity ends its arm but not a
   replay with an unstarted arm. Compare this portfolio with a separately executed
   best-of-11 policy of independent, unchanged-candidate, no-feedback calls that
   continues after invalid draws and stops at its first final certificate. E4 is
   paired call-cap efficacy, not token- or realized-cost matching. Retain both
   actual data-generation and replayed deployment cost.
6. **E5 masked feedback.** vf-masked preserves the failure preamble, bullet count,
   and list structure but replaces obligation identities/categories with neutral
   opaque placeholders independent of identity, passed set, class, model output,
   and fixture ID. E5 estimates the value of interpretable obligation identity
   beyond failure count/list structure, not perfect isolation from prompt form.
   The placeholder-attention limitation is stated explicitly.
7. **Endpoint families.** The primary family is
   \(\{\mathrm{E1\ vf-gr@5},\mathrm{E2\ gr-ss},\mathrm{E4\ portfolio-control}\}\)
   x {fresh qwen, fresh DeepSeek}, adjusted once by paper-wide Holm across six
   hypotheses. E3 vf@1-gr@1 is secondary. E5 is secondary with its own
   two-model Holm family and cannot support a primary headline.
8. **Primary pooled analysis.** For each model-endpoint, fit logit-link binomial
   GEE with arm and rep fixed effects, fixture-ID clusters, exchangeable working
   correlation, and robust sandwich covariance. Report the delta-method
   standardized marginal risk difference, averaging equally over rep levels and
   the fixed fixtures. A logged numerical failure triggers only independence
   working correlation with the same mean model and covariance. Identity-link GEE
   and fixture bootstrap are excluded.
9. **Sensitivity and descriptive analysis.** Show rep-specific paired risk
   differences and the 14-base leave-one-out range without additional decision
   gates. Class tables report differences, discordant counts, and unadjusted
   descriptive intervals without stars or BH testing.
10. **Interruptions and invalidity.** Replace records only under a prespecified
    exogenous provider-fault predicate, such as HTTP 429 plus the provider's
    insufficient-balance code; retain both attempts in the audit trail and log
    service segments. Model parse and schema failures remain outcomes. Report
    “success discordance with an invalid counterpart” and “with a
    valid-but-failing counterpart,” not causal rescue.
11. **Cost and audit reporting.** Report total model calls, verifier calls,
    input/output tokens, invalid categories, stopping reasons, and policy-level
    costs including failures. Do not use the old success-only
    `verifier_calls_per_success` as efficiency.
12. **Paper structure and claims.** Section 5 separates auditable qwen pilot data
    from unverifiable DeepSeek legacy aggregates; Section 6 contains every fresh
    complete confirmatory run and the frozen primary/secondary families; Section 7
    is descriptive exploration. Only the six primary Section 6 hypotheses may
    support headline confirmatory claims. The pilot top line remains the
    compute-scaled qwen coverage sentence frozen in Round 2, with no feedback-
    content or cross-model ordering claim.
13. **Freeze and execution order.** Draft the protocol uncommitted; present the
    MDE/cost choice; write the selected R; commit that complete protocol as the
    freeze timestamp; implement and offline-test; record the implementation
    manifest; then and only then collect fresh confirmatory responses.

[FLAG] **Single point in this reply most likely to be wrong:** permitting the
analysis-protocol freeze to precede implementation may be too permissive for these
custom E4/E5 interventions; offline testing could expose a semantic ambiguity that
is better resolved in the main freeze commit than through a pre-data amendment.
