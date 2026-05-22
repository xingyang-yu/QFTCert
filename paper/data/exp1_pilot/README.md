# Exp 1 Pilot — depth=1 detection baseline

**Status:** pilot run, NOT the final paper number. To be re-run with a
larger fixture set (depth ∈ {1, 2, 3}) and a multi-model panel before
the table in the paper is locked.

## Run provenance

| Field | Value |
|---|---|
| Date (UTC) | 2026-05-20T23:27:46+00:00 |
| Model | `claude-sonnet-4-6` |
| max_tokens | 2048 |
| Fixture set | `fixtures/detection_mvp.jsonl` (30 samples) |
| Fixture set sha256 | `d4235f79583b56763179f59fb5825ce398d1205da08b7ea6e501ff0b848537c6` |
| Run id | `pilot_baseline_20260520` |
| Original run dir (gitignored) | `runs/detection/pilot_baseline_20260520/` |
| Mean latency / call | 11.6 s |
| Total wall time | ~5.8 min |
| Token usage | 95 846 input / 14 598 output |
| Approx cost (Sonnet 4.6 pricing) | ≈ $0.51 |

## Headline finding (read this carefully — raw accuracy is misleading)

Sonnet 4.6 implements a **degenerate constant-prediction policy**: it
labels every one of the 30 sanitized depth=1 pairs as `not_dual`. The
fixture set is class-imbalanced (24 negatives / 6 positives), so an
always-`not_dual` predictor scores 24/30 = 0.80 by construction.
**Sonnet's raw accuracy is exactly the always-`not_dual` baseline** —
the model has no discrimination above the trivial floor.

| metric | value | how to read |
|---|---|---|
| **raw accuracy** | **0.80 (24/30)** | DO NOT report as headline — it is the class-imbalance floor |
| **balanced accuracy** | **0.50 (chance)** | The actual headline number on this fixture set |
| **always-`not_dual` baseline** | **0.80** | Equal to raw accuracy → Sonnet is the trivial baseline |
| **always-`dual` baseline** | 0.20 | symmetric reference |
| **positive recall** (`dual` → `dual`) | **0/6 = 0.00** | Sonnet catches no positives |
| **negative recall** (`not_dual` → `not_dual`) | 24/24 = 1.00 | Trivially, because Sonnet always says `not_dual` |

Confusion matrix:

|  | LLM `dual` | LLM `not_dual` |
|---|---|---|
| GT `dual` | **0** | 6 |
| GT `not_dual` | 0 | **24** |

- False positives: 0
- False negatives: 6 (all positives misclassified)
- Confidence: every wrong call was rated `high` — Sonnet is
  high-confidence at being uniformly cautious, not at making physical
  judgments.

**Bottom line:** the right reading of this pilot is "Sonnet 4.6
single-shot has zero discriminative ability above the class-imbalance
baseline on sanitized depth=1 quiver duality pairs", not "Sonnet 4.6
achieves 80% accuracy".

## Specific physics failure mode read from `reasoning` field

Sonnet **does** invoke Seiberg duality (N_c → N_f − N_c) but
**miscounts the flavor index** of bifundamentals on quivers. It treats
arrow multiplicity as N_f, ignoring the source node's rank
contribution.

Example reasoning quote (positive `dp0_toric_N3_node1_positive_001`):

> "For node G1 in Theory A (rank 3), the effective number of flavors
> from adjacent arrows is 3+3=6, giving a dual rank N_f − N_c = 3, not
> 6 as in Theory B — therefore the gauge groups are inconsistent."

The correct count: each of the 3 incoming arrows from a rank-3 node
contributes N_other = 3 effective flavors, so N_f = 9 and the dual
rank is N_f − N_c = 9 − 3 = 6, which **matches** the candidate. The
model has the Seiberg formula but applies it without the multiplicity
factor.

Compounded with R-repaired R-charges that look non-canonical (e.g.
11/6, 1/3, 4/3 in F_0 II positives), Sonnet concludes "this is not the
dP_0 / F_0 II dual I have memorized" → confident `not_dual`.

## Per-class accuracy (Sonnet single-shot, sanitized depth=1)

