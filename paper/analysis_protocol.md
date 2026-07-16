# Analysis Protocol — repair-loop confirmatory phase

Status: DRAFT, UNCOMMITTED. Becomes frozen at the git commit that writes the
selected replication count R into section 3. No fresh confirmatory model response
may be generated before that commit.

Provenance: converged Claude<->Codex loop (GPT 5.6 Sol, xhigh, 5 rounds,
CONVERGED at Round 5), transcript in crossmodel_flip_discussion.md at repo root.
All numbered components below lift the converged texts verbatim where quoted.

## 0. Benchmark

Fixed 145-fixture depth-1 repairable set, deterministic regeneration at seed
20260715 (manifest: runs/experiments/repair_d1/fixtures/manifest.jsonl). Classes:
drop_w_term (38), flip_w_sign (13), r_charge_perturb (52), rank_perturb (42);
fixtures nest in 14 theory/node bases. Full-theory edit mode. Feedback verifier
L=3, final verifier L=5 (anti-gaming pair). K caps per arm as in section 4.

## 1. Estimand and scope

Estimate, for each named model/provider/decoding configuration, the mean success
probability over repeated calls, averaged equally over the fixed 145 fixtures.
Record model/version, provider/date window, sampling parameters, token cap,
prompt hashes, and harness commit. Fixture-level inference concerns model-call
randomness on this benchmark; inferential claims do not generalize to new
fixtures or model versions.

## 2. Evidence tiers

- Exploratory pilot (auditable): existing qwen2_* runs (vf 21/145, gr 19/145,
  det 32/145, ss 13/145), glm-5.2 ss 7/145; per-fixture records on disk.
- Unverifiable legacy aggregates: DeepSeek 2026-07-15 numbers (records lost to a
  tmp wipe). Labeled as such, excluded from every inferential calculation.
- Confirmatory: fresh qwen-plus and deepseek-chat runs collected under this
  frozen protocol only.
- Exploratory extensions: one-rep glm-5.2 and MiniMax suites, depth-2 axis,
  class-level patterns, below-floor and cheating behaviors.

## 3. Replication freeze

The common replication count R is selected from {2,3} using the prospective MDE
table (section 8) and budget, BEFORE the freeze commit; it applies to every
confirmatory model-policy cell and is not amended after any fresh response.

R = 3 (selected by the user on 2026-07-16 from the section-8 MDE table and the
observed-spend cost estimate, before this freeze commit; no fresh confirmatory
response existed at selection time).

## 4. Component collection and E4 replay (frozen verbatim)

For every confirmatory fixture-rep, collect complete, mutually independent ss,
gr, and vf-med arm outcomes under their respective 1, 5, and 5 call caps,
irrespective of whether another arm certifies. Use these complete component
outcomes for E1 and E2. Construct the E4 portfolio outcome by deterministic
replay in the frozen order ss, gr, vf-med: the replay stops at the first recorded
final certificate; an invalid output terminates only its current arm; if an
unstarted arm remains, the policy proceeds to it. Calls and tokens occurring
after the replay's stopping point are excluded from the E4 deployed-policy
accounting but retained in the experiment audit trail and actual data-generation
accounting.

**E4 control policy.** Execute at most 11 mutually independent single-shot calls,
each from the unchanged original candidate and with no failure feedback. Continue
after invalid outputs and stop at the first final certificate. The first
final-certified candidate is the control output.

**E4 estimand and accounting.** E4 is the paired difference in success
probability between these policies under equal 11-model-call caps. For each
policy, report realized model calls, verifier calls, input/output tokens, invalid
outputs, and stopping reason. E4 is a call-cap efficacy comparison, not a
realized-compute or token-matched comparison.

## 5. E5 masked-feedback contrast (secondary, frozen verbatim)

At every round, vf-masked receives the same failure preamble and the same number
and structure of obligation bullets as vf-med, but every obligation name and
category is replaced by a neutral opaque placeholder. Placeholder generation may
depend on bullet count and position but not on obligation identity, the
passed-obligation set, perturbation class, model output, or fixture identity. E5
is vf-med minus vf-masked at K=5 and estimates the value of interpretable
obligation identities beyond revealing failure count and list structure; it does
not claim perfect isolation from all prompt-form effects. E5 is secondary, with
Holm adjustment across its two model-specific hypotheses, and cannot support a
primary headline claim. Stated limitation: neutral opaque placeholders may
themselves change model attention and epistemic behavior; if that effect is
large, E5 still will not isolate semantic information despite avoiding
outcome-dependent misinformation.

## 6. Endpoint families

Primary family (ONE paper-wide Holm adjustment across all six):
{E1 vf-vs-gr at K=5, E2 gr-vs-ss, E4 portfolio-vs-control} x {fresh qwen-plus,
fresh deepseek-chat}.

Secondary: E3 vf@1-vs-gr@1 (nested single-round content contrast; paired effect
and interval, no primary claim). E5 (own two-hypothesis Holm family).

