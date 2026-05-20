"""Phase 2c-a detection smoke tests.

Pins:
  - `run_detection` issues exactly one `complete_structured` call with
    the locked schema, locked tool_name, and locked system prompt.
  - The user message contains both sanitized JSONs (no Seiberg-mutated /
    R-repaired provenance leakage).
  - The `MockLLMClient.structured_responses` queue drives a deterministic
    smoke run across the committed `fixtures/detection_smoke.jsonl`.
  - `DetectionDecision` rejects out-of-schema values at the dataclass
    boundary so the runner never has to revalidate.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dualitycert.agent import (
    DETECTION_DECISION_SCHEMA,
    DETECTION_SYSTEM_PROMPT,
    DETECTION_TOOL_NAME,
    DetectionDecision,
    MockLLMClient,
    run_detection,
)
from dualitycert.agent.detection import build_detection_user_message
from dualitycert.benchmark import (
    read_fixtures_jsonl,
    sanitize_for_prompt,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
SMOKE_FIXTURES_PATH = REPO_ROOT / "fixtures" / "detection_smoke.jsonl"


# ----------------------------------------------------------------------
# Schema / prompt invariants.
# ----------------------------------------------------------------------


def test_decision_schema_locks_three_required_fields():
    """Rule 4: verdict, confidence, reasoning. All required, enums fixed."""

    assert DETECTION_DECISION_SCHEMA["required"] == [
        "verdict",
        "confidence",
        "reasoning",
    ]
    props = DETECTION_DECISION_SCHEMA["properties"]
    assert props["verdict"]["enum"] == ["dual", "not_dual"]
    assert props["confidence"]["enum"] == ["low", "medium", "high"]


def test_detection_decision_rejects_out_of_schema_values():
    """The dataclass __post_init__ is the runner's safety net."""

    with pytest.raises(ValueError, match="verdict"):
        DetectionDecision(verdict="maybe", confidence="low", reasoning="x")
    with pytest.raises(ValueError, match="confidence"):
        DetectionDecision(verdict="dual", confidence="extremely_high", reasoning="x")


# ----------------------------------------------------------------------
# Single-call behaviour.
# ----------------------------------------------------------------------


def test_run_detection_issues_one_structured_call():
    """One LLM call, no follow-ups; the schema and tool_name reach the backend."""

    payload = {
        "verdict": "dual",
        "confidence": "medium",
        "reasoning": "anomaly tables match and R(W)=2 on both sides.",
    }
    mock = MockLLMClient(structured_responses=[payload])

    decision = run_detection(
        sanitized_electric={"name": "Theory A", "node_labels": ["G0"], "ranks": [3],
                            "u1_globals": ["U(1)_R"], "arrows": [], "superpotential": []},
        sanitized_candidate={"name": "Theory B", "node_labels": ["G0"], "ranks": [3],
                             "u1_globals": ["U(1)_R"], "arrows": [], "superpotential": []},
        client=mock,
        model="mock",
        max_tokens=128,
    )

    assert decision.verdict == "dual"
    assert decision.confidence == "medium"
    assert decision.reasoning.startswith("anomaly")
    assert decision.latency_s is None  # MockLLMClient does not report timing

    # Exactly one structured call, with the locked tool / schema / system prompt.
    assert len(mock.structured_calls) == 1
    call = mock.structured_calls[0]
    assert call["model"] == "mock"
    assert call["max_tokens"] == 128
    assert call["tool_name"] == DETECTION_TOOL_NAME
    assert call["schema"] is DETECTION_DECISION_SCHEMA
    assert call["system"] == DETECTION_SYSTEM_PROMPT
    # No text-completion path used.
    assert mock.calls == []


def test_user_message_carries_both_sanitized_jsons():
    """The user prompt must include both theories under the A/B labels."""

    a = {"name": "Theory A", "ranks": [3], "node_labels": ["G0"],
         "u1_globals": ["U(1)_R"], "arrows": [], "superpotential": []}
    b = {"name": "Theory B", "ranks": [6], "node_labels": ["G0"],
         "u1_globals": ["U(1)_R"], "arrows": [], "superpotential": []}
    message = build_detection_user_message(a, b)
    assert "Theory A (electric):" in message
    assert "Theory B (candidate dual):" in message
    assert '"ranks": [\n    3\n  ]' in message or '"ranks": [3]' in message
    assert '"ranks": [\n    6\n  ]' in message or '"ranks": [6]' in message
    assert "Seiberg-dual / IR-equivalent" in message


def test_run_detection_passes_sanitized_payloads_not_raw_provenance():
    """Smoke-set fixture goes through sanitize_for_prompt before reaching the LLM."""

    fixtures = read_fixtures_jsonl(SMOKE_FIXTURES_PATH)
    assert fixtures, "smoke fixtures must exist (run scripts/generate_detection_fixtures.py)"
    f = fixtures[0]
    san_e = sanitize_for_prompt(f.electric, theory_label="Theory A")
    san_c = sanitize_for_prompt(f.candidate, theory_label="Theory B")
    payload = {"verdict": "dual", "confidence": "high", "reasoning": "smoke"}
    mock = MockLLMClient(structured_responses=[payload])

    run_detection(
        sanitized_electric=san_e,
        sanitized_candidate=san_c,
        client=mock,
        model="mock",
        max_tokens=2048,
    )

    user_msg = mock.structured_calls[0]["user"]
    # Provenance markers must NOT appear.
    for needle in (
        "Seiberg-mutated",
        "R-repaired",
        "(integrated)",
        "SU(2N)",
    ):
        assert needle not in user_msg, f"sanitization leaked: {needle!r} in prompt"
    # Theory labels DO appear.
    assert "Theory A (electric)" in user_msg
    assert "Theory B (candidate dual)" in user_msg


# ----------------------------------------------------------------------
# Smoke-set MockLLMClient walk-through.
# ----------------------------------------------------------------------


def test_smoke_fixture_set_drives_through_mock_with_label_oracle():
    """The runner abstraction in Step 6 will do this for real; here we
    pin that a per-fixture loop with sanitization + MockLLMClient works
    end-to-end on the committed smoke set.

    The mock "oracle" responds with the verifier's ground-truth label —
    so on the smoke set, accuracy must be 100% by construction. That
    pins the harness, not the LLM."""

    fixtures = read_fixtures_jsonl(SMOKE_FIXTURES_PATH)
    canned_responses = [
        {
            "verdict": f.ground_truth_label,
            "confidence": "high",
            "reasoning": "oracle reply",
        }
        for f in fixtures
    ]
    mock = MockLLMClient(structured_responses=canned_responses)

    correct = 0
    for fixture in fixtures:
        san_e = sanitize_for_prompt(fixture.electric, theory_label="Theory A")
        san_c = sanitize_for_prompt(fixture.candidate, theory_label="Theory B")
        decision = run_detection(
            sanitized_electric=san_e,
            sanitized_candidate=san_c,
            client=mock,
            model="mock",
            max_tokens=2048,
        )
        if decision.verdict == fixture.ground_truth_label:
            correct += 1

    assert correct == len(fixtures) == len(mock.structured_calls)
