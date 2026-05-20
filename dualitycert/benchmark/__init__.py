"""Detection benchmark infrastructure for the Phase 2c-a evaluation.

Sub-modules:
  - `fixtures` — Fixture / FixtureMetadata / GenerationLogEntry dataclasses,
    `sanitize_for_prompt()`, and JSONL I/O helpers.
  - `generators` — one builder per fixture class (positives + each
    negative class), each emitting an accepted Fixture or logging a
    discard reason. (Populated in Phase 2c-a Step 3.)
  - `runner` — drive a fixture set through an LLMClient, write per-run
    artefacts to `runs/detection/<run_id>/`. (Step 6.)
  - `metrics` — accuracy + breakdowns from `results.jsonl`. (Step 6.)

See `docs/phase2c_a_detection_plan.md` (and the project memory note of
the same name) for the locked design.
"""

from dualitycert.benchmark.fixtures import (
    Fixture,
    FixtureMetadata,
    GenerationLogEntry,
    fixture_from_dict,
    fixture_set_hash,
    fixture_to_dict,
    generation_entry_from_dict,
    generation_entry_to_dict,
    read_fixtures_jsonl,
    read_generation_log,
    sanitize_for_prompt,
    write_fixtures_jsonl,
    write_generation_log,
)
from dualitycert.benchmark.metrics import build_summary
from dualitycert.benchmark.runner import (
    DetectionRunResult,
    run_detection_benchmark,
)

__all__ = [
    "DetectionRunResult",
    "Fixture",
    "FixtureMetadata",
    "GenerationLogEntry",
    "build_summary",
    "fixture_from_dict",
    "fixture_set_hash",
    "fixture_to_dict",
    "generation_entry_from_dict",
    "generation_entry_to_dict",
    "read_fixtures_jsonl",
    "read_generation_log",
    "run_detection_benchmark",
    "sanitize_for_prompt",
    "write_fixtures_jsonl",
    "write_generation_log",
]
