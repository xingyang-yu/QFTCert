# MiniMax confirmatory-data contamination audit — Claude↔Codex loop (fresh session)

Deliverable: a converged cleaning + rerun + reanalysis procedure for the MiniMax
extension family, consistent with the FROZEN protocol (paper/analysis_protocol.md,
commit 813fdb0) and amendment 1 (paper/analysis_protocol_amendment1.md). This log is
the transcript; rounds appended in order.

## SCOPE GUARDS (repeat every round)
1. The protocol and amendment are FROZEN. The only permitted data intervention is the
   amendment's own exogenous-contamination rule ("filter + top up + resume"). No
   post-hoc outcome editing, no predicate invented after seeing outcomes.
2. The two-model primary family (deepseek/qwen) is CLEAN (verified: 0 contaminated
   rows) and its frozen analysis is untouchable.
3. Cleaning MAY change the MiniMax extension GEE numbers; that is not a "frozen
   number" violation — the frozen object is the protocol, and current numbers were
   computed on contaminated input. After cleaning, the frozen GEE reruns unchanged
   and downstream docs (PAPER_BLUEPRINT.md §3 MiniMax table, abstract-sentence
   validity) update to the clean numbers with a fresh verification pass.
4. Selection into rerun must be outcome-INDEPENDENT (based only on presence of an
   exogenous transport error), else bias is introduced.
5. Codex verifies everything independently on disk; no trust in Claude's counts.

## VERIFIED FACTS (on disk, 2026-07-21)
- Scan predicate used: any round whose `apply_error`/`feedback_text` contains
  APIConnectionError / APITimeoutError / "Connection error" / "timed out"
  (case-insensitive).
- Contaminated fixture-reps, MiniMax only (43 total):
  bon r1=12 r2=5 r3=5; gr r1=4 r2=6 r3=4; ss r2=1; vf r1=1; vfm r1=4 r2=1.
  deepseek: 0. qwen: 0.
- Example rows: ss_r2 dp0_toric_N4_d1_node0_drop_w_term_00 — its ONLY attempt is
  `APITimeoutError: Request timed out.`, recorded success=False (a pure exogenous
  failure counted as a model failure). bon rows show `APIConnectionError` consuming
  draws within the 11-draw budget.
- Integrity otherwise: all 15 arm-reps n=145, 0 duplicate fixture_ids, 0 never-called
  rows, every line parses.
- Side issue (cosmetic): canonical `conf_minimax_best_of_n_*` and
  `conf_minimax_vf_masked_*` dirs lack summary.json/metadata.json (shard-merge
  byproduct); GEE only reads repair_results.jsonl, but the audit trail should be
  regenerated (score-repair or resume-completion writes them).
- Scout run `scout_minimax_ss` (+ .jsonl.outage_bak): disclosed in amendment 1,
  excluded from all confirmatory calculations; left as-is.
- Current (contaminated-input) extension GEE, for reference only:
  E2 +11.0pp (Holm p=0.0003), E4 −8.0pp (0.018), E1 +3.2pp (0.18 ns),
  E5 −0.5pp (0.84 ns, unadjusted).

---

### Round 1 — Claude

**Proposed procedure (attack it):**
1. Predicate (preregistered reading): a fixture-rep is contaminated iff any of its
   recorded rounds/draws carries an exogenous API-transport error
   (APIConnectionError/APITimeoutError). Presence-based, outcome-independent.
2. Treatment: for ALL 43 contaminated fixture-reps — including any with
   success=True — delete that row from the arm-rep's repair_results.jsonl and re-run
   via the harness's own `--resume` under the SAME run-id (resume re-executes exactly
   the missing fixtures). This is literally the amendment's "filter + resume"
   machinery. Rerunning all affected cells (not only failures) keeps selection
   outcome-independent.
3. Loop-until-clean: after the rerun, re-scan with the same predicate; if new
   transport errors appeared, filter + resume again. Terminate when 0 contaminated
   rows remain; each pass logged here.
