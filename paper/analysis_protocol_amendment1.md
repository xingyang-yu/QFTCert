# Amendment 1 — MiniMax-M2.5 extension family (pre-data)

Status: becomes frozen at the git commit adding this file. No MiniMax
confirmatory response exists at commit time (verified: only the discarded
scout run below).

## Scope

Extends the frozen protocol (paper/analysis_protocol.md, commit 813fdb0)
with a THIRD model as its own extension family. Nothing in the original
six-hypothesis primary family, its Holm adjustment, or any other frozen
clause changes.

## Model and provider

MiniMax-M2.5 via Alibaba Cloud Bailian (dashscope compatible-mode,
route openai:MiniMax-M2.5). Provider constraint, disclosed: Bailian locks
`enable_thinking` to True for this model (the parameter rejects False),
so unlike the two primary models the extension model runs WITH
provider-forced reasoning; reasoning tokens bill as output. Forced
tool_choice under thinking is rejected by the provider with an error and
the harness's documented automatic fallback to tool_choice=auto applies
(commit c2469ac). Same config as the primary campaigns
(configs/repair_d1_ft.json, max_tokens 8192), same fixture set, same
R=3, same complete component collection, same E4 replay and best-of-11
control, same vf_masked construction, same contamination predicate and
resume rules, same GEE primary analysis.

## Scout disclosure

A single-shot SCOUT run (run-id scout_minimax_ss) was executed before
this amendment to check interface viability and cost. Its first attempt
was contaminated by a local network outage (108 fixtures with
APIConnectionError; filtered under the exogenous predicate, backup
.jsonl.outage_bak) and rerun to completion: 22/145 certified, invalid
11.0%, abstain 13.8%, ~4.0k output tokens/call. The scout informed the
GO decision and the cost estimate ONLY; it is EXCLUDED from every
confirmatory calculation, and the confirmatory single-shot replications
are fresh runs with distinct run-ids.

## Endpoint families

Extension primary family (own Holm adjustment across THREE hypotheses;
does not touch the original paper-wide family):
{E1 vf-vs-gr, E2 gr-vs-ss, E4 portfolio-vs-control} x {MiniMax-M2.5}.

Extension secondary: E5 vf-vs-masked (single hypothesis, reported with
unadjusted p, labeled secondary); E3 descriptive.

Claims language: extension results are reported alongside but SEPARATELY
from the two-model primary family; the paper's existence claim about
model-dependent strategy remains grounded in the primary family, with
the extension model as additional evidence under its own adjustment.

## Execution

Run-ids conf_minimax_<arm>_r<rep>, arms
{single_shot_repair, generic_retry, verifier_feedback, best_of_n,
vf_masked}, reps {1,2,3}, score-e4 per rep, detached execution with
--resume idempotence. Cost projection from the scout: ~17M input +
~44M output tokens; unit price unknown at freeze time (console-only),
account topped up to >=CNY 150; if balance exhausts mid-run the
exogenous-contamination rule applies (filter + top up + resume).
