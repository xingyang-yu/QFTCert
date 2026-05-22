"""Phase 2c-a runner + metrics tests.

Drive the committed smoke set through MockLLMClient with two response
strategies, and pin the output artefact shape (fixtures.jsonl,
results.jsonl, summary.json, metadata.json) under runs/detection/<id>/.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dualitycert.agent import MockLLMClient
from dualitycert.benchmark import (
    Fixture,
    build_summary,
    fixture_set_hash,
    read_fixtures_jsonl,
    run_detection_benchmark,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
SMOKE_FIXTURES_PATH = REPO_ROOT / "fixtures" / "detection_smoke.jsonl"


# ----------------------------------------------------------------------
# Helpers.
# ----------------------------------------------------------------------


def _oracle_responses(fixtures: list[Fixture]) -> list[dict]:
    """Return canned responses that always agree with the ground truth."""

    return [
        {
            "verdict": f.ground_truth_label,
            "confidence": "high",
            "reasoning": "oracle reply",
        }
        for f in fixtures
    ]


def _adversary_responses(fixtures: list[Fixture]) -> list[dict]:
    """Return canned responses that always disagree with the ground truth."""

    flip = {"dual": "not_dual", "not_dual": "dual"}
    return [
        {
            "verdict": flip[f.ground_truth_label],
            "confidence": "low",
            "reasoning": "adversary reply",
        }
        for f in fixtures
    ]


# ----------------------------------------------------------------------
# Runner end-to-end on the committed smoke set.
# ----------------------------------------------------------------------


def test_runner_oracle_writes_full_artefacts(tmp_path: Path):
    fixtures = read_fixtures_jsonl(SMOKE_FIXTURES_PATH)
    mock = MockLLMClient(structured_responses=_oracle_responses(fixtures))

    result = run_detection_benchmark(
        fixtures,
        client=mock,
        model="mock-sonnet",
        max_tokens=1024,
        output_dir=tmp_path,
        run_id="smoke_oracle",
        run_config={"client": "MockLLMClient", "purpose": "harness_pin"},
        timestamp_override="2026-05-20T00:00:00+00:00",
    )

    # All four artefacts exist.
    run_dir = result.run_dir
    assert (run_dir / "fixtures.jsonl").exists()
    assert (run_dir / "results.jsonl").exists()
    assert (run_dir / "summary.json").exists()
    assert (run_dir / "metadata.json").exists()

    # Per-sample lines in results.jsonl == fixture count.
    results_lines = (run_dir / "results.jsonl").read_text().splitlines()
    assert len(results_lines) == len(fixtures)
    for line in results_lines:
        record = json.loads(line)
        assert {
            "fixture_id",
            "ground_truth",
            "llm_decision",
            "llm_confidence",
            "llm_reasoning",
            "correct",
        } <= record.keys()
        assert record["correct"] is True

    # Summary: 100% accuracy (oracle).
    summary = json.loads((run_dir / "summary.json").read_text())
    assert summary["n_total"] == len(fixtures)
    assert summary["n_correct"] == len(fixtures)
    assert summary["accuracy"] == 1.0
    for label in ("dual", "not_dual"):
        if label in summary["accuracy_by_class"]:
            assert summary["accuracy_by_class"][label] == 1.0
    # Confusion matrix: all weight on the diagonal.
    cm = summary["confusion_matrix"]
    assert cm["dual"]["not_dual"] == 0
    assert cm["not_dual"]["dual"] == 0

    # Metadata: fixture set hash matches the snapshot.
    metadata = json.loads((run_dir / "metadata.json").read_text())
    assert metadata["run_id"] == "smoke_oracle"
    assert metadata["model"] == "mock-sonnet"
    assert metadata["max_tokens"] == 1024
    assert metadata["n_fixtures"] == len(fixtures)
    assert metadata["fixture_set_hash"] == fixture_set_hash(fixtures)
    assert metadata["timestamp"] == "2026-05-20T00:00:00+00:00"
    assert metadata["run_config"]["client"] == "MockLLMClient"


def test_runner_adversary_yields_zero_accuracy(tmp_path: Path):
    """The accuracy = 0 case: flipped responses across the entire smoke set."""

    fixtures = read_fixtures_jsonl(SMOKE_FIXTURES_PATH)
    mock = MockLLMClient(structured_responses=_adversary_responses(fixtures))

    result = run_detection_benchmark(
        fixtures,
        client=mock,
        model="mock-sonnet",
        output_dir=tmp_path,
        run_id="smoke_adv",
        timestamp_override="2026-05-20T00:00:00+00:00",
    )

    summary = result.summary
    assert summary["accuracy"] == 0.0
    cm = summary["confusion_matrix"]
    # All weight off-diagonal.
    assert cm["dual"]["dual"] == 0
    assert cm["not_dual"]["not_dual"] == 0
    # All flipped entries land on the off-diagonal.
    flips = cm["dual"]["not_dual"] + cm["not_dual"]["dual"]
    assert flips == len(fixtures)


def test_runner_snapshot_matches_input_fixture_set(tmp_path: Path):
    """The fixtures.jsonl written under the run dir round-trips back to the input."""

    fixtures = read_fixtures_jsonl(SMOKE_FIXTURES_PATH)
    mock = MockLLMClient(structured_responses=_oracle_responses(fixtures))
    result = run_detection_benchmark(
        fixtures,
        client=mock,
        output_dir=tmp_path,
        run_id="snapshot_test",
        timestamp_override="t",
    )
    snapshot = read_fixtures_jsonl(result.run_dir / "fixtures.jsonl")
    assert snapshot == fixtures


def test_runner_rejects_empty_fixture_set(tmp_path: Path):
    with pytest.raises(ValueError, match="empty fixture set"):
        run_detection_benchmark(
            [],
            client=MockLLMClient(structured_responses=[]),
            output_dir=tmp_path,
        )


# ----------------------------------------------------------------------
# Metrics module: per-bucket breakdowns.
# ----------------------------------------------------------------------


def test_summary_breakdowns_are_per_class_and_per_source(tmp_path: Path):
    """The per-source / per-perturbation accuracy tables are non-trivial
    on the smoke set."""

    fixtures = read_fixtures_jsonl(SMOKE_FIXTURES_PATH)
    mock = MockLLMClient(structured_responses=_oracle_responses(fixtures))
    result = run_detection_benchmark(
        fixtures,
        client=mock,
        output_dir=tmp_path,
        run_id="breakdown",
        timestamp_override="t",
    )
    summary = result.summary

    sources = {f.metadata.source for f in fixtures}
    assert set(summary["accuracy_by_source"]) == sources
    assert set(summary["counts_by_source"]) == sources

    ptypes = {f.metadata.perturbation_type for f in fixtures}
    assert set(summary["accuracy_by_perturbation_type"]) == ptypes
    # Each bucket must sum the per-source / per-ptype counts to the total.
    assert sum(summary["counts_by_source"].values()) == summary["n_total"]
    assert (
        sum(summary["counts_by_perturbation_type"].values()) == summary["n_total"]
    )


def test_summary_rejects_mismatched_results_and_fixtures():
    """A safety check: results and fixtures must align."""

    fixtures = read_fixtures_jsonl(SMOKE_FIXTURES_PATH)
    bogus_results = [
        {
            "fixture_id": "does_not_exist",
            "ground_truth": "dual",
            "llm_decision": "dual",
            "correct": True,
        }
    ]
    with pytest.raises(ValueError, match="length mismatch"):
        build_summary(bogus_results, fixtures)


def test_summary_exposes_balanced_accuracy_and_trivial_baselines():
    """Class-imbalance guards (Phase 2c-a Exp 1 sediment): a degenerate
    'always not_dual' policy must be visible from summary.json alone,
    not inferable only from the confusion matrix."""

    fixtures = read_fixtures_jsonl(SMOKE_FIXTURES_PATH)
    # Oracle responses: balanced_accuracy should be 1.0.
    oracle = MockLLMClient(structured_responses=_oracle_responses(fixtures))
    summary_oracle = build_summary(
        [
            {
                "fixture_id": f.fixture_id,
                "ground_truth": f.ground_truth_label,
                "llm_decision": f.ground_truth_label,
                "correct": True,
            }
            for f in fixtures
        ],
        fixtures,
    )
    assert summary_oracle["balanced_accuracy"] == 1.0

    # Always-not_dual policy: raw accuracy == always_not_dual_baseline,
    # balanced_accuracy == 0.5 (chance) regardless of class skew.
    always_not_dual = [
        {
            "fixture_id": f.fixture_id,
            "ground_truth": f.ground_truth_label,
            "llm_decision": "not_dual",
            "correct": f.ground_truth_label == "not_dual",
        }
        for f in fixtures
    ]
    summary_degen = build_summary(always_not_dual, fixtures)
    assert summary_degen["balanced_accuracy"] == 0.5
    assert summary_degen["accuracy"] == summary_degen["always_not_dual_baseline"]

    # The two trivial baselines sum to 1 (each fixture is in exactly one class).
    assert (
        summary_degen["always_not_dual_baseline"]
        + summary_degen["always_dual_baseline"]
    ) == 1.0


def test_summary_balanced_accuracy_is_none_for_single_class_set():
    """When the input distribution has only one ground-truth class,
    balanced_accuracy is undefined — surface as None, not 0 / 1."""

    fixtures = [
        f for f in read_fixtures_jsonl(SMOKE_FIXTURES_PATH)
        if f.ground_truth_label == "not_dual"
    ]
    assert fixtures, "smoke set should contain at least one not_dual fixture"
    records = [
        {
            "fixture_id": f.fixture_id,
            "ground_truth": "not_dual",
            "llm_decision": "not_dual",
            "correct": True,
        }
        for f in fixtures
    ]
    summary = build_summary(records, fixtures)
    assert summary["balanced_accuracy"] is None
    assert summary["always_dual_baseline"] == 0.0
    assert summary["always_not_dual_baseline"] == 1.0


def test_summary_handles_partial_unknown_token_counts():
    """If the backend reports None for token counts (MockLLMClient case),
    the summary omits the tokens block rather than emitting zeros."""

    fixtures = read_fixtures_jsonl(SMOKE_FIXTURES_PATH)[:1]
    record = {
        "fixture_id": fixtures[0].fixture_id,
        "ground_truth": fixtures[0].ground_truth_label,
        "llm_decision": fixtures[0].ground_truth_label,
        "correct": True,
        "latency_s": None,
        "input_tokens": None,
        "output_tokens": None,
    }
    summary = build_summary([record], fixtures)
    assert "tokens" not in summary
    assert "latency_s" not in summary