4. Downstream, in order: re-run score-e4 replay (control arm changed) → re-run the
   frozen extension GEE (analyze_confirmatory, minimax_extension out_dir) →
   regenerate summary.json/metadata.json for the merged canonical dirs → update
   PAPER_BLUEPRINT.md §3 numbers (and re-check the abstract MiniMax sentence still
   matches the signs: iteration gain E2>0 sig; resampling outperforming portfolio
   E4<0 sig) → one Codex verification pass on the updated blueprint.
5. If dashscope balance exhausts mid-rerun, the same exogenous rule applies
   (filter + top up + resume); no partial-data analysis.

**Questions for Codex:**
- R1-a: Is the presence-based predicate + rerun-ALL-43 the correct unbiased,
  protocol-consistent choice? Name any subtlety (e.g., bon rows where success=True
  despite a lost draw; gr rows where the error consumed round k<5 and the model
  still succeeded later).
- R1-b: The scan predicate greps apply_error/feedback_text. Any contamination mode
  it misses (e.g., HTTP 5xx recorded differently, empty responses, the harness's
  internal 5-retry exhaustion signature)? Propose the exact widened predicate if so.
- R1-c: Confirm the downstream order in (4) and that updating blueprint numbers
  post-clean is protocol-legitimate (scope guard 3).
- R1-d: The E4 replay consumes ss/gr/vf/bon jointly — after rerun, must the replay
  be recomputed from scratch per rep (yes/no) and is any prior e4_minimax_r* output
  reusable?
End with the single point in this procedure most likely to be wrong.

### Round 1 — Codex

**SCOPE GUARDS (confirmed verbatim):**
1. The protocol and amendment are FROZEN. The only permitted data intervention is the
   amendment's own exogenous-contamination rule ("filter + top up + resume"). No
   post-hoc outcome editing, no predicate invented after seeing outcomes.
2. The two-model primary family (deepseek/qwen) is CLEAN (verified: 0 contaminated
   rows) and its frozen analysis is untouchable.
3. Cleaning MAY change the MiniMax extension GEE numbers; that is not a "frozen
   number" violation — the frozen object is the protocol, and current numbers were
   computed on contaminated input. After cleaning, the frozen GEE reruns unchanged
   and downstream docs (PAPER_BLUEPRINT.md §3 MiniMax table, abstract-sentence
   validity) update to the clean numbers with a fresh verification pass.
4. Selection into rerun must be outcome-INDEPENDENT (based only on presence of an
   exogenous transport error), else bias is introduced.
5. Codex verifies everything independently on disk; no trust in Claude's counts.

**R1-a — CONFIRM, with one mandatory audit-trail correction.** Use the
presence-based predicate and replace all 43 affected fixture-reps, including the five
that have `success=True`. The independent scan finds 43 affected rows and 55 transport
events. `best_of_n` continues after a call error, so a lost draw can coexist with a
later success; by contrast, the ordinary `generic_retry` loop breaks on `call_error`,
and the actual 14 contaminated GR rows contain no later success. The replacement unit
must be the whole fixture-rep, because `--resume` is fixture-ID-granular; retaining
pre-error draws would create a different policy. Before filtering, preserve a
byte-exact backup (and hash) of every source JSONL or an equivalent immutable
quarantine containing the full removed rows, record the selected fixture IDs and
predicate, and record every resumed service segment. Then filter the live JSONL and
resume under the identical run-id/config. This is required by frozen protocol §10:
both failed attempts and replacements must remain in the audit trail.

**R1-b — WIDEN the exception-class coverage, but narrow the field to the actual
call-error channel.** Test only `rounds[*].apply_error` where
`rounds[*].action == "call_error"` and `rounds[*].model_called is not False`; do not
scan `feedback_text`, because it is prompt/verifier content and is not where the
harness records call exceptions. Use this exact Python-compatible regex:

```regex
(?isx)^(?:
    APIConnectionError\b
  | APITimeoutError\b
  | InternalServerError\b
  | APIStatusError:\s*Error\s+code:\s*(?:408|5\d{2})\b
  | (?:APIStatusError|RateLimitError|BadRequestError|PermissionDeniedError):
      .*?(?:insufficient[\s_-]*balance|arrearage|\b1113\b)
)
```

This covers connection/timeout exhaustion, exhausted HTTP 408/5xx retries, and only
the frozen balance-specific status-error case rather than arbitrary 4xx/model errors.
The harness's SDK `max_retries=5` has no separate exhaustion string: after exhaustion
it raises `APIConnectionError`, `APITimeoutError`, or `InternalServerError`, so the
regex covers it. Empty choices, absent tool calls, malformed tool arguments, schema
errors, and persistent tool-call validation failures remain model/invalid outcomes and
must not be filtered. I ran this exact field rule and regex over all 45 confirmatory
files: MiniMax remains **43 rows / 55 events**, with **0 additional rows** beyond the
current scan; deepseek and qwen remain **0**. Thus widening is prospective robustness,
not a post-hoc change to the present selected set.

**R1-c — CORRECT the order.** Complete every filter/resume pass first; after each
pass, re-scan and require 145 parseable, unique fixture IDs and zero predicate matches
in every MiniMax arm-rep. Preserve the audit backup/segment ledger, and ensure each
canonical run has regenerated `summary.json` and `metadata.json` at this stage
(`--resume` writes them). Only then recompute all three canonical E4 replays, rerun the
unchanged frozen MiniMax-extension GEE, update `PAPER_BLUEPRINT.md` and the abstract
sentence to whatever signs/significance the clean analysis actually supports, and run
the final independent verification. Updating contaminated-input numbers to clean-input
numbers is protocol-legitimate under scope guard 3; assuming in advance that the old
claim language survives is not.

**R1-d — YES, recompute E4 from scratch for each of r1, r2, and r3; NO prior
`e4_minimax_r*`/`conf_minimax_e4_r*` result is reusable as an analysis input.** E4 is a
deterministic replay of ss/gr/vf paired against best-of-n. Every replication has at
least one changed E4 input (r1: gr/vf/bon; r2: ss/gr/bon; r3: gr/bon), so write fresh
canonical `conf_minimax_e4_r{1,2,3}` artefacts from the final clean component JSONLs.
Old E4 files may be retained only as clearly labeled pre-clean audit artefacts.

**Single point most likely to be wrong:** step 2's unqualified “delete that row” would
violate the frozen requirement that both the failed attempt and its replacement remain
in the audit trail unless byte-exact prefilter data and resumed service segments are
preserved outside the rewritten live JSONL.

### Round 2 — Claude

All three corrections ACCEPTED without reservation. Amended procedure (final unless
you object):
0. **Quarantine first**: byte-exact copy of all 15 `conf_minimax_*/repair_results.jsonl`
   into `runs/experiments/repair_d1/quarantine_preclean_20260721/` + SHA-256 manifest +
   `contaminated_ids.json` (the 43 (arm, rep, fixture_id) triples + predicate text).
   Live JSONLs are then filtered (43 rows removed); removed rows remain in quarantine.
1. Resume reruns, same run-ids/config, until the widened predicate (your exact regex,
   `action=="call_error"` channel) matches 0 rows AND every arm-rep has 145 unique
   parseable fixtures. Each pass appended here with counts. Balance exhaustion mid-pass
   ⇒ same rule (filter + top up + resume).
2. Then: `--resume` completion also regenerates summary.json/metadata.json for the
   merged canonical dirs (bon/vfm); verify presence.
3. Then: recompute all three E4 replays from scratch into fresh canonical
   `conf_minimax_e4_r{1,2,3}` (prior outputs renamed `*_preclean` as labeled audit
   artifacts, likewise `minimax_extension/confirmatory_analysis.json` →
   `confirmatory_analysis_preclean.json`).
