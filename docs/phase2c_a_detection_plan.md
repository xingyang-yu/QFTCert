# Phase 2c-a Detection Benchmark (Design Lock, MVP)

**Status:** spec + design lock for Phase 2c-a, **MVP implemented and sealed**
(commit `e586456`, 2026-05-20 — same day as the design lock). The
detection benchmark is the first of three planned LLM evaluation layers
(2c-a / 2c-b / 2c-c, see §1). Design was closed with codex review on
2026-05-20; the 8-step implementation order in §"Implementation order"
landed end-to-end and the smoke + MVP fixture sets are committed under
`fixtures/`. Phase 2c0 (mutation engine) and Phase 2c1 (R-repair) are
sealed prerequisites (see `docs/phase2c0_mutation_engine.md`,
`docs/phase2c1_r_repair.md`).

This doc is the single source of truth for the Phase 2c-a contract. New
sessions picking up implementation should treat the rules in §3 as
fixed and surface design questions as discussion before changing them.

---

## 1. Phase 2c three-layer plan

```
Phase 2c-a: detection_loop    ← this spec
   yes/no on paired (electric, candidate); accuracy vs verifier ground truth

Phase 2c-b: diagnosis_loop
   LLM classifies failure mode (anomaly / W / R / chiral ring / unknown);
   alignment with verifier obligation failures

Phase 2c-c: repair_loop_v2
   LLM iteratively modifies theory under verifier feedback until pass;
   success rate / iterations / final status
```

Each layer is independently measurable. Story line: *single-shot LLM
detection is unreliable; verifier-grounded iteration improves it; each
layer's gain is attributable.* Phase 2c-a alone is the foundation — do
not bundle 2c-b/2c-c into it.

The existing `dualitycert/agent/repair_loop.py` is the v1 baseline for
the eventual 2c-c; 2c-a does **not** modify or refactor it.

## 2. Existing infrastructure to reuse (NOT re-build)

- `dualitycert/agent/client.py` — `LLMClient` Protocol + `AnthropicAdapter`
  + `MockLLMClient`. Extend (Rule 5), don't replace.
- `dualitycert/agent/repair_loop.py` — keep AS-IS. Do not refactor to
  "generalize" detection from it.
- `dualitycert/qft/critic.py::build_repair_prompt` — repair-loop only;
  detection has its own prompt template (§4).
- `scripts/run_experiment.py` + `aggregate_runs.py` — repair-loop CLI;
  detection writes its own script (mirror structure but separate code path).
- `ai_runs/` — repair-loop fixtures; detection writes to `fixtures/`
  (separate dir).

## 3. The 10 frozen design rules

### Rule 1: Detection task is independent of repair-loop.

New modules `dualitycert/agent/detection.py` + `dualitycert/benchmark/`
sit parallel to `dualitycert/agent/repair_loop.py`. No shared task
driver. `LLMClient` is shared but extended (Rule 5), not refactored.

