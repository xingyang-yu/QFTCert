"""OpenAICompatAdapter against a fake OpenAI-SDK-shaped client (no network).

The adapter must satisfy the same LLMClient contract as AnthropicAdapter:
text from `complete`, forced-tool-call dict from `complete_structured`,
and a hard raise when the provider returns no usable tool call.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from dualitycert.agent.client import LLMClient, OpenAICompatAdapter


def _response(*, content=None, tool_calls=None, usage=True):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=(
            SimpleNamespace(prompt_tokens=11, completion_tokens=7)
            if usage
            else None
        ),
    )


def _tool_call(name, arguments):
    return SimpleNamespace(
        function=SimpleNamespace(name=name, arguments=arguments)
    )


class _FakeOpenAI:
    """Mimics `openai.OpenAI().chat.completions.create`."""

    def __init__(self, response):
        self._response = response
        self.calls: list[dict] = []
        completions = SimpleNamespace(create=self._create)
        self.chat = SimpleNamespace(completions=completions)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


def test_complete_returns_stripped_text():
    fake = _FakeOpenAI(_response(content="  the answer \n"))
    adapter = OpenAICompatAdapter(fake)
    out = adapter.complete(model="m", system="s", user="u", max_tokens=64)
    assert out == "the answer"
    call = fake.calls[0]
    assert call["model"] == "m"
    assert call["messages"][0] == {"role": "system", "content": "s"}
    assert call["messages"][1] == {"role": "user", "content": "u"}


def test_complete_structured_parses_forced_tool_call():
    payload = {"verdict": "dual", "confidence": "low", "reasoning": "r"}
    fake = _FakeOpenAI(
        _response(tool_calls=[_tool_call("judge", json.dumps(payload))])
    )
    adapter = OpenAICompatAdapter(fake)
    resp = adapter.complete_structured(
        model="m",
        system="s",
        user="u",
        schema={"type": "object"},
        tool_name="judge",
        max_tokens=64,
    )
    assert resp.data == payload
    assert resp.input_tokens == 11
    assert resp.output_tokens == 7
    assert resp.latency_s is not None
    call = fake.calls[0]
    assert call["tool_choice"] == {
        "type": "function",
        "function": {"name": "judge"},
    }
    assert call["tools"][0]["function"]["name"] == "judge"
    assert call["tools"][0]["function"]["parameters"] == {"type": "object"}


def test_complete_structured_skips_other_tools_finds_target():
    payload = {"action": "no_change", "reasoning": "r"}
    fake = _FakeOpenAI(
        _response(
            tool_calls=[
                _tool_call("other_tool", "{}"),
                _tool_call("repair_action", json.dumps(payload)),
            ]
        )
    )
    adapter = OpenAICompatAdapter(fake)
    resp = adapter.complete_structured(
        model="m",
        system="s",
        user="u",
        schema={"type": "object"},
        tool_name="repair_action",
        max_tokens=64,
    )
    assert resp.data == payload


def test_complete_structured_raises_on_missing_tool_call():
    fake = _FakeOpenAI(_response(content="I refuse to call tools"))
    adapter = OpenAICompatAdapter(fake)
    with pytest.raises(RuntimeError, match="did not contain a tool call"):
        adapter.complete_structured(
            model="m",
            system="s",
            user="u",
            schema={"type": "object"},
            tool_name="judge",
            max_tokens=64,
        )


def test_complete_structured_raises_on_unparseable_arguments():
    fake = _FakeOpenAI(
        _response(tool_calls=[_tool_call("judge", "{not json")])
    )
    adapter = OpenAICompatAdapter(fake)
    with pytest.raises(RuntimeError, match="unparseable arguments"):
        adapter.complete_structured(
            model="m",
            system="s",
            user="u",
            schema={"type": "object"},
            tool_name="judge",
            max_tokens=64,
        )


def test_extra_body_passthrough():
    payload = {"action": "no_change", "reasoning": "r"}
    fake = _FakeOpenAI(
        _response(tool_calls=[_tool_call("repair_action", json.dumps(payload))])
    )
    adapter = OpenAICompatAdapter(fake, extra_body={"enable_thinking": False})
    adapter.complete_structured(
        model="m", system="s", user="u", schema={"type": "object"},
        tool_name="repair_action", max_tokens=64,
    )
    assert fake.calls[0]["extra_body"] == {"enable_thinking": False}
    fake2 = _FakeOpenAI(_response(content="x"))
    OpenAICompatAdapter(fake2).complete(
        model="m", system="s", user="u", max_tokens=64
    )
    assert fake2.calls[0]["extra_body"] is None  # default: no extensions


def test_adapter_satisfies_llmclient_protocol():
    fake = _FakeOpenAI(_response(content="x"))
    assert isinstance(OpenAICompatAdapter(fake), LLMClient)


def test_missing_sdk_raises_actionable_error(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def block_openai(name, *args, **kwargs):
        if name == "openai":
            raise ImportError("No module named 'openai'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", block_openai)
    with pytest.raises(RuntimeError, match="llm-openai"):
        OpenAICompatAdapter()
