# Paper-scale experiment harness

This document covers the `dualitycert.experiments` package — the
reproducible framework that runs the three-layer Phase 2c paper
experiments on top of the locked Phase 2c-a detection MVP
(`dualitycert.benchmark`) and the verifier core (`dualitycert.qft`).

The MVP is **not modified**: the experiments package reuses the
sanitizer, the verifier, and the Seiberg mutation / R-repair engine, and
adds configs, a manifest format, verifier-gated generation, the
single-shot (Layer A/B) and repair (Layer C) runners, and statistics.

## The three layers

- **Layer A — Detection.** The LLM sees a blind sanitized
  `(Theory A, Theory B)` pair and predicts `dual` / `not_dual`.
- **Layer B — Diagnosis.** The LLM predicts which failure-mode
  categories the pair violates (`anomaly`, `superpotential`, `r_charge`,
  `chiral_ring`, `rank`, `unknown`), scored against the verifier's
  failed obligations.
- **Layer C — Repair.** The LLM iteratively edits Theory B; the verifier
  checks each attempt. Four arms isolate the value of verifier feedback.

## Package map

| Module | Role |
|---|---|
| `experiments/config.py` | `ExperimentConfig` / `VerifierConfig` / `RepairConfig` / `ModelConfig`, JSON load/save, hashing |
| `experiments/manifest.py` | `ManifestRecord`, `AttritionRecord`, `SizeCovariates`, JSONL + CSV I/O |
| `experiments/verifier.py` | verifier wrapper with the chiral-ring cutoff knob + obligation→category map |
| `experiments/perturbations.py` | the standardized perturbation operators (pure edits) |
| `experiments/chains.py` | depth-K `generate_mutation_chain` + `apply_single_seiberg_mutation` (single-step move) |
| `experiments/generation.py` | verifier-gated depth×class fixture generation |
| `agent/diagnosis.py` | single-call diagnosis (parallel to `agent/detection.py`) |
| `agent/dryrun.py` | `DryRunModelClient` (offline, deterministic, no API key) |
| `experiments/single_shot.py` | Layer A/B runner |
| `experiments/repair.py` | Layer C runner + `score_repair` |
| `experiments/jsonpatch.py` | RFC-6902 add/remove/replace applier |
| `experiments/scoring.py` | detection + diagnosis scoring |
| `experiments/stats.py` | Wilson CIs, per-cell tables, tidy CSV export |
| `experiments/cli.py` | the `dualitycert` subcommands |

## Quickstart (all dry-run, no API key)

```bash
# 1. Generate a verifier-gated manifest from the MVP config.
dualitycert generate-fixtures --config configs/mvp.json --out runs/mvp

# 2. (optional) Re-verify the manifest as a dataset-integrity check.
dualitycert verify-manifest --manifest runs/mvp/manifest.jsonl --out runs/mvp/verified

# 3. Single-shot detection + diagnosis with the offline dry-run client.
dualitycert run-single-shot --manifest runs/mvp/manifest.jsonl \
    --config configs/mvp.json --model dryrun --out runs/mvp_singleshot

# 4. Re-score existing model outputs against the manifest.
dualitycert score-single-shot --results runs/mvp_singleshot/*/model_outputs.jsonl \
    --manifest runs/mvp/manifest.jsonl --out runs/mvp_singleshot/scores

# 5. Repair loop (verifier_feedback arm), dry-run.
dualitycert run-repair-loop --manifest runs/mvp/manifest.jsonl \
    --config configs/paper_repair.json --arm verifier_feedback \
    --model dryrun --out runs/repair_dryrun

# 6. Score a repair run.
dualitycert score-repair --run runs/repair_dryrun/<run_id> --out runs/repair_dryrun/scores
```

`scripts/run_experiment_dryrun.py` runs steps 1/3/5 end-to-end in-process
as a smoke test.

## Configs

Three JSON configs ship under `configs/`:

- `configs/mvp.json` — reproduces the locked depth=1 MVP (L=3,
  `phase2c_a_detection` profile, six fixture classes).
