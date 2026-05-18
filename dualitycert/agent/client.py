"""LLM client abstraction for the repair loop.

The repair loop depends only on LLMClient; any backend that satisfies the
Protocol can be dropped in.  Two implementations ship here:
  - AnthropicAdapter  wraps the anthropic SDK (requires pip install anthropic)
  - MockLLMClient     returns canned responses deterministically; used in tests
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    """Minimal interface the repair loop requires from a language model backend."""

    def complete(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int,
    ) -> str:
        """Return the assistant's text reply (stripped).

        Implementations must raise on hard errors (auth failure, rate-limit
        exhaustion after retries, etc.) and return an empty string only when
        the model genuinely produced no text content.
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


class MockLLMClient:
    """Deterministic LLMClient for tests; returns canned JSON responses.

    Pass a list of response strings; each call pops the next one.  If the
    list is exhausted the client raises RuntimeError so tests fail loudly
    instead of silently returning empty text.

    Usage::

        mock = MockLLMClient([json.dumps(repaired_claim)])
        result = run_llm_repair_loop(broken_data, client=mock, model="mock")
    """

    def __init__(self, responses: list[str]) -> None:
        self._queue = list(responses)
        self.calls: list[dict[str, Any]] = []

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
        if not self._queue:
            raise RuntimeError("MockLLMClient: response queue exhausted")
        return self._queue.pop(0)
