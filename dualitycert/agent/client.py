"""LLM client abstraction for the verifier-in-the-loop pipelines.

Two concerns share this module:

  - Free-form text completion (`complete`), used by the repair loop in
    `dualitycert.agent.repair_loop`. The repair loop asks the model to
    emit a corrected JSON object and parses it best-effort.

  - Structured tool-use completion (`complete_structured`), used by the
    detection benchmark in `dualitycert.benchmark`. The detection runner
    cannot tolerate unparseable text; it asks the model to call a single
    declared tool whose `input_schema` we pin, and we read the tool
    arguments back as a validated dict.

Both methods sit on the same `LLMClient` Protocol so any backend can
drop in. Three implementations ship here:

  - AnthropicAdapter — wraps the anthropic SDK (requires
    `pip install -e .[llm]`). Uses the Messages API for `complete` and
    the same Messages API with `tools=[...]` + `tool_choice` for
    `complete_structured`.
  - OpenAICompatAdapter — wraps the openai SDK (requires
    `pip install -e .[llm-openai]`) pointed at ANY OpenAI-compatible
    /chat/completions endpoint: OpenAI itself, OpenRouter, Groq,
    Together, Gemini's OpenAI-compat layer, local vLLM/Ollama, ...
    Provider selection is just `base_url` + `api_key` (the SDK also
    reads OPENAI_BASE_URL / OPENAI_API_KEY from the environment).
  - MockLLMClient   — deterministic; returns canned text from a
    `responses` queue (existing repair-loop semantics) and canned
    structured payloads from a separate `structured_responses` queue
    (used by detection smoke tests).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


__all__ = [
    "AnthropicAdapter",
    "LLMClient",
    "MockLLMClient",
    "OpenAICompatAdapter",
    "StructuredLLMResponse",
]


@dataclass(frozen=True)
class StructuredLLMResponse:
    """Wrapper around a single structured (tool-use) LLM reply.

    `data` is the tool-input dict after schema validation by the backend.
    Latency / token counters are populated when the backend exposes them
    (Anthropic does via `response.usage`); the mock leaves them `None`
    so callers can branch on `is None` rather than special-casing zero.
    `raw_response` is for debugging only — runner code should not depend
    on its shape.
    """

    data: dict
    latency_s: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    raw_response: Any | None = None


@runtime_checkable
class LLMClient(Protocol):
    """Minimal interface our LLM pipelines require from a backend."""

    def complete(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int,
    ) -> str:
        """Return the assistant's text reply (stripped).

        Implementations must raise on hard errors (auth failure, rate-
        limit exhaustion after retries, etc.) and return an empty string
        only when the model genuinely produced no text content.
        """
        ...

    def complete_structured(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: dict,
        tool_name: str,
        max_tokens: int,
    ) -> StructuredLLMResponse:
        """Return a structured-tool-use reply validated against `schema`.

        The backend MUST force a single call to the declared tool
        (e.g. Anthropic `tool_choice={"type": "tool", "name": tool_name}`)
        and surface its `input` arguments as `StructuredLLMResponse.data`.

        Implementations must raise on hard errors AND on the model
        refusing to call the tool — there is no "empty structured reply"
        success case. Detection callers cannot recover from missing
        structured output.
        """
        ...


class AnthropicAdapter:
    """LLMClient backed by the Anthropic Messages API."""

    def __init__(self, client: Any | None = None) -> None:
        if client is None:
            try:
                from anthropic import Anthropic
            except ImportError as exc:
                raise RuntimeError(
                    "anthropic SDK is not installed. Install with: pip install -e .[llm]"
                ) from exc
            client = Anthropic()
        self._client = client

    def complete(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int,
    ) -> str:
        response = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        parts: list[str] = []
        for block in getattr(response, "content", []) or []:
            text = getattr(block, "text", None)
            if text is not None:
                parts.append(text)
        return "".join(parts).strip()

    def complete_structured(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: dict,
        tool_name: str,
        max_tokens: int,
    ) -> StructuredLLMResponse:
        start = time.monotonic()
        response = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            tools=[
                {
                    "name": tool_name,
                    "description": (
                        "Return the structured judgment. The arguments object "
                        "must match the declared input_schema exactly. Do not "
                        "produce any output outside this tool call."
                    ),
                    "input_schema": schema,
                }
            ],
            tool_choice={"type": "tool", "name": tool_name},
        )
        latency_s = time.monotonic() - start

        tool_input: dict | None = None
        for block in getattr(response, "content", []) or []:
            if getattr(block, "type", None) == "tool_use" and getattr(
                block, "name", None
            ) == tool_name:
                candidate = getattr(block, "input", None)
                if isinstance(candidate, dict):
                    tool_input = candidate
                    break
        if tool_input is None:
            raise RuntimeError(
                f"Anthropic response did not contain a tool_use block for "
                f"{tool_name!r}; got content blocks "
                f"{[getattr(b, 'type', None) for b in getattr(response, 'content', []) or []]!r}"
            )

        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "input_tokens", None) if usage is not None else None
        output_tokens = (
            getattr(usage, "output_tokens", None) if usage is not None else None
        )

        return StructuredLLMResponse(
            data=tool_input,
            latency_s=latency_s,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            raw_response=response,
        )


class OpenAICompatAdapter:
    """LLMClient backed by any OpenAI-compatible chat-completions endpoint.

    Works against OpenAI, OpenRouter (`https://openrouter.ai/api/v1`),
    Groq (`https://api.groq.com/openai/v1`), Together, Gemini's
    OpenAI-compat layer
    (`https://generativelanguage.googleapis.com/v1beta/openai/`), and
    local vLLM / Ollama servers. Pass `base_url` / `api_key` explicitly,
    or rely on the SDK's OPENAI_BASE_URL / OPENAI_API_KEY environment
    variables. A pre-built client object can be injected for tests.

    `complete_structured` forces a single function call via
    `tool_choice={"type": "function", "function": {"name": tool_name}}`
    and parses the returned JSON arguments. Providers that ignore forced
    tool choice and return no tool call make this raise — the Protocol
    contract (no silent empty structured reply) is preserved.
    """

    def __init__(
        self,
        client: Any | None = None,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        max_retries: int = 5,
    ) -> None:
        if client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError(
                    "openai SDK is not installed. Install with: "
                    "pip install -e .[llm-openai]"
                ) from exc
            kwargs: dict[str, Any] = {}
            if base_url is not None:
                kwargs["base_url"] = base_url
            if api_key is not None:
                kwargs["api_key"] = api_key
            # Free-tier providers throttle by tokens/minute; the SDK's
            # exponential backoff honors Retry-After on 429/5xx, so a
            # higher retry budget turns bursts into waits, not failures
            # (a raised call is recorded as an invalid fixture).
            client = OpenAI(max_retries=max_retries, **kwargs)
        self._client = client

    def complete(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int,
    ) -> str:
        response = self._client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        choices = getattr(response, "choices", None) or []
        if not choices:
            return ""
        content = getattr(choices[0].message, "content", None)
        return (content or "").strip()

    def complete_structured(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: dict,
        tool_name: str,
        max_tokens: int,
    ) -> StructuredLLMResponse:
        start = time.monotonic()
        request = dict(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "description": (
                            "Return the structured judgment. The arguments "
                            "object must match the declared parameters schema "
                            "exactly. Do not produce any output outside this "
                            "tool call."
                        ),
                        "parameters": schema,
                    },
                }
            ],
            tool_choice={"type": "function", "function": {"name": tool_name}},
        )
        # Some providers (e.g. Groq) return HTTP 400 when the MODEL emits a
        # malformed function call (code `tool_use_failed`, message "Failed to
        # call a function" / "tool call validation failed") rather than
        # surfacing the bad call. Decoding is stochastic, so a couple of fresh
        # attempts usually recover; persistent failure still raises (recorded
        # as invalid output — a model that reliably cannot emit a valid call).
        attempts = 3
        for attempt in range(attempts):
            try:
                response = self._client.chat.completions.create(**request)
                break
            except Exception as exc:
                msg = str(exc).lower()
                transient = (
                    "tool_use_failed" in msg
                    or "failed to call a function" in msg
                    or "tool call validation failed" in msg
                )
                if not transient or attempt == attempts - 1:
                    raise
        latency_s = time.monotonic() - start

        choices = getattr(response, "choices", None) or []
        tool_input: dict | None = None
        seen: list[str] = []
        for choice in choices:
            for call in getattr(choice.message, "tool_calls", None) or []:
                fn = getattr(call, "function", None)
                name = getattr(fn, "name", None)
                seen.append(str(name))
                if fn is None or name != tool_name:
                    continue
                try:
                    candidate = json.loads(fn.arguments)
                except (TypeError, json.JSONDecodeError) as exc:
                    raise RuntimeError(
                        f"OpenAI-compat tool call {tool_name!r} returned "
                        f"unparseable arguments: {exc}"
                    ) from exc
                if isinstance(candidate, dict):
                    tool_input = candidate
                    break
            if tool_input is not None:
                break
        if tool_input is None:
            raise RuntimeError(
                f"OpenAI-compat response did not contain a tool call for "
                f"{tool_name!r}; got tool calls {seen!r}"
            )

        usage = getattr(response, "usage", None)
        input_tokens = (
            getattr(usage, "prompt_tokens", None) if usage is not None else None
        )
        output_tokens = (
            getattr(usage, "completion_tokens", None) if usage is not None else None
        )

        return StructuredLLMResponse(
            data=tool_input,
            latency_s=latency_s,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            raw_response=response,
        )


class MockLLMClient:
    """Deterministic LLMClient for tests.

    Two independent FIFO queues:

      - `responses`: list of canned text strings. Each `complete()` call
        pops the next one. Used by the repair-loop tests.
      - `structured_responses`: list of canned dicts (already validated
        by the caller against the schema they will pass). Each
        `complete_structured()` call pops the next one and wraps it in a
        `StructuredLLMResponse` with `latency_s = None` / token counts
        `None`.

    Exhausting either queue raises RuntimeError so tests fail loudly
    instead of silently returning empty data.

    Usage::

        mock = MockLLMClient(
            responses=[json.dumps(repaired_claim)],
            structured_responses=[{"verdict": "dual", "confidence": "high", "reasoning": "..."}],
        )

    For backward compatibility the positional first argument is the text
    `responses` queue, matching the original repair-loop API.
    """

    def __init__(
        self,
        responses: list[str] | None = None,
        *,
        structured_responses: list[dict] | None = None,
    ) -> None:
        self._text_queue: list[str] = list(responses or [])
        self._structured_queue: list[dict] = list(structured_responses or [])
        self.calls: list[dict[str, Any]] = []
        self.structured_calls: list[dict[str, Any]] = []

    def complete(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int,
    ) -> str:
        self.calls.append(
            {"model": model, "system": system, "user": user, "max_tokens": max_tokens}
        )
        if not self._text_queue:
            raise RuntimeError("MockLLMClient: response queue exhausted")
        return self._text_queue.pop(0)

    def complete_structured(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: dict,
        tool_name: str,
        max_tokens: int,
    ) -> StructuredLLMResponse:
        self.structured_calls.append(
            {
                "model": model,
                "system": system,
                "user": user,
                "schema": schema,
                "tool_name": tool_name,
                "max_tokens": max_tokens,
            }
        )
        if not self._structured_queue:
            raise RuntimeError(
                "MockLLMClient: structured response queue exhausted"
            )
        return StructuredLLMResponse(
            data=self._structured_queue.pop(0),
            latency_s=None,
            input_tokens=None,
            output_tokens=None,
            raw_response=None,
        )