**Why:** the three Phase 2c layers must be independently measurable;
coupling detection to repair (e.g. "detection is repair with
max_iterations=0") would entangle their signals.

### Rule 2: Input = blind (electric, candidate) pair.

LLM prompt contains ONLY:
- sanitized `electric` JSON
- sanitized `candidate` JSON
- a fixed question string

Everything else — `seed`, `mutation_depth`, `perturbation_type`,
`verifier_ground_truth`, fixture id — is **analysis-only metadata**,
never enters the prompt.

**Why:** the benchmark measures the LLM's physical judgment, not its
ability to read metadata hints. `mutation_depth` in the prompt would
let the LLM use it as a confidence cue ("depth-1 from dP_0 is probably
the dP_0 magnetic effective I've seen in training").

### Rule 3: Prompt JSON must be sanitized.

`mutate_bare` / `integrate_linear_fields` / `repair_r_charges` write
provenance into `name` (e.g. `"dP_0 toric (electric) (Seiberg-mutated at
node 0, bare) (integrated) (R-repaired)"`). If unstripped, the LLM can
answer by pattern-matching on the string `"Seiberg-mutated"` without
reading the quiver structure — that would inflate positive accuracy to
~100% with zero physical content, and the inflation would be
**asymmetric** (negatives don't go through the engine, so their name is
clean), giving a near-perfect-but-fake accuracy number.

Sanitize rule (implement in `dualitycert/benchmark/fixtures.py` or a
dedicated `sanitizer.py`):

```python
def sanitize_for_prompt(theory_json, *, theory_label: str) -> dict:
    """Strip provenance-leaking fields. theory_label is "Theory A" or "Theory B"."""
    n = len(theory_json["ranks"])
    return {
        "name": theory_label,                       # was "dP_0 (Seiberg-mutated ...)"
        "node_labels": [f"G{i}" for i in range(n)], # was "SU(3)_0" / "SU(2N)_0"
        "ranks": theory_json["ranks"],              # unchanged
        "u1_globals": theory_json["u1_globals"],    # unchanged
        "arrows": theory_json["arrows"],            # unchanged (labels X02[k] are structural, OK)
        "superpotential": theory_json["superpotential"],  # unchanged
    }
```

**`node_labels` matters:** `"SU(2N)_0"` literally leaks the rank
parametrization that's specific to the magnetic side of a Seiberg
duality. Replace with neutral `f"G{i}"` (just an opaque gauge group
label).

**Arrow labels `X{i}{j}[k]` are structural** (encode source/target
indices), not provenance — keep them. Same for R-charges, W
coefficients, ranks.

Both `electric` and `candidate` get sanitized; LLM sees "Theory A" +
"Theory B" only.

### Rule 4: Output = structured tool use, schema locked.

```python
DETECTION_DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["dual", "not_dual"]},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "reasoning": {"type": "string"},
    },
    "required": ["verdict", "confidence", "reasoning"],
}
```

Three-level confidence (not numeric 0..1) because:
- LLMs return 0.8/0.95 with no real granularity on a continuous scale
- 3-level enum forces coarse self-assessment; calibration analysis is
  a 3×2 contingency table, no binning needed

### Rule 5: LLM client gets a provider-neutral `complete_structured`.

Extend `LLMClient` Protocol (don't break the existing `complete`):

```python
class LLMClient(Protocol):
    def complete(self, *, model, system, user, max_tokens) -> str: ...
    # existing — repair-loop uses this, detection does not touch it

    def complete_structured(
        self, *, model, system, user, schema, tool_name, max_tokens,
    ) -> StructuredLLMResponse: ...
    # new — detection uses this; returns schema-validated dict + instrumentation


@dataclass(frozen=True)
class StructuredLLMResponse:
    data: dict                          # already validated against `schema`
    latency_s: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    raw_response: Any | None = None     # debugging only
```

Adapter strategy:
- `AnthropicAdapter.complete_structured` → uses Anthropic tool_use API
- `MockLLMClient.complete_structured` → pops from a
  `structured_responses: list[dict]` queue
- Cross-vendor fenced-JSON fallback adapter: **do not implement in MVP**
  (YAGNI; add when a second backend appears)

**Why a `StructuredLLMResponse` wrapper, not a plain dict:**
instrumentation not collected is data lost. Cost / latency can be
appended later by Anthropic SDK's `response.usage`; runner code
accepts `None` until then.

### Rule 6: Ground truth only accepts unambiguous verifier results.

Generator gating:

```python
if verifier_result.overall_status == Status.CERTIFIED:
    label = "dual"
    accept(fixture)
elif verifier_result.overall_status == Status.FAILED:
    label = "not_dual"
    accept(fixture)
else:
    # NOT_APPLICABLE / UNKNOWN / OUTWARD_OUT_OF_SCOPE / mixed
    discard(fixture); log_to_generation_artifact(reason="ambiguous_ground_truth")
```

**Why:** Phase 2c0's F_0 II boundary regression already showed that
`bounded_chiral_ring_consistency` can route through `NOT_APPLICABLE`
when P4 is broken upstream (see
`tests/test_mutation_engine.py::test_f0_phase_ii_mutation_topology_matches_but_trial_r_fails_mixed_anomaly`).
Calling these "not_dual" would punish the LLM for an answer where the
verifier itself has no verdict. Most pure-quiver fixtures fall to
CERTIFIED/FAILED, but the discard rule must be hard-coded in the
generator.

### Rule 7: Two-tier fixture sets.

| | Smoke set | MVP benchmark set |
|---|---|---|
| Size | 8–10 | ~30 |
| Purpose | pytest + MockLLMClient | first real LLM evaluation |
| In CI? | yes | no (cost + non-determinism) |
| File | `fixtures/detection_smoke.jsonl` | `fixtures/detection_mvp.jsonl` |
| LLM responses | canned per-fixture in `tests/test_detection_smoke.py` | live API call |

Smoke set pins LLM scoring + parse + sanitize behavior; MVP set
generates the paper accuracy number.

### Rule 8: Positive generation strategy.

```python
candidate = repair_r_charges(
    integrate_linear_fields(
        mutate_bare(electric_json, node=v)
    )
)["representative"]
```

MVP scope:
- depth = 1 only (no chain runner this phase)
- seeds = dP_0 toric + F_0 II electric trial only
- mutate at every legal `node v` per seed

Expected fixture count: dP_0 (3 nodes) + F_0 II positives. F_0 II nodes
are verifier-gated case-by-case (the §"Expected fixture count" estimate
during design lock was conservative — at implementation time every F_0
II node 0/1/2/3 turned out to pass `mutate_bare`, and the Rule 6 gate
also CERTIFIED them after R-repair; only a subset is needed to fill the
budget). The frozen MVP composition picks **dP_0 N=3 at all three nodes
+ dP_0 N=4 at node 0 + F_0 II N=3 at nodes 0 and 2** for 6 positives
total (see `scripts/generate_detection_fixtures.py` `_mvp_positives()`).
The augmentation over N ∈ {3, 4} on dP_0 is preserved as a hedge against
LLM memorization of the canonical N=3 dP_0 dual.

**Avoid N=2** in MVP positives. SU(2) hits low-rank special cases that
Phase 3 boundary-scope marking is intended to flag (`SU(2)`,
`Nf = Nc + 1`, low rank → OUT_OF_SCOPE); using it in MVP positives
risks the verifier-gating in Rule 6 routing the fixture through
OUT_OF_SCOPE → discard, wasting generator effort. Every augmented
fixture still passes Rule 6 gating before acceptance.

### Rule 9: Negative generation strategy.

**Main negatives (Type-4 + Type-3 naive):**

- **Type-4 W drop** (~8): take a positive fixture's candidate, drop one
  W term. Already validated as a strong adversarial in
  `tests/test_mutation_engine.py::test_w_drop_on_engine_output_fails_at_length_3_r_charge_2`
  (Phase 2b sediment).
- **Type-4 W sign swap** (~4): flip the coefficient sign on one W term.
  MVP **does not** do general "swap to arbitrary invalid value" (Phase
  2b found some coefficient changes are silent misses); sign-flip is
  enough to break the verifier reliably.
- **Type-3 R naive** (~8): randomly perturb a single field's R by a
  small rational (e.g. +1/3 or -1/3); do NOT enforce W=2 preservation.
  Verifier rejects on whichever channel breaks first (W consistency or
  mixed anomaly).

**Baseline / control negatives:**

- **Type-1/2 trivial** (~2): change a single rank by ±1, or add/remove
  one arrow multiplicity. LLM can probably catch these from memory;
  included only to calibrate the floor.
- **Wrong-pair** (~2): pair an unrelated (dP_0 electric, F_0 II
  candidate). Tests "can the LLM see that ranks don't even match" —
  sanity floor.

**Type-3 constrained** (R perturbed in the W-only kernel but outside
the full kernel, so W=2 holds but mixed anomaly breaks): **deferred to
post-MVP.** Requires a new helper around `repair_r_charges` to compute
the W-only kernel and project out the full-system kernel direction.
Add in Phase 2c-a-extended if the MVP shows LLM accuracy >90% on naive
Type-3.

**Total MVP fixture mix:**

```
positive:              6
Type-4 W drop:         8
Type-4 W sign swap:    4
Type-3 R naive:        8
Type-1/2 trivial:      2
wrong-pair:            2
─────────────────────────
total:                30
```

**Every negative must pass the verifier-gating in Rule 6.** Generators
retry with a different perturbation seed if the first attempt produces
CERTIFIED or ambiguous; after N retries (suggest N=10), discard and log.

### Rule 10: Persistence formats.

**Fixture files** (`fixtures/*.jsonl`): strict JSONL, one fixture per
line, encoded as

```python
json.dumps(obj, sort_keys=True, ensure_ascii=False)
```

No `indent=2` (would break "one record per line"). For human reading,
optionally write `fixtures/*.pretty.json` (a parallel non-JSONL
list-of-dicts file) — generated, never authoritative.

**Generation log** (`fixtures/<dataset>.generation.jsonl`): one entry
per generation *attempt* (accepted + discarded), each carrying:

```python
{
  "fixture_id": "dp0_node0_positive_001",
  "generation_status": "accepted" | "discarded",
  "discard_reason": str | None,
  "prompt_visible_fields": ["electric", "candidate"],  # explicit audit trail
  "verifier_ground_truth": {...},
  "metadata": {...}    # full provenance: source, seed, mutation_depth, perturbation, ...
}
```

**Fixture file itself** only contains accepted entries;
`prompt_visible_fields` and `generation_status` are NOT in the fixture
entries (implicit: all accepted, all blind-pair). Provenance metadata
IS in fixture entries (the analysis layer needs it).

**Runner outputs** (`runs/detection/<run_id>/`):

```
fixtures.jsonl     # input snapshot (sha-pinned reproducibility)
results.jsonl      # one line per sample: {fixture_id, llm_decision, ground_truth, correct, latency_s, input_tokens, output_tokens}
summary.json      # {n_total, accuracy, accuracy_by_class, accuracy_by_seed, accuracy_by_perturbation_type, confusion_matrix}
metadata.json     # {model, model_version, timestamp, fixture_set_hash, run_config}
```

`results.jsonl` is also strict JSONL (`indent=None`, `sort_keys=True`).

## 4. Locked module layout

```
dualitycert/agent/
  client.py              # extend: LLMClient.complete_structured, StructuredLLMResponse,
                         #         AnthropicAdapter.complete_structured, MockLLMClient extension
  detection.py           # NEW: run_detection(electric_json, candidate_json, *, client, model)
                         #      -> DetectionDecision (single call, no loop)
  repair_loop.py         # UNCHANGED

dualitycert/benchmark/   # NEW module
  __init__.py
  fixtures.py            # FixtureMetadata dataclass + JSONL I/O + sanitize_for_prompt()
  generators.py          # generate_positive(), perturb_type4_drop(), perturb_type4_sign_swap(),
                         # perturb_type3_r_naive(), perturb_type1_rank(), pair_wrong()
  runner.py              # run_detection_benchmark(fixtures_path, client, model)
                         # -> writes runs/detection/<run_id>/
  metrics.py             # accuracy, confusion matrix, per-class / per-seed / per-perturbation breakdown

tests/
  test_detection_smoke.py            # 8-10 fixture x MockLLMClient via pytest
  test_benchmark_generators.py       # unit tests: each generator + verifier-gating + sanitizer
  test_benchmark_sanitizer.py        # explicit tests that sanitize_for_prompt strips name/node_labels
                                     # and preserves arrows/W

scripts/
  generate_detection_fixtures.py     # build fixtures/detection_smoke.jsonl + fixtures/detection_mvp.jsonl
                                     # from seeds + RNG seed
  run_detection_benchmark.py         # run runner on fixtures/detection_mvp.jsonl against Anthropic API

fixtures/
  detection_smoke.jsonl              # ~10 accepted fixtures (committed to repo; deterministic from RNG seed)
  detection_smoke.generation.jsonl   # generation log (committed)
  detection_mvp.jsonl                # ~30 accepted fixtures (committed)
  detection_mvp.generation.jsonl     # generation log (committed)

runs/detection/<run_id>/             # gitignored — large + per-run
```

## 5. LLM prompt templates (locked)

System prompt (provider-neutral, no Anthropic-specific phrasing):

```
You are a theoretical physicist evaluating proposed 4d N=1 supersymmetric
gauge theory dualities.

You will see two theory JSONs labeled "Theory A" and "Theory B", each
encoding a quiver gauge theory: gauge group ranks, bifundamental matter
arrows with R-charges, and a superpotential of cubic+ monomials.

Your task: judge whether Theory A and Theory B are Seiberg-dual / IR-
equivalent under the standard scope (cubic gauge anomaly cancellation,
SU(N)^2 x U(1)_R mixed anomaly cancellation, R(W)=2 R-charge balance,
F-term ideal consistency, bounded chiral-ring multiplicity matching).

Use the provided structured-output tool to return your verdict with a
confidence level and a brief reasoning. Do not write any output outside
the tool call.
```

User message template:

```
Theory A (electric):
{sanitized_electric_json_indented}

Theory B (candidate dual):
{sanitized_candidate_json_indented}

Question: Are Theory A and Theory B Seiberg-dual / IR-equivalent under
the verifier scope described above?
```

`max_tokens = 2048` (enough for ~5-line reasoning + tool call).

## 6. Verifier ground truth schema in fixtures

```python
"verifier_ground_truth": {
    "overall_status": "CERTIFIED" | "FAILED",   # discard if anything else (Rule 6)
    "failed_obligations": [str, ...],            # empty for positives; obligation names for negatives
}
```

Do not store the full `details` (too large, redundant).

## 7. Implementation order (locked)

1. **`dualitycert/agent/client.py` extension** + `MockLLMClient.complete_structured`
   for tests. Smallest unit; pin via `tests/test_agent_client_structured.py`.
2. **`dualitycert/benchmark/fixtures.py`** with `sanitize_for_prompt()` and
   JSONL I/O. Pin via `tests/test_benchmark_sanitizer.py` (name /
   node_labels stripped, arrows / W / ranks preserved).
3. **`dualitycert/benchmark/generators.py`** — one generator per fixture
   class, each with built-in verifier-gating (Rule 6). Pin via
   `tests/test_benchmark_generators.py` (every accepted output passes
   its declared label; reproducible from RNG seed).
4. **`scripts/generate_detection_fixtures.py`** — produce
   `fixtures/detection_smoke.jsonl` + `fixtures/detection_mvp.jsonl`
   from seeds + RNG. Commit both files.
5. **`dualitycert/agent/detection.py`** with `run_detection()`
   (single-call). Pin via `tests/test_detection_smoke.py` (MockLLMClient
   + 10 canned responses).
6. **`dualitycert/benchmark/runner.py`** + **`dualitycert/benchmark/metrics.py`**
   — drive the smoke set through MockLLMClient, write to
   `runs/detection/<smoke_id>/`. Pin via runner unit test.
7. **`scripts/run_detection_benchmark.py`** — manual entry to drive the
   MVP set against the Anthropic API. Not in CI; user invokes when ready.
8. **First MVP run** on Sonnet 4.6 (or whichever Claude is current).
   Inspect `summary.json`. Local commit (embargo still in effect per
   the project's confidentiality posture).

## 8. Out of Phase 2c-a scope (deferred)

- **Mutation chain depth ≥ 2 positives.** Need a chain runner that
  composes `mutate_bare(integrate(...))` across nodes; deferred to
  2c-a-extended once the depth=1 baseline is stable.
- **Type-3 R constrained.** Needs a W-only kernel helper around
  `repair_r_charges`. Deferred per Rule 9.
- **Type-4 W add.** Adding a valid closed-walk W term that breaks
  F-ideal balance is constructively non-trivial. Drop + sign swap are
  sufficient for MVP.
- **Cross-vendor fenced-JSON fallback adapter.** Anthropic-only until a
  second backend is needed.
- **Multi-model comparison.** Single model (latest Sonnet) for MVP;
  cross-model panel deferred.
- **Cost optimization.** ~30 samples × ~800 tokens RT ≈ <$1/run; not
  worth optimizing for MVP scale.
- **Phase 2c-b (diagnosis) and Phase 2c-c (repair-loop v2).** Out of
  2c-a entirely. Each gets its own design lock.

## 9. Open questions for next session start

None known. All design decisions are locked above. If implementation
surfaces new questions (e.g. a sanitize rule edge case where a
`node_label` contains a non-Latin character, or the Anthropic SDK
tool_use API requires a different schema dialect than the JSON Schema
in Rule 4), surface as discussion before committing code.

## 10. Files to read first when picking up implementation

- `docs/phase2c1_r_repair.md` — predecessor spec; mutation engine +
  R-repair output is the source of positives.
- `dualitycert/agent/client.py` + `dualitycert/agent/repair_loop.py` —
  existing infrastructure to extend (not refactor).
- `dualitycert/qft/critic.py` — repair-loop's prompt builder;
  detection's is parallel, not derived.
- `dualitycert/qft/mutation_engine.py` + `dualitycert/qft/r_repair.py`
  — positives source.
- `tests/test_mutation_engine.py` (F_0 II fixtures) +
  `tests/test_r_repair.py` — pattern for fixture construction.
- `ai_runs/` directory — repair-loop fixture format reference (detection
  writes to `fixtures/` instead, but JSONL conventions can borrow).
- This file.