- `configs/paper_detection.json` — depths `[1,2,3,4]` × seven classes;
  depths ≥ 2 route to attrition until the engine supports them (see
  below).
- `configs/paper_repair.json` — repair config with `K=5`,
  `feedback_mode=verifier_feedback`, **feedback verifier at L=3 and final
  verifier at the stricter L=6** (the anti-gaming guardrail).

Key fields: `depths`, `fixture_classes`, `n_per_cell`, `seed`,
`verifier.{duality_profile,chiral_ring_max_length,require_r_graded}`,
`model.{provider,model,max_tokens}`,
`repair.{max_rounds,feedback_mode,feedback_detail,feedback_verifier,final_eval_verifier}`,
`output_dir`, `split`.

## Manifest schema

`runs/<...>/manifest.jsonl` — one JSON object per fixture:

| Field | Meaning |
|---|---|
| `fixture_id` | stable deterministic id |
| `seed_id` | the rng sub-seed for this fixture |
| `mutation_chain_id` | the chain that built the positive (or `null`) |
| `depth` | requested cell depth |
| `chain_depth` | generated chain length (moves applied; = `depth` on success) |
| `mutation_node_sequence` | the node mutated at each step |
| `intermediate_hashes` | canonical hashes `h0..h_K` of `T0..T_K` |
| `final_theory_hash` | canonical hash of `T_K` (the candidate) |
| `perturbation_class` | `positive` / `drop_w_term` / `flip_w_sign` / `r_charge_perturb` / `rank_perturb` / `trivial_rank` / `wrong_pair` |
| `label` / `verifier_status` | `CERTIFIED` or `FAILED` (manifest is verifier-gated) |
| `repairable` | true for the four repairable negative classes |
| `theory_a_path` / `theory_b_path` | theory JSON files, relative to the manifest |
| `sanitized` | `false` (theories stored raw; the runner sanitizes at prompt time) |
| `failed_obligations` | `[{name, category}, ...]` |
| `verifier_config_hash` / `verifier_config` | the gating verifier settings |
| `size_covariates` | nodes / fields / W-terms / max monomial length / R-bearing fields / token estimate |
| `generation_metadata` | `rng_seed`, `generated_at`, `generator_version`, `git_commit` |
| `perturbation_metadata` | exactly what the operator changed |
| `source`, `split` | seed family, dataset split label |

`runs/<...>/attrition.jsonl` records every excluded attempt with an
`attrition_reason` ∈ `{UNKNOWN, NOT_APPLICABLE, OUT_OF_SCOPE,
verifier_error, duplicate, schema_invalid, depth_not_implemented,
unexpected_label, generator_discard}`. `unexpected_label` covers silent
misses (a perturbation the verifier did not catch); `depth_not_implemented`
covers depth ≥ 2 cells.

`manifest.csv` is a flat one-row-per-fixture export of the same data.

## Output files

- `generate-fixtures`: `manifest.jsonl`, `manifest.csv`,
  `attrition.jsonl`, `config.json`, `theories/*.json`.
- `run-single-shot`: `<run_id>/{model_outputs.jsonl, scored.jsonl,
  scored.csv, summary.json, metadata.json, cell_tables.json,
  tidy_detection.csv}`.
- `run-repair-loop`: `<run_id>/{repair_results.jsonl, summary.json,
  metadata.json}`.
- `score-repair`: `{summary.json, cell_tables.json, tidy_repair.csv}`.

`tidy_*.csv` are one-row-per-fixture×model×arm files ready for external
mixed-effects (GLMM) modeling in R/Python. We do **not** fit a GLMM here;
the tidy CSV is the handoff. `cell_tables.json` carries per-depth /
per-class / per-cell proportions with **Wilson 95% confidence
intervals**.

## Scoring

- **Detection**: accuracy (invalid output counted as wrong), balanced
  accuracy, always-`not_dual` / always-`dual` baselines, per-class,
  confusion matrix, separate `invalid_rate`.