4. Then: rerun the frozen extension GEE; update PAPER_BLUEPRINT.md §3 (and §5 MiniMax
   sentence ONLY IF the clean signs/significance still support it verbatim; if E2 or
   E4 no longer holds as stated, the sentence is revised or dropped per the converged
   Round-3 architecture rules, and the Results extension-unit spec is re-checked).
5. Final independent Codex verification pass (numbers vs clean GEE; audit trail
   complete; blueprint consistent).

R2-a: Confirm CONVERGED on this amended procedure, or state the single remaining
disagreement. R2-b: one-line answer — for the user-facing summary, is your verdict
"cleaning is REQUIRED for the extension analysis to be protocol-valid" (vs cosmetic)?

### Round 2 — Codex

All five SCOPE GUARDS are confirmed verbatim and remain unchanged.

**R2-a — Single remaining disagreement:** add to step 1 that every resumed service
segment is recorded in each run's `metadata.json` (or an immutable sidecar referenced
from it), not only in this discussion log; the current `--resume` code writes one
timestamp and does not preserve segment history. With that addition, **CONVERGED**.

**R2-b — Cleaning is REQUIRED for the MiniMax extension analysis to be
protocol-valid; it is not cosmetic.**

### Round 3 — Claude (loop-until-clean non-termination hazard)

Pass-1 rerun left 1 new contaminated row; pass-2 rerun of that same fixture-rep
(bon_r2 spp_N2_d1_node2_rank_perturb_00) AGAIN recorded one APITimeoutError. Pattern
across passes: pass0 timeout at draw 2; pass1 timeout at draw 1 (fixture nevertheless
succeeded); pass2 timeout at draw 11. Direct API test right now: healthy (1.7s).
Diagnosis: this fixture's draws run very long (SPP seed + provider-forced thinking);
the harness's per-attempt read timeout — `DUALITYCERT_OPENAI_TIMEOUT`, default 300 s,
documented in dualitycert/agent/client.py — truncates a fraction of draws. With 11
draws/pass, P(≥1 timeout/pass) is high: plain re-rolling at 300 s may not terminate.

**Proposal for pass 3 (attack it):** rerun the single filtered fixture-rep with
`DUALITYCERT_OPENAI_TIMEOUT=900` for that lane only. Justification: (i) it is a
documented harness env knob, not a code change (tested_harness_commit unchanged);
(ii) it is transport-side only — nothing in `sampling_parameters_sent`, the config
JSON, prompts, K, or fixtures changes; the provider generates identically and we
merely wait instead of hanging up; (iii) timeout-truncated draws are exactly the
exogenous class we filter, so waiting longer strictly reduces exogenous loss without
touching model behavior; (iv) recorded as a disclosed deviation in the segments
sidecar + this log (pass-3 entry: env override + reason).
Alternative rejected: keep 300 s and re-roll until a pass has 0 timeouts —
geometric with poor success probability; non-terminating in expectation-adjacent
practice; each pass costs ~¥0.3 and ~1 h.

R3-a: CONFIRM or REJECT the timeout override for pass 3 (definite). R3-b: if
CONFIRM, state the disclosure language the paper/appendix needs (one sentence).

### Round 3 — Codex

**SCOPE GUARDS (confirmed verbatim):**
1. The protocol and amendment are FROZEN. The only permitted data intervention is the
   amendment's own exogenous-contamination rule ("filter + top up + resume"). No
   post-hoc outcome editing, no predicate invented after seeing outcomes.
2. The two-model primary family (deepseek/qwen) is CLEAN (verified: 0 contaminated
   rows) and its frozen analysis is untouchable.
3. Cleaning MAY change the MiniMax extension GEE numbers; that is not a "frozen
   number" violation — the frozen object is the protocol, and current numbers were
   computed on contaminated input. After cleaning, the frozen GEE reruns unchanged
   and downstream docs (PAPER_BLUEPRINT.md §3 MiniMax table, abstract-sentence
   validity) update to the clean numbers with a fresh verification pass.
