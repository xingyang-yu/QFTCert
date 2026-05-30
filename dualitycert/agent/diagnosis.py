"""Single-call blind failure-mode diagnosis (Layer B, Phase 2c-b).

Parallel to `dualitycert.agent.detection`: one structured LLM call per
fixture, but the model predicts *which failure-mode categories* the pair
violates rather than a binary dual / not_dual verdict. The prediction is
scored against the verifier's `failed_obligations` (mapped to categories
by `dualitycert.experiments.verifier.categorize_obligation`).

The schema/tool/prompt are versioned and intended to be frozen once the
diagnosis benchmark runs, mirroring the detection MVP discipline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from dualitycert.agent.client import AnthropicAdapter, LLMClient


__all__ = [
    "DIAGNOSIS_DECISION_SCHEMA",
    "DIAGNOSIS_SYSTEM_PROMPT",
    "DIAGNOSIS_TOOL_NAME",
    "DIAGNOSIS_FAILURE_MODES",
    "DEFAULT_MODEL",
    "DEFAULT_MAX_TOKENS",
    "DiagnosisDecision",
    "build_diagnosis_user_message",
    "run_diagnosis",
]


DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 2048

DIAGNOSIS_TOOL_NAME = "duality_diagnosis"

# Mirrors `dualitycert.experiments.verifier.FAILURE_MODE_CATEGORIES`
# minus "unknown" handling: "unknown" is offered to the model as a
# catch-all, but a consistent pair is signaled by an empty list.
DIAGNOSIS_FAILURE_MODES: tuple[str, ...] = (
    "anomaly",
    "superpotential",
    "r_charge",
    "chiral_ring",
    "rank",
    "unknown",
)


DIAGNOSIS_DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "failure_modes": {
            "type": "array",
            "items": {"type": "string", "enum": list(DIAGNOSIS_FAILURE_MODES)},
            "description": (
                "The consistency obligation categories Theory B violates "
                "relative to Theory A. Return an EMPTY list if the pair is a "
                "valid dual (no obligation fails). Categories: anomaly "
                "(gauge / mixed 't Hooft anomalies), superpotential (W "
                "consistency / R(W)=2), r_charge (R-symmetry / central "
                "charge), chiral_ring (bounded chiral-ring multiplicities), "
                "rank (gauge rank), unknown."
            ),
        },
        "confidence": {
            "type": "string",
            "enum": ["low", "medium", "high"],
            "description": "Coarse confidence band in the diagnosis.",
        },
        "reasoning": {
            "type": "string",
            "description": (
                "Brief physical reasoning citing the specific obligation(s) "
                "the diagnosis turns on."
            ),
        },
    },
    "required": ["failure_modes", "confidence", "reasoning"],
}


DIAGNOSIS_SYSTEM_PROMPT = """You are a theoretical physicist diagnosing why a proposed 4d N=1 \
supersymmetric gauge theory duality fails (or confirming that it holds).

You will see two quiver theory JSONs labeled "Theory A" (electric) and \
"Theory B" (candidate dual): gauge ranks, bifundamental arrows with \
R-charges, and a superpotential.

Your task: identify which consistency obligation categories Theory B \
violates relative to Theory A, choosing from:
  - anomaly        : cubic gauge or SU(N)^2 x U(1)_R mixed 't Hooft anomalies
  - superpotential : superpotential consistency / R(W)=2 balance
  - r_charge       : R-symmetry assignment / central charge matching
  - chiral_ring    : bounded chiral-ring multiplicity mismatch
  - rank           : gauge rank mismatch
  - unknown        : a failure you cannot localize

If Theory A and Theory B ARE a valid dual (no obligation fails), return an \
EMPTY failure_modes list. Use the structured-output tool only; do not write \
anything outside the tool call."""


@dataclass(frozen=True)
class DiagnosisDecision:
    """Parsed result of a single diagnosis call."""

    failure_modes: tuple[str, ...]
    confidence: str
    reasoning: str
    latency_s: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None

    def __post_init__(self) -> None:
        for mode in self.failure_modes:
            if mode not in DIAGNOSIS_FAILURE_MODES:
                raise ValueError(
                    f"DiagnosisDecision.failure_modes contains invalid mode "
                    f"{mode!r}; allowed {DIAGNOSIS_FAILURE_MODES!r}"
                )
        if self.confidence not in {"low", "medium", "high"}:
            raise ValueError(
                f"DiagnosisDecision.confidence must be low/medium/high; "
                f"got {self.confidence!r}"
            )

    @property
    def modes_set(self) -> frozenset[str]:
        return frozenset(self.failure_modes)


def build_diagnosis_user_message(
    sanitized_electric: Mapping[str, Any],
    sanitized_candidate: Mapping[str, Any],
) -> str:
    """Compose the user-turn prompt for one diagnosis call.

    Both arguments MUST be sanitized (see
    `dualitycert.benchmark.sanitize_for_prompt`) so no provenance leaks.
    """

    return (
        "Theory A (electric):\n"
        + json.dumps(dict(sanitized_electric), indent=2, sort_keys=True)
        + "\n\nTheory B (candidate dual):\n"
        + json.dumps(dict(sanitized_candidate), indent=2, sort_keys=True)
        + "\n\nQuestion: Which consistency obligation categories (if any) does "
        "Theory B violate relative to Theory A?"
    )


def run_diagnosis(
    *,
    sanitized_electric: Mapping[str, Any],
    sanitized_candidate: Mapping[str, Any],
    client: LLMClient | None = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> DiagnosisDecision:
    """Single LLM call: prompt -> tool_use -> validated diagnosis."""

    if client is None:
        client = AnthropicAdapter()

    user_message = build_diagnosis_user_message(
        sanitized_electric, sanitized_candidate
    )
    response = client.complete_structured(
        model=model,
        system=DIAGNOSIS_SYSTEM_PROMPT,
        user=user_message,
        schema=DIAGNOSIS_DECISION_SCHEMA,
        tool_name=DIAGNOSIS_TOOL_NAME,
        max_tokens=max_tokens,
    )
    data = response.data
    modes = tuple(str(m) for m in data.get("failure_modes", []))
    return DiagnosisDecision(
        failure_modes=modes,
        confidence=str(data["confidence"]),
        reasoning=str(data["reasoning"]),
        latency_s=response.latency_s,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
    )