| Class | n | accuracy |
|---|---|---|
| positive (none) | 6 | 0/6 = 0.00 |
| W drop | 8 | 8/8 = 1.00 |
| W sign swap | 4 | 4/4 = 1.00 |
| R naive | 8 | 8/8 = 1.00 |
| rank perturb | 2 | 2/2 = 1.00 |
| wrong pair | 2 | 2/2 = 1.00 |

The trivial discrimination structure (`100% recall on broken, 0% recall
on real`) is the point — the model is a constant `not_dual` predictor
on this distribution, not a duality detector.

## Per-source breakdown

| Source family | n | accuracy |
|---|---|---|
| dp0_toric | 22 | 18/22 = 0.818 |
| f0_phase_ii | 6 | 4/6 = 0.667 |
| dp0_toric × f0_phase_ii (wrong-pair) | 2 | 2/2 = 1.000 |

F_0 II is harder for Sonnet because all 4 F_0 II positives are false
negatives and there are no F_0 II negatives to dilute the score.

## Paper-narrative implications

1. **Headline framing** — "vanilla Sonnet 4.6 on sanitized 4d N=1
   quiver duality pairs implements a degenerate constant-prediction
   policy (always `not_dual`), yielding balanced accuracy = 0.50 —
   chance. The apparent raw accuracy of 0.80 reflects only the
   class-imbalance baseline (24/30 negatives in the fixture set).
   Reporting raw accuracy alone would be misleading on this
   distribution; balanced accuracy is the headline number." Any
   downstream paper text must use `balanced_accuracy` /
   `always_not_dual_baseline` from `summary.json`, not `accuracy`
   alone.

2. **Citeable failure mode** — bifundamental flavor miscounting in
   quiver Seiberg duality. Specific, namable, reproducible from the
   reasoning logs.

3. **Confidence calibration is broken** — every wrong call was
   high-confidence. The model is not aware of its uncertainty.

4. **Strengthens depth-extension argument** — if Sonnet cannot
   recognize sanitized canonical depth=1 dP_0, depth ≥ 2 will be at
   least as bad. The accuracy-vs-depth curve will be flat at the
   negative-base-rate ceiling.

5. **Strengthens diagnosis (2c-b) angle** — Sonnet *does* talk about
   ranks and R-charges in its reasoning. Diagnosis benchmark can ask
   "which obligation fails?" and score the predicted-failed-obligation
   list against the verifier's. Sonnet may be partially right on
   diagnosis even while being wrong on detection.

6. **Strengthens repair (2c-c) angle** — the repair loop's job is
   exactly to teach the model that N_f counts include the source rank
   multiplicity. Whether verifier feedback closes this gap is the
   experiment.

## What's NOT in this pilot (and why we don't read too much into it)

- **No comparison across model sizes** — Opus 4.7 and Haiku 4.5 likely
  behave differently (Opus presumably more permissive on positives, but
  unknown). Need a 3-model panel before claiming "Sonnet is the
  representative case".
- **Only depth=1 mutations** — every positive here is a single-step
  Seiberg dual of dP_0 or F_0 II. Depth ≥ 2 has yet to be tested.
- **n = 6 positives** is small. Adding more seed theories (Y^{p,q},
  L^{a,b,c}, conifold orbifolds) before final paper run.
- **Single run, no temperature sweep** — Anthropic API default is
  effectively deterministic for tool_use, but a second run with
  different seed would confirm reproducibility.

## Artefacts in this directory

- `results.jsonl` — 30 records, each with fixture_id, ground_truth,
  llm_decision, llm_confidence, llm_reasoning, correct, latency_s,
  input_tokens, output_tokens.
- `summary.json` — aggregated metrics produced by
  `dualitycert.benchmark.metrics.build_summary`.
- `metadata.json` — model, fixture_set_hash, timestamp, run_config.

`fixtures.jsonl` is NOT duplicated here; the run was on the committed
`fixtures/detection_mvp.jsonl` whose sha256 matches the
`fixture_set_hash` in `metadata.json`.

## Reproducing

```sh
# Verify fixture set integrity
sha256sum fixtures/detection_mvp.jsonl   # must match metadata.json::fixture_set_hash

# Re-run (will hit the live API and write to runs/detection/<new-id>/)
python scripts/run_detection_benchmark.py --run-id pilot_baseline_rerun
```

A re-run on the same fixture set should reproduce the headline numbers
up to LLM nondeterminism — verdicts are typically stable but reasoning
text and exact token counts will differ.