- **Diagnosis**: the model returns two fields — `failure_modes`
  (PRIMARY: verifier obligation categories `anomaly` / `superpotential`
  / `r_charge` / `chiral_ring` / `unknown`) and `suspected_cause`
  (SECONDARY: the upstream perturbation `drop_w_term` / `flip_w_sign` /
  `r_charge_perturb` / `rank_perturb` / `wrong_pair` / `unknown`).
  Primary scoring uses `failure_modes`: exact-set match + macro-F1 over
  a **fixed** label vocabulary (the four obligation categories, so the
  metric is comparable across runs). `suspected_cause` is scored only as
  secondary analysis. Note there is no `rank` obligation — a rank error
  surfaces as an anomaly failure; `rank_perturb` lives in
  `suspected_cause`.
- **Repair**: `success@1/3/5` (judged by the **final** verifier),
  iterations-to-success, verifier-calls-per-success, invalid-JSON rate,
  out-of-scope rate, abstention rate, do-no-harm rate on positives,
  mean edit distance, `generalization_to_final_check` gap, per-depth /
  per-class breakdowns. In `force_model_on_certified` challenge mode it
  additionally reports `harm_rate` and `unnecessary_edit_rate`.

## Plugging in a real model provider

Everything above runs offline with `--model dryrun`
(`DryRunModelClient`). To run live against Anthropic:

```bash
pip install -e .[llm]
export ANTHROPIC_API_KEY=sk-...
dualitycert run-single-shot --manifest runs/mvp/manifest.jsonl \
    --config configs/mvp.json --model claude-sonnet-4-6 --out runs/mvp_live
```

`--model <id>` (anything other than `dryrun`) uses
`dualitycert.agent.client.AnthropicAdapter`. Any object implementing the
`LLMClient` protocol (`complete` + `complete_structured`) can be dropped
in. Unit tests never hit the network.

## Anti-gaming guardrail (chiral-ring cutoff L)

The bounded chiral-ring check is exact only up to a cutoff word length
`L = claim.metadata["bounded_chiral_ring"]["max_length"]` (default 6,
capped at 8). A repair could "pass" at a lenient `L_feedback` but fail at
a stricter `L_eval`. The repair loop therefore separates:

- `RepairConfig.feedback_verifier` — what the model is scored/feedback'd
  against during the loop;
- `RepairConfig.final_eval_verifier` — what determines true success.

Success is always judged by the final verifier. When a candidate passes
the feedback verifier but fails the final one, `success=False` and
`generalization_to_final_check=False` flags the gap. The model never
supplies verifier settings (they come only from config), and patches
targeting verifier metadata are rejected.

## Depth-K mutation chains (Phase 2d)

`generate_mutation_chain(seed_theory, depth, rng, constraints,
verifier_config=...)` composes `depth` single-node Seiberg moves
(`apply_single_seiberg_mutation` = `mutate_bare` → `integrate_linear_fields`
→ `repair_r_charges`, the same pipeline the depth-1 MVP positives use)
from a seed `T0` to a final `T_K`. The positive fixture pair is
`(T0, T_K)`; negative perturbations are applied to `T_K`.

**`depth` is the GENERATED chain length** — the number of moves applied —
**not** a proven minimal mutation distance. Records expose it as
`chain_depth` / `depth_requested` / `depth_realized`. We make no
shortest-path / minimal-duality-depth claim.

Node selection at each step is deterministic under `rng` (the first
step prefers the seed's pinned node so depth-1 reproduces the locked MVP
fixtures). A step is rejected — and another node tried, up to
`chain.max_attempts_per_step` — if the move fails, immediately
backtracks (`T_i == T_{i-2}`), repeats an earlier state, exceeds a size
budget, is schema-invalid, or fails adjacent verification. depth ≥ 2
generation retries the whole chain up to `chain.max_chain_attempts_per_cell`
with fresh rng.

### Verification policy (configurable)

For a chain `T0 → T1 → … → T_K`:

- `chain.verify_adjacent_steps` (default **true**): every
  `(T_{i-1}, T_i)` must verify CERTIFIED, else the step is rejected.
  This is conservative — it only composes *verified* single duals.
- `chain.verify_seed_to_final` (default **true**): the `(T0, T_K)`
  endpoint pair must verify CERTIFIED for the positive to enter the main
  manifest. **Success is always judged by this seed-to-final check.**

Empirically on the current seeds: with adjacent verification ON, no
depth-2 positive is reachable (dp0's dual is outside single-step MVP
scope; every f0 depth-2 adjacent pair fails) → honest attrition. With
**seed-to-final gating only** (adjacent OFF, see
`configs/paper_detection_dev_depth2.json`), F_0 yields genuine depth-2
CERTIFIED duals whose intermediate theory is mechanical scaffolding (not
itself required to be a dual). No depth-2 examples are ever fabricated.

### R-charge policy: judge ① (given) vs judge ②a (superconformal)

`VerifierConfig.r_charge_policy` selects how a claim's R-charge is judged:

- **`"given"`** (default — judge ①): the claim's R is trusted and only
  checked for consistency (`R(W)=2`, anomaly-freedom) and duality
  matching. This is the locked behavior; it is **not serialized when
  default**, so existing config hashes are byte-stable.
- **`"superconformal"`** (judge ②a): the claim must carry **the**
  superconformal (a-maximized) R. The a-maximization audit
  (`superconformal R-charge audit`) recomputes the superconformal R from
  the structure and kills a wrong-R claim *before* the duality
  comparison — an ill-specified theory does not merit a duality verdict.
  Requires the optional `[amax]` extra (sympy).

Under `"superconformal"`, `generate_fixtures` substitutes the
superconformal R into both sides of every positive (via
`qft.a_maximization.with_superconformal_r`) before gating — rational for
the symmetric families (dp0 / f0 / c3_z2z2), an exact algebraic number
for the irrational-R families (dp1 / dp2 / spp, e.g. `sqrt(97)` on SPP).
The mutation chain's *internal* verification still runs under judge ①
(the engine emits a rational-feasible R; the ②a audit applies only to the
final substituted claim), so a family whose electric R is symmetric but
whose superconformal R is irrational (SPP) is not killed before
substitution. a-max failure on a positive routes it to attrition
(`OUT_OF_SCOPE`), never a fabricated claim. The substitution is fully
gated on the flag, so judge-① generation is byte-for-byte unchanged.

The audit is a **strictly stronger gate**: it catches negatives judge ①
silently misses (e.g. `drop_w_term` on the non-chiral c3_z2z2 / spp
duals, whose dropped term shifts the superconformal R). The smoke config
`configs/smoke_superconformal.json` is the all-seed depth-1 dataset under
this policy.

### Strict completeness (replaces the old depth preflight)

Generation is **strict by default**: after generating, if any requested
`(depth × class)` cell produced zero main fixtures,
`generate_fixtures` raises `IncompleteCellsError` listing the empty
cells. This keeps a paper run from silently shipping partial coverage.
The shipped `paper_*` configs keep depths `[1,2,3,4]` and so fail
completeness until verified depth ≥ 2 chains exist on their seeds. Pass
`--allow-incomplete-cells` (or `allow_incomplete_cells: true`) to record
honest attrition instead — as the dev depth-2 config does.

### Tiny depth-2 dry run

```bash
dualitycert generate-fixtures \
    --config configs/paper_detection_dev_depth2.json \
    --out runs/dev_depth2 --allow-incomplete-cells
```

This produces depth-1 fixtures plus real depth-2 fixtures from F_0
(positive + perturbed negatives) and routes dp0 depth-2 attempts to
attrition (`single_step_mutation_failed`).

### Chain attrition reasons

`no_valid_mutation_nodes`, `single_step_mutation_failed`,
`immediate_backtracking_rejected`, `repeated_state_rejected`,
`intermediate_schema_invalid`, `intermediate_out_of_scope`,
`adjacent_verifier_failed`, `adjacent_verifier_unknown`,
`final_verifier_failed`, `final_verifier_unknown`,
`exceeds_size_budget`, `duplicate_chain`, `duplicate_final_pair`,
`max_attempts_exceeded`.

