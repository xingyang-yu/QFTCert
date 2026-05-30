"""Deterministic, offline model client for dry runs and tests.

`DryRunModelClient` conforms to the `LLMClient` Protocol but never makes
a network call and requires no API key. Unlike `MockLLMClient` (a finite
FIFO queue), it answers an unbounded number of calls, which is what the
end-to-end dry-run CLI commands need.

By default it returns a schema-valid stub for whichever structured tool
it is handed (detection / diagnosis / repair). For tests that need
specific behavior — an oracle, or a deliberately *invalid* payload to
exercise invalid-output handling — inject a `structured_policy`.
"""

from __future__ import annotations

from typing import Any, Callable

from dualitycert.agent.client import StructuredLLMResponse


__all__ = ["DryRunModelClient"]

# A structured_policy receives (user, tool_name, schema) and returns the
# dict to surface as StructuredLLMResponse.data (may be schema-invalid on
# purpose, to test downstream validation).
StructuredPolicy = Callable[..., dict]


class DryRunModelClient:
    """Offline deterministic LLMClient."""

    def __init__(
        self,
        *,
        detection_verdict: str = "not_dual",
        diagnosis_modes: tuple[str, ...] = ("unknown",),
        structured_policy: StructuredPolicy | None = None,
        text_policy: Callable[[str], str] | None = None,
        fail_structured: bool = False,
    ) -> None:
        self.detection_verdict = detection_verdict
        self.diagnosis_modes = tuple(diagnosis_modes)
        self.structured_policy = structured_policy
        self.text_policy = text_policy
        self.fail_structured = fail_structured
        self.structured_calls: list[dict[str, Any]] = []
        self.text_calls: list[dict[str, Any]] = []

    def complete(
        self,
        *,
        model: str,
        system: str,
        user: str,
        max_tokens: int,
    ) -> str:
        self.text_calls.append(
            {"model": model, "system": system, "user": user, "max_tokens": max_tokens}
        )
        if self.text_policy is not None:
            return self.text_policy(user)
        return "{}"

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
        if self.fail_structured:
            raise RuntimeError(
                "DryRunModelClient: forced structured failure (fail_structured=True)"
            )
        if self.structured_policy is not None:
            data = self.structured_policy(
                user=user, tool_name=tool_name, schema=schema
            )
        else:
            data = self._default_structured(schema)
        return StructuredLLMResponse(
            data=data,
            latency_s=0.0,
            input_tokens=max(1, len(user) // 4),
            output_tokens=8,
        )

    def _default_structured(self, schema: dict) -> dict:
        props = schema.get("properties", {})
        if "verdict" in props:
            return {
                "verdict": self.detection_verdict,
                "confidence": "low",
                "reasoning": "dry-run deterministic stub",
            }
        if "failure_modes" in props:
            return {
                "failure_modes": list(self.diagnosis_modes),
                "confidence": "low",
                "reasoning": "dry-run deterministic stub",
            }
        if "action" in props:
            return {
                "action": "no_change",
                "patches": [],
                "reasoning": "dry-run deterministic stub",
            }
        # Generic fallback: fill required keys with empty values.
        out: dict[str, Any] = {}
        for key in schema.get("required", []):
            out[key] = _empty_for(props.get(key, {}))
        return out


def _empty_for(prop_schema: dict) -> Any:
    t = prop_schema.get("type")
    if t == "array":
        return []
    if t == "object":
        return {}
    if t in {"integer", "number"}:
        return 0
    if t == "boolean":
        return False
    enum = prop_schema.get("enum")
    if enum:
        return enum[0]
    return ""
