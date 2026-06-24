"""Single-call blind paired duality detection (Phase 2c-a).

`run_detection` is the per-fixture LLM call. The runner in
`dualitycert.benchmark.runner` loops over fixtures and writes the
per-sample / per-run artefacts; this module is just the prompt + tool
schema + result wrapping for one pair.

Locked design (see `docs/phase2c_a_detection_plan.md` Rules 1, 4, 5):

  - Detection is INDEPENDENT of the repair loop. No shared driver, no
    "max_iterations=0" pretense. Single LLM call per fixture.
  - Output is structured tool use, not free-form text. The model
    forced-calls a tool with the schema below; if it cannot, the call
    raises (no fenced-JSON fallback in the MVP backend set).
  - The decision schema has three fields and is locked. Adding/removing
    fields requires re-running the entire MVP benchmark, so it is
    intentionally frozen here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from dualitycert.agent.client import AnthropicAdapter, LLMClient


__all__ = [
    "DETECTION_DECISION_SCHEMA",
    "DETECTION_SYSTEM_PROMPT",
    "DETECTION_SYSTEM_PROMPT_COMPUTED_R",
    "DETECTION_TOOL_NAME",
    "DEFAULT_MODEL",
    "DEFAULT_MAX_TOKENS",
    "DetectionDecision",
    "build_detection_user_message",
    "run_detection",
]


DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 2048

DETECTION_TOOL_NAME = "duality_decision"


# Locked JSON Schema for the LLM's structured output (Rule 4).
# `verdict` and `confidence` are enums on purpose — coarser self-
# assessment scales than free-form numeric confidences are easier to
# calibrate from a 3×2 contingency table than from a binned floating-
# point range. Do not loosen these without re-running the benchmark.
DETECTION_DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {
            "type": "string",
            "enum": ["dual", "not_dual"],
            "description": (
                "Whether Theory A and Theory B are Seiberg-dual / IR-equivalent "
                "under the verifier scope described in the system prompt."
            ),
        },
        "confidence": {
            "type": "string",
            "enum": ["low", "medium", "high"],
            "description": (
                "Coarse confidence band. low = at-best a guess; medium = the "
                "obvious checks support the verdict; high = the verdict is "
                "forced by anomaly / R-charge / chiral-ring algebra."
            ),
        },
        "reasoning": {
            "type": "string",
            "description": (
                "Brief (a few sentences) physical reasoning supporting the "
                "verdict. Cite the specific obligation(s) the verdict turns on."
            ),
        },
    },
    "required": ["verdict", "confidence", "reasoning"],
}


DETECTION_SYSTEM_PROMPT = """You are a theoretical physicist evaluating proposed 4d N=1 supersymmetric \
gauge theory dualities.

You will see two theory JSONs labeled "Theory A" and "Theory B", each \
encoding a quiver gauge theory: gauge group ranks, bifundamental matter \
arrows with R-charges, and a superpotential of cubic+ monomials.

Your task: judge whether Theory A and Theory B are Seiberg-dual / IR-\
equivalent under the standard scope (cubic gauge anomaly cancellation, \
SU(N)^2 x U(1)_R mixed anomaly cancellation, R(W)=2 R-charge balance, \
F-term ideal consistency, bounded chiral-ring multiplicity matching).

Use the provided structured-output tool to return your verdict with a \
confidence level and a brief reasoning. Do not write any output outside \
the tool call."""


# Judge ②b ("computed" R-charge policy) variant: the theories shown to the
# model carry NO R-charges (the verifier recomputes the superconformal R by
# a-maximization), so the model commits only to quiver + matter + W. Used
# verbatim instead of DETECTION_SYSTEM_PROMPT when run_detection(computed_r=True).
DETECTION_SYSTEM_PROMPT_COMPUTED_R = """You are a theoretical physicist evaluating proposed 4d N=1 supersymmetric \
gauge theory dualities.

