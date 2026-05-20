"""Tests for the structured-tool-use extension of `LLMClient`.

These tests pin the Phase 2c-a Step 1 contract: any backend satisfying
the protocol must accept a `(model, system, user, schema, tool_name,
max_tokens)` call and return a `StructuredLLMResponse` whose `data`
field is the validated tool-input dict. The Anthropic adapter is
exercised via a fake SDK stub (so the test suite stays offline). The
MockLLMClient is exercised directly.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from dualitycert.agent import (
    AnthropicAdapter,
    LLMClient,
    MockLLMClient,
    StructuredLLMResponse,
)


_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["dual", "not_dual"]},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "reasoning": {"type": "string"},
    },
    "required": ["verdict", "confidence", "reasoning"],
}


# ----------------------------------------------------------------------
# Protocol surface.
# ----------------------------------------------------------------------


def test_mock_satisfies_llm_client_protocol():
    """MockLLMClient must satisfy the extended Protocol (both methods)."""

    assert isinstance(MockLLMClient(), LLMClient)


def test_mock_text_queue_back_compat():
    """The original positional-text-queue API still works for repair-loop tests."""

    mock = MockLLMClient(["hello"])
    out = mock.complete(model="m", system="sys", user="u", max_tokens=8)
    assert out == "hello"
    assert mock.calls == [
        {"model": "m", "system": "sys", "user": "u", "max_tokens": 8}
    ]


# ----------------------------------------------------------------------
# MockLLMClient.complete_structured behaviour.
# ----------------------------------------------------------------------


def test_mock_structured_returns_wrapped_response():
    """A queued dict comes back as `StructuredLLMResponse.data`; metadata is None."""

    payload = {
        "verdict": "dual",
        "confidence": "high",
        "reasoning": "anomalies match, R(W)=2 holds.",
    }
    mock = MockLLMClient(structured_responses=[payload])

    response = mock.complete_structured(
        model="mock",
        system="sys",
        user="usr",
        schema=_SCHEMA,
        tool_name="duality_decision",
        max_tokens=128,
    )

    assert isinstance(response, StructuredLLMResponse)
    assert response.data == payload
    assert response.latency_s is None
    assert response.input_tokens is None
    assert response.output_tokens is None
    assert response.raw_response is None
    assert mock.structured_calls == [
        {
            "model": "mock",
            "system": "sys",
            "user": "usr",
            "schema": _SCHEMA,
            "tool_name": "duality_decision",
            "max_tokens": 128,
        }
    ]


def test_mock_structured_queue_is_fifo():
    """Subsequent calls pop in queue order, independent from the text queue."""

    first = {"verdict": "dual", "confidence": "high", "reasoning": "a"}
    second = {"verdict": "not_dual", "confidence": "low", "reasoning": "b"}
    mock = MockLLMClient(structured_responses=[first, second])

    r1 = mock.complete_structured(
        model="m", system="s", user="u", schema=_SCHEMA, tool_name="t", max_tokens=8
    )
    r2 = mock.complete_structured(
        model="m", system="s", user="u", schema=_SCHEMA, tool_name="t", max_tokens=8
    )

    assert r1.data == first
    assert r2.data == second


def test_mock_structured_exhausted_raises():
    """Empty structured queue raises with a clear message (no silent default)."""

    mock = MockLLMClient(structured_responses=[])

    with pytest.raises(RuntimeError, match="structured response queue exhausted"):
        mock.complete_structured(
            model="m",
            system="s",
            user="u",
            schema=_SCHEMA,
            tool_name="t",
            max_tokens=8,
        )


def test_mock_text_and_structured_queues_are_independent():
    """Popping one queue must not affect the other; tests can mix repair + detection."""

    mock = MockLLMClient(
        responses=["txt"],
        structured_responses=[{"verdict": "dual", "confidence": "low", "reasoning": "x"}],
    )

    structured = mock.complete_structured(
        model="m",
        system="s",
        user="u",
        schema=_SCHEMA,
        tool_name="t",
        max_tokens=8,
    )
    text = mock.complete(model="m", system="s", user="u", max_tokens=8)

    assert structured.data["verdict"] == "dual"
    assert text == "txt"


# ----------------------------------------------------------------------
# AnthropicAdapter.complete_structured behaviour (offline fake SDK).
# ----------------------------------------------------------------------


class _FakeMessagesAPI:
    """Records the `create()` kwargs and returns a stubbed response."""

    def __init__(self, response: Any) -> None:
        self._response = response
        self.last_kwargs: dict | None = None

    def create(self, **kwargs):  # noqa: ANN003 (mirror Anthropic surface)
        self.last_kwargs = kwargs
        return self._response


class _FakeAnthropicClient:
    def __init__(self, response: Any) -> None:
        self.messages = _FakeMessagesAPI(response)


def _tool_use_response(name: str, args: dict, *, input_tokens: int = 100, output_tokens: int = 50):
    block = SimpleNamespace(type="tool_use", name=name, input=args)
    usage = SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens)
    return SimpleNamespace(content=[block], usage=usage)


def test_anthropic_adapter_structured_extracts_tool_input():
    """Adapter must read the tool_use block's `input` and surface usage tokens."""

    payload = {
        "verdict": "not_dual",
        "confidence": "medium",
        "reasoning": "rank mismatch.",
    }
    fake_client = _FakeAnthropicClient(
        _tool_use_response("duality_decision", payload, input_tokens=233, output_tokens=47)
    )
    adapter = AnthropicAdapter(client=fake_client)

    response = adapter.complete_structured(
        model="claude-sonnet-4-6",
        system="sys",
        user="usr",
        schema=_SCHEMA,
        tool_name="duality_decision",
        max_tokens=2048,
    )

    assert response.data == payload
    assert response.input_tokens == 233
    assert response.output_tokens == 47
    assert response.latency_s is not None and response.latency_s >= 0.0
    # Ensure we forced the tool call.
    kwargs = fake_client.messages.last_kwargs
    assert kwargs["model"] == "claude-sonnet-4-6"
    assert kwargs["system"] == "sys"
    assert kwargs["max_tokens"] == 2048
    assert kwargs["messages"] == [{"role": "user", "content": "usr"}]
    assert kwargs["tool_choice"] == {"type": "tool", "name": "duality_decision"}
    assert len(kwargs["tools"]) == 1
    assert kwargs["tools"][0]["name"] == "duality_decision"
    assert kwargs["tools"][0]["input_schema"] == _SCHEMA