Only the six primary hypotheses may support headline confirmatory claims.

## 7. Primary pooled analysis (frozen verbatim)

For each model and endpoint, fit a marginal binomial GEE with logit link, arm and
replication fixed effects, fixture ID as the clustering unit, exchangeable
working correlation, and robust sandwich covariance. Report the arm contrast as a
standardized marginal risk difference: predict each arm at every observed
replication level, average predictions equally over replication levels and the
fixed 145 fixtures, and subtract. Construct its 95% confidence interval by the
delta method using the robust covariance. If the exchangeable working-correlation
fit fails numerically, refit the same logit mean model with independence working
correlation and the same robust covariance; this numerical fallback preserves the
estimand and is triggered only by a logged solver failure. Rep-specific paired
risk differences and the leave-one-base-out range are sensitivity summaries, not
additional decision gates. Identity-link GEE and fixture bootstrap are excluded.

## 8. Prospective MDE (recorded before R selection)

Paired-contrast normal approximation, MDE ~ (z_alpha' + z_0.8) * sqrt(q/(R*145)),
worst Holm step alpha' = 0.05/6 (z = 2.638), z_0.8 = 0.842; optimistic
independence bound (within-fixture correlation rho > 0 inflates by
sqrt(1+(R-1)rho)). Pilot-informed discordance: vf-gr 20/145 = 0.138,
gr-ss 22/145 = 0.152.

| q | R=2 (pp) | R=3 (pp) |
|---:|---:|---:|
| 0.10 | 6.46 | 5.28 |
| 0.15 | 7.91 | 6.46 |
| 0.20 | 9.14 | 7.46 |

The qwen pilot differences, 1.4 pp for E1 and 4.1 pp for E2, are below the
optimistic 6-9 pp MDE range. If fresh estimates remain small, report their
multiplicity-adjusted confidence intervals without calling the result equivalence
or a bounded null; effects of scientific interest remain compatible with the data
whenever the interval includes them.

## 9. Sensitivity and descriptive analysis

Rep-specific paired risk differences and the 14-base leave-one-out range are
reported without additional decision gates. Class-level tables report paired
differences, discordant counts, and unadjusted descriptive intervals, with no
significance stars and no BH layer. The post-hoc origin of the earlier
"two-regime" class hypothesis is disclosed; no confirmatory class-level claim is
made in this paper.

## 10. Interruptions, contamination, invalidity

Records are replaced only under a prespecified exogenous provider-fault
predicate: HTTP 429 carrying the provider's insufficient-balance/arrearage code
(e.g. Zhipu code 1113), or an equivalent documented provider-outage signature.
Both the failed attempt and its replacement stay in the audit trail, selected by
fixture ID; service segments of resumed runs are logged in run metadata. Model
parse and schema failures remain outcomes, never replaced. Reporting language:
"success discordance with an invalid counterpart" vs "with a valid-but-failing
counterpart"; no causal rescue phrasing. Unparseable tool arguments and
schema-invalid theories are reported as separate invalidity categories.

## 11. Cost and audit reporting

Report per policy: total model calls, verifier calls, input/output tokens,
invalidity categories, stopping reasons, and policy-level costs including
failures. The legacy success-only `verifier_calls_per_success` metric is not
used for efficiency claims.

## 12. Paper structure and claims

Section 5 (exploratory pilot evidence): auditable qwen pilot per-fixture results
and lost-record DeepSeek aggregates in SEPARATE subsections; the latter labeled
"unverifiable legacy aggregates," post-hoc role disclosed, excluded from
inference. Section 6 (confirmatory): every fresh complete qwen and DeepSeek run
under this protocol; primary/secondary families as in section 6 above. Section 7
(exploratory extensions): descriptive only. Pilot top line (frozen): "On a fixed
145-fixture benchmark, one qwen-plus run produced 34 verifier-certified repairs
when single-shot, generic-retry, and category-feedback outputs were pooled,
versus 13 for single shot, while using 1,071 versus 145 model calls; category
feedback differed from generic retry by 2 repairs (paired exact p=0.824), so this
pilot shows compute-scaled verifier-gated coverage but establishes neither a
benefit from feedback content nor a cross-model ordering."

## 13. Freeze and execution order (frozen verbatim)

Draft the protocol uncommitted; present the MDE/cost choice; write the selected
R; commit that complete protocol as the freeze timestamp; implement and
offline-test best-of-11, vf-masked, component replay, changed-path
instrumentation, and total-cost accounting without generating confirmatory model
responses; before the first fresh response, record the tested harness commit,
prompt hashes, configs, and test results in an immutable execution manifest. Any
implementation discovery that changes an estimand, intervention, endpoint,
exclusion rule, or analysis requires a timestamped pre-data protocol amendment;
it may not be treated as a silent code fix. Then and only then collect fresh
confirmatory responses.
