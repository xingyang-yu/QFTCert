"""Tests for the repair loop using MockLLMClient (no API calls).

These tests verify that the LLMClient Protocol is real: any object satisfying
the interface can drive the repair loop to convergence.  They also document
the expected iteration behavior for each failure type.
"""

from __future__ import annotations

import copy
import json

import pytest

from dualitycert.agent import MockLLMClient, run_llm_repair_loop
from dualitycert.core.certificates import OUTWARD_PARTIAL, OUTWARD_PASSED


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_fixture(name: str) -> dict:
    from pathlib import Path
    return json.loads(
        (Path(__file__).parent.parent / "claims" / f"{name}.json").read_text()
    )


def _with(data: dict, **overrides) -> dict:
    """Return a shallow-merged copy of data with nested key overrides.

    Supports one level of nesting via dotted keys, e.g. 'magnetic.rank'.
    """
    result = copy.deepcopy(data)
    for key, value in overrides.items():
        parts = key.split(".", 1)
        if len(parts) == 2:
            result.setdefault(parts[0], {})[parts[1]] = value
        else:
            result[key] = value
    return result


PASSING_STATUSES = {OUTWARD_PASSED, OUTWARD_PARTIAL}


# ---------------------------------------------------------------------------
# wrong_magnetic_rank: mock returns correct rank on first repair attempt
# ---------------------------------------------------------------------------

def test_mock_convergence_wrong_rank():
    broken = _load_fixture("wrong_magnetic_rank")  # rank=3, should be 2
    repaired = _with(broken, **{"magnetic.rank": 2})

    mock = MockLLMClient([json.dumps(repaired)])
    result = run_llm_repair_loop(broken, client=mock, model="mock")

    assert result.converged
    assert result.final_outward_status in PASSING_STATUSES
    assert result.iteration_count == 2  # iter 0 fails, iter 1 passes
    assert len(mock.calls) == 1


def test_mock_no_llm_call_when_already_passing():
    passing = _load_fixture("sqcd_Nc3_Nf5")

    mock = MockLLMClient([])  # queue empty; any call would raise
    result = run_llm_repair_loop(passing, client=mock, model="mock")

    assert result.converged
    assert result.iteration_count == 1
    assert len(mock.calls) == 0


def test_mock_parse_error_stops_loop():
    broken = _load_fixture("wrong_magnetic_rank")

    mock = MockLLMClient(["this is not json at all"])
    result = run_llm_repair_loop(broken, client=mock, model="mock", max_iterations=4)

    assert not result.converged
    assert result.iterations[-1].parse_error is not None
    assert len(mock.calls) == 1  # stopped after first parse failure


def test_mock_max_iterations_cutoff():
    broken = _load_fixture("wrong_magnetic_rank")
    # Return a still-broken claim each time
    still_broken = _with(broken, **{"magnetic.rank": 99})

    mock = MockLLMClient([json.dumps(still_broken)] * 3)
    result = run_llm_repair_loop(broken, client=mock, model="mock", max_iterations=3)

    assert not result.converged
    assert result.iteration_count == 4  # iter 0..3; 3 LLM calls
    assert len(mock.calls) == 3


# ---------------------------------------------------------------------------
# Protocol structural check
# ---------------------------------------------------------------------------

def test_mock_satisfies_llm_client_protocol():
    from dualitycert.agent import LLMClient
    assert isinstance(MockLLMClient([]), LLMClient)