You will see two theory JSONs labeled "Theory A" and "Theory B", each \
encoding a quiver gauge theory: gauge group ranks, bifundamental matter \
arrows, and a superpotential of cubic+ monomials. The R-charges are NOT \
given: the superconformal R-symmetry is fixed by a-maximization, so work it \
out yourself from the matter content and superpotential as your reasoning \
requires.

Your task: judge whether Theory A and Theory B are Seiberg-dual / IR-\
equivalent under the standard scope (cubic gauge anomaly cancellation, \
SU(N)^2 x U(1)_R mixed anomaly cancellation, R(W)=2 R-charge balance, \
F-term ideal consistency, bounded chiral-ring multiplicity matching).

Use the provided structured-output tool to return your verdict with a \
confidence level and a brief reasoning. Do not write any output outside \
the tool call."""


@dataclass(frozen=True)
class DetectionDecision:
    """The parsed result of a single detection call."""

    verdict: str               # "dual" | "not_dual"
    confidence: str            # "low" | "medium" | "high"
    reasoning: str
    latency_s: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None

    def __post_init__(self) -> None:
        if self.verdict not in {"dual", "not_dual"}:
            raise ValueError(
                f"DetectionDecision.verdict must be 'dual' or 'not_dual'; "
                f"got {self.verdict!r}"
            )
        if self.confidence not in {"low", "medium", "high"}:
            raise ValueError(
                f"DetectionDecision.confidence must be 'low' / 'medium' / "
                f"'high'; got {self.confidence!r}"
            )


def build_detection_user_message(
    sanitized_electric: Mapping[str, Any],
    sanitized_candidate: Mapping[str, Any],
) -> str:
    """Compose the user-turn prompt for one fixture.

    Both `sanitized_electric` and `sanitized_candidate` MUST come from
    `dualitycert.benchmark.sanitize_for_prompt()` — passing the raw
    fixture JSONs would leak the Seiberg-mutated / R-repaired
    provenance via the `name` / `node_labels` fields (Rule 3).
    """

    return (
        "Theory A (electric):\n"
        + json.dumps(dict(sanitized_electric), indent=2, sort_keys=True)
        + "\n\nTheory B (candidate dual):\n"
        + json.dumps(dict(sanitized_candidate), indent=2, sort_keys=True)
        + "\n\nQuestion: Are Theory A and Theory B Seiberg-dual / IR-"
        "equivalent under the verifier scope described above?"
    )


def run_detection(
    *,
    sanitized_electric: Mapping[str, Any],
    sanitized_candidate: Mapping[str, Any],
    client: LLMClient | None = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    computed_r: bool = False,
) -> DetectionDecision:
    """Single LLM call: prompt -> tool_use -> validated decision.

    On any structural failure (tool not called, schema-incompatible
    payload), `client.complete_structured` raises — there is no parse-
    fallback in the MVP backend set. Callers (the runner) should
    surface the failure rather than swallowing it.

    `computed_r=True` selects the judge-②b system prompt (the theories
    carry no R-charges; the verifier recomputes the superconformal R). The
    default leaves the locked judge-① prompt byte-for-byte unchanged.
    """

    if client is None:
        client = AnthropicAdapter()

    user_message = build_detection_user_message(
        sanitized_electric, sanitized_candidate
    )
    response = client.complete_structured(
        model=model,
        system=(
            DETECTION_SYSTEM_PROMPT_COMPUTED_R
            if computed_r
            else DETECTION_SYSTEM_PROMPT
        ),
        user=user_message,
        schema=DETECTION_DECISION_SCHEMA,
        tool_name=DETECTION_TOOL_NAME,
        max_tokens=max_tokens,
    )
    data = response.data
    return DetectionDecision(
        verdict=str(data["verdict"]),
        confidence=str(data["confidence"]),
        reasoning=str(data["reasoning"]),
        latency_s=response.latency_s,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
    )