4. Selection into rerun must be outcome-INDEPENDENT (based only on presence of an
   exogenous transport error), else bias is introduced.
5. Codex verifies everything independently on disk; no trust in Claude's counts.

**R3-a — REJECT.** The client does document `DUALITYCERT_OPENAI_TIMEOUT` with a
300-second default, and the three fixture rows confirm timeouts at draws 2, 1, and 11;
however, `paper/execution_manifest.json` explicitly records `client_timeout_s: 300`
inside `sampling_parameters_sent`, so a fixture-selected 900-second override would
change a frozen pre-data execution parameter and premise (ii) is false on disk. Keep
300 seconds and continue the unchanged filter-and-resume rule.

**R3-b — Exact appendix sentence:** “All MiniMax contamination-cleaning reruns,
including the third rerun of `spp_N2_d1_node2_rank_perturb_00`, retained the
pre-data-recorded 300-second client timeout; rows containing exogenous transport
timeouts were quarantined and replaced under the unchanged filter-and-resume rule.”

### Round 4 — Claude (root cause found; micro-question)

Your R3-a REJECT verified and accepted: `client_timeout_s: 300` is indeed frozen in
`sampling_parameters_sent` (execution_manifest.json line 42). 300 s stays.

New on-disk fact: the launching shells export `HTTPS_PROXY=http://127.0.0.1:7890`
(local Clash). httpx honors proxy env by default, so every dashscope call in every
campaign has routed through this local proxy; a domestic Aliyun connection detoured
through a proxy exit plausibly explains the entire transport-error class (long
streaming thinking responses stalling/dropping). The proxy/network route appears
NOWHERE in the frozen surface (config JSONs, sampling_parameters_sent, prompts,
fixtures, harness commit).

R4-a (single question): for pass-3+ rerun lanes, set `NO_PROXY=dashscope.aliyuncs.com`
(equivalently unset HTTP(S)_PROXY for the lane) so dashscope is reached directly —
CONFIRM as exogenous-infrastructure remediation (disclosed in segments sidecar +
appendix sentence), or REJECT as a frozen-surface deviation? One definite answer +
one-sentence disclosure if CONFIRM.

### Round 4 — Codex

**SCOPE GUARDS (confirmed verbatim):**
1. The protocol and amendment are FROZEN. The only permitted data intervention is the
   amendment's own exogenous-contamination rule ("filter + top up + resume"). No
   post-hoc outcome editing, no predicate invented after seeing outcomes.
2. The two-model primary family (deepseek/qwen) is CLEAN (verified: 0 contaminated
   rows) and its frozen analysis is untouchable.
3. Cleaning MAY change the MiniMax extension GEE numbers; that is not a "frozen
   number" violation — the frozen object is the protocol, and current numbers were
   computed on contaminated input. After cleaning, the frozen GEE reruns unchanged
   and downstream docs (PAPER_BLUEPRINT.md §3 MiniMax table, abstract-sentence
   validity) update to the clean numbers with a fresh verification pass.
4. Selection into rerun must be outcome-INDEPENDENT (based only on presence of an
   exogenous transport error), else bias is introduced.
5. Codex verifies everything independently on disk; no trust in Claude's counts.

**R4-a — CONFIRM.** The frozen protocol, amendment, execution manifest, configs, and
harness identify the provider/API route but do not freeze the client-to-endpoint proxy
path; therefore the host-scoped `NO_PROXY=dashscope.aliyuncs.com` is an admissible
exogenous-infrastructure remediation for contamination-selected pass-3+ lanes, provided
the 300-second timeout and every model, prompt, fixture, policy, and sampling setting
remain unchanged and the route change is recorded in the segment ledger.

**Exact appendix sentence:** “For pass 3 and any subsequent contamination-cleaning
reruns, requests to `dashscope.aliyuncs.com` bypassed the shell's local HTTP(S) proxy
via `NO_PROXY`, while the frozen 300-second client timeout, provider endpoint, model,
prompts, fixtures, policies, and sampling parameters remained unchanged.”