def test_anthropic_adapter_structured_raises_when_no_tool_use_block():
    """Refusal / text-only reply must raise — there is no fallback path."""

    text_only = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="sorry, I cannot answer")],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )
    fake_client = _FakeAnthropicClient(text_only)
    adapter = AnthropicAdapter(client=fake_client)

    with pytest.raises(RuntimeError, match="did not contain a tool_use block"):
        adapter.complete_structured(
            model="m",
            system="s",
            user="u",
            schema=_SCHEMA,
            tool_name="duality_decision",
            max_tokens=128,
        )


def test_anthropic_adapter_structured_ignores_wrong_tool_name():
    """A tool_use block for a different tool must NOT be silently accepted."""

    wrong_tool = SimpleNamespace(
        content=[
            SimpleNamespace(type="tool_use", name="some_other_tool", input={"v": 1}),
        ],
        usage=SimpleNamespace(input_tokens=1, output_tokens=1),
    )
    fake_client = _FakeAnthropicClient(wrong_tool)
    adapter = AnthropicAdapter(client=fake_client)

    with pytest.raises(RuntimeError, match="did not contain a tool_use block"):
        adapter.complete_structured(
            model="m",
            system="s",
            user="u",
            schema=_SCHEMA,
            tool_name="duality_decision",
            max_tokens=128,
        )


def test_anthropic_adapter_complete_still_works_after_extension():
    """Regression: the existing text `complete` path still works on the same adapter."""

    response = SimpleNamespace(
        content=[SimpleNamespace(text="ok")],
        usage=SimpleNamespace(input_tokens=1, output_tokens=1),
    )
    fake_client = _FakeAnthropicClient(response)
    adapter = AnthropicAdapter(client=fake_client)

    out = adapter.complete(model="m", system="s", user="u", max_tokens=8)
    assert out == "ok"


# ----------------------------------------------------------------------
# Cross-method sanity: the schema dict is passed through verbatim.
# ----------------------------------------------------------------------


def test_schema_is_passed_through_verbatim_to_mock_and_adapter():
    """The runner relies on the schema reaching the backend untouched."""

    deep_schema = json.loads(json.dumps(_SCHEMA))

    mock = MockLLMClient(structured_responses=[{"verdict": "dual", "confidence": "low", "reasoning": "y"}])
    mock.complete_structured(
        model="m", system="s", user="u", schema=deep_schema, tool_name="t", max_tokens=8
    )
    assert mock.structured_calls[0]["schema"] is deep_schema

    fake_client = _FakeAnthropicClient(
        _tool_use_response("t", {"verdict": "dual", "confidence": "low", "reasoning": "y"})
    )
    adapter = AnthropicAdapter(client=fake_client)
    adapter.complete_structured(
        model="m", system="s", user="u", schema=deep_schema, tool_name="t", max_tokens=8
    )
    assert fake_client.messages.last_kwargs["tools"][0]["input_schema"] is deep_schema
