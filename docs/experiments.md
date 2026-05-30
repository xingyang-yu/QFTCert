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
| `experiments/chains.py` | `generate_mutation_chain` (depth=1 wired; depth≥2 raises) |
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
| `depth` | mutation depth (1 today) |
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
- **Diagnosis**: exact-set match, macro-F1 over the category labels,
  per-category P/R/F1, `invalid_rate`.
- **Repair**: `success@1/3/5` (judged by the **final** verifier),
  iterations-to-success, verifier-calls-per-success, invalid-JSON rate,
  out-of-scope rate, abstention rate, do-no-harm rate on positives,
  mean edit distance, `generalization_to_final_check` gap, per-depth /
  per-class breakdowns.

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

## depth ≥ 2 support status

The single-node Seiberg engine (`dualitycert.qft.mutation_engine`)
supports exactly one mutation step today, so
`generate_mutation_chain(depth>=2)` raises `DepthNotImplementedError` and
generation routes those cells to attrition with reason
`depth_not_implemented`. **No deep chains are fabricated.** Configs may
already request depths `[1,2,3,4]`; only the depth ≥ 2 branch in
`experiments/chains.py` needs to change when multi-step mutation lands.

### Known TODOs

- **depth ≥ 2 mutation chains** — implement multi-step chains in
  `chains.py` (the only place that raises today).
- **`llm_critic` arm** — the interface exists; a real critic client can
  be injected, otherwise a fixed non-grounded template is used. Wiring a
  dedicated critic model is left for the live run.
- **`trivial_rank`** — currently an alias of `rank_perturb`; a distinct
  trivial-perturbation set can be added if the paper needs it.