### Known limitations

- `canonical_theory_hash` is a normalized-JSON hash, **not** a
  graph-isomorphism canonical form: dedup is sound (no false merges) but
  may keep isomorphic duplicates.
- depth ≥ 2 success depends on verifier scope and on theory-size growth
  along the chain (size budgets send oversized chains to attrition).
- "generated depth" is chain length only — **no** minimal-distance /
  shortest-path claim.

## Endpoint-pool pairing (Phase 2d-ext)

The mutation engine is a *benchmark generator*; the benchmark task is
endpoint QFTCert verification, not path reconstruction. So fixtures need
not always pair the seed `T0` with the chain end `T_K`. Set
`pair_generation_mode: "endpoint_pool"` (default is
`legacy_seed_endpoint`, which keeps the original `(T0, T_K)` behavior) to
instead:

1. **Build an endpoint pool** — for each curated seed (an *orbit*),
   mechanically expand depths `0..endpoint_pool.max_pool_depth`,
   collecting every reachable theory (deduped by canonical hash),
   tagged with `theory_id / seed_id / orbit_id / generation_depth /
   mutation_sequence / size`. No verifier runs during pool construction.
2. **Sample blind pairs** `(T_i, T_j)` and verifier-gate each. `pair_origin`:
   - `same_orbit_endpoint_pair` — same orbit → **positive iff CERTIFIED**
     (often *neither* side is the seed, e.g. two depth-1 magnetic phases);
   - `perturbed_endpoint_pair` — a certified pair with one side perturbed
     → repairable **negative iff FAILED**;
   - `cross_orbit_pair` / `size_matched_cross_pair` — different orbits
     (the latter within `size_match_tolerance`) → **negative iff FAILED**;
   - `wrong_pair` — legacy alias of cross-orbit.
   UNKNOWN / NOT_APPLICABLE / OUT_OF_SCOPE and unexpected labels go to
   attrition. `label_source` is always `endpoint_qftcert`.

A/B orientation is **balanced** (the lower-depth / seed theory is not
always side A); `pair_swapped` records the choice. Pairs are deduped by
the unordered pair of canonical hashes (displayed order stays
randomized). `perturbation_class` reuses the existing vocabulary
(`positive` / the four repairable classes / `wrong_pair`) so existing
scoring/diagnosis applies unchanged; the finer `pair_origin` taxonomy
lives in `pair_metadata`.

The manifest's `pair_metadata` records `theory_id_a/b`, `seed_id_a/b`,
`orbit_id_a/b`, `generation_depth_a/b`,
`pair_generation_depth_{max,sum,delta}`, `pair_origin`, `label_source`,
`generation_history_shown_to_model=false`, and `pair_swapped` (the key
ones are also flattened into `manifest.csv`). **None of this provenance
is ever shown to the model** — the runner sanitizes the two theories at
prompt time.

```bash
dualitycert generate-fixtures \
    --config configs/paper_detection_endpoint_pool.json \
    --out runs/endpoint_pool --allow-incomplete-cells
```

Sampling controls live under `endpoint_pool` in the config
(`max_pool_depth`, `max_endpoints_per_orbit`, `max_pairs_per_theory`,
`max_pairs_per_orbit`, `balance_pair_orientation`, `balance_depth_pairs`,
`allow_same_theory_pair`, `allow_same_hash_pair`, `size_match_tolerance`,
`n_perturbed_per_certified`, `pair_origins`).

### Known TODOs

- **depth ≥ 2 mutation chains** — implement multi-step chains in
  `chains.py` (the only place that raises today).
- **`llm_critic` arm** — the interface exists; a real critic client can
  be injected, otherwise a fixed non-grounded template is used. Wiring a
  dedicated critic model is left for the live run.
- **`trivial_rank`** — currently an alias of `rank_perturb`; a distinct
  trivial-perturbation set can be added if the paper needs it.
