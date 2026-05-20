"""Detection benchmark runner — drives a fixture set through an LLMClient.

Per the locked plan (§10 "Runner outputs") each run writes four files
into `runs/detection/<run_id>/`::

    fixtures.jsonl     # snapshot of the input fixture set (sha-pinned)
    results.jsonl      # one line per sample, deterministic schema
    summary.json       # aggregated metrics
    metadata.json      # model, fixture set hash, run config, timestamp

The runner is intentionally thin: it loops over fixtures, sanitizes,
calls `run_detection`, and serializes. Aggregation logic lives in
`dualitycert.benchmark.metrics`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from dualitycert.agent.client import LLMClient
from dualitycert.agent.detection import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DetectionDecision,
    run_detection,
)
from dualitycert.benchmark.fixtures import (
    Fixture,
    fixture_set_hash,
    fixture_to_dict,
    sanitize_for_prompt,
    write_fixtures_jsonl,
)
from dualitycert.benchmark.metrics import build_summary


__all__ = [
    "DetectionRunResult",
    "run_detection_benchmark",
]


@dataclass(frozen=True)
class DetectionRunResult:
    """In-memory record of one benchmark run."""

    run_id: str
    run_dir: Path
    fixtures: tuple[Fixture, ...]
    results: tuple[dict[str, Any], ...]
    summary: dict[str, Any]
    metadata: dict[str, Any]


def run_detection_benchmark(
    fixtures: Iterable[Fixture],
    *,
    client: LLMClient,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    output_dir: Path | str,
    run_id: str | None = None,
    run_config: Mapping[str, Any] | None = None,
    timestamp_override: str | None = None,
) -> DetectionRunResult:
    """Run the benchmark and write artefacts to `output_dir/<run_id>/`.

    `run_id` defaults to an ISO-8601 UTC timestamp (precise to seconds)
    so multiple runs do not collide. Tests pass `run_id` explicitly to
    keep paths deterministic.

    `timestamp_override` lets tests pin the metadata.json timestamp.
    """

    fixtures_tuple: tuple[Fixture, ...] = tuple(fixtures)
    if not fixtures_tuple:
        raise ValueError("run_detection_benchmark: empty fixture set")

    if run_id is None:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    run_dir = Path(output_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # 1. Snapshot the fixture set under the run directory. This is the
    #    sha-pinned reference the analysis layer reads back later.
    fixtures_snapshot_path = run_dir / "fixtures.jsonl"
    write_fixtures_jsonl(fixtures_snapshot_path, fixtures_tuple)

    # 2. Per-fixture detection calls.
    results: list[dict[str, Any]] = []
    for fixture in fixtures_tuple:
        sanitized_e = sanitize_for_prompt(fixture.electric, theory_label="Theory A")
        sanitized_c = sanitize_for_prompt(fixture.candidate, theory_label="Theory B")
        decision: DetectionDecision = run_detection(
            sanitized_electric=sanitized_e,
            sanitized_candidate=sanitized_c,
            client=client,
            model=model,
            max_tokens=max_tokens,
        )
        record: dict[str, Any] = {
            "fixture_id": fixture.fixture_id,
            "ground_truth": fixture.ground_truth_label,
            "llm_decision": decision.verdict,
            "llm_confidence": decision.confidence,
            "llm_reasoning": decision.reasoning,
            "correct": decision.verdict == fixture.ground_truth_label,
            "latency_s": decision.latency_s,
            "input_tokens": decision.input_tokens,
            "output_tokens": decision.output_tokens,
        }
        results.append(record)

    # 3. results.jsonl (strict JSONL, sort_keys for byte-stability).
    results_path = run_dir / "results.jsonl"
    with results_path.open("w", encoding="utf-8") as fh:
        for record in results:
            fh.write(json.dumps(record, sort_keys=True, ensure_ascii=False))
            fh.write("\n")

    # 4. summary.json.
    summary = build_summary(results, fixtures_tuple)
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # 5. metadata.json. The timestamp is the one identifying field; the
    #    fixture_set_hash pins reproducibility.
    timestamp = timestamp_override or datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )
    metadata = {
        "run_id": run_id,
        "model": model,
        "max_tokens": int(max_tokens),
        "fixture_set_hash": fixture_set_hash(fixtures_tuple),
        "n_fixtures": len(fixtures_tuple),
        "timestamp": timestamp,
        "run_config": dict(run_config or {}),
    }
    (run_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return DetectionRunResult(
        run_id=run_id,
        run_dir=run_dir,
        fixtures=fixtures_tuple,
        results=tuple(results),
        summary=summary,
        metadata=metadata,
    )
