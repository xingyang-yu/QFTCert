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
    "DIAGNOSIS_SUSPECTED_CAUSES",
    "DEFAULT_MODEL",
    "DEFAULT_MAX_TOKENS",
    "DiagnosisDecision",
    "build_diagnosis_user_message",
    "run_diagnosis",
]


DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 2048

DIAGNOSIS_TOOL_NAME = "duality_diagnosis"

# PRIMARY task labels: the verifier *obligation* categories. These are
# what the verifier can actually report as failed, so they are the
# scorable ground truth. "rank" is deliberately NOT here — a rank
# perturbation surfaces as an anomaly obligation failure; rank is a
# perturbation *cause*, not a verifier obligation (see suspected_cause).
DIAGNOSIS_FAILURE_MODES: tuple[str, ...] = (
    "anomaly",
    "superpotential",
    "r_charge",
    "chiral_ring",
    "unknown",
)

# SECONDARY task labels: the upstream perturbation the model suspects
# caused the inconsistency. Scored only as secondary analysis (the
# primary diagnosis metric uses failure_modes).
DIAGNOSIS_SUSPECTED_CAUSES: tuple[str, ...] = (
    "drop_w_term",
    "flip_w_sign",
    "r_charge_perturb",
    "rank_perturb",
    "wrong_pair",
    "unknown",
)


DIAGNOSIS_DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "failure_modes": {
            "type": "array",
            "items": {"type": "string", "enum": list(DIAGNOSIS_FAILURE_MODES)},
            "description": (
                "PRIMARY: the verifier obligation categories Theory B "
                "violates relative to Theory A. Return an EMPTY list if the "
                "pair is a valid dual. Categories: anomaly (gauge / mixed "
                "'t Hooft anomalies), superpotential (W consistency / "
                "R(W)=2), r_charge (R-symmetry / central charge), chiral_ring "
                "(bounded chiral-ring multiplicities), unknown."
            ),
        },
        "suspected_cause": {
            "type": "array",
            "items": {"type": "string", "enum": list(DIAGNOSIS_SUSPECTED_CAUSES)},
            "description": (
                "SECONDARY (optional): the upstream edit you suspect broke "
                "the duality, from drop_w_term, flip_w_sign, r_charge_perturb, "
                "rank_perturb, wrong_pair, unknown. EMPTY if the pair is a "
                "valid dual."
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

PRIMARY task — identify which consistency obligation categories Theory B \
violates relative to Theory A, choosing from:
  - anomaly        : cubic gauge or SU(N)^2 x U(1)_R mixed 't Hooft anomalies
  - superpotential : superpotential consistency / R(W)=2 balance
  - r_charge       : R-symmetry assignment / central charge matching
  - chiral_ring    : bounded chiral-ring multiplicity mismatch
  - unknown        : a failure you cannot localize
Return these in failure_modes (EMPTY if the pair is a valid dual). Note a \
gauge-rank error shows up as an anomaly obligation failure — there is no \
separate "rank" obligation.

SECONDARY task (optional) — in suspected_cause, name the upstream edit you \
think broke the duality (drop_w_term, flip_w_sign, r_charge_perturb, \
rank_perturb, wrong_pair, unknown), or EMPTY for a valid dual.

Use the structured-output tool only; do not write anything outside the \
tool call."""


@dataclass(frozen=True)
class DiagnosisDecision:
    """Parsed result of a single diagnosis call."""

    failure_modes: tuple[str, ...]
    confidence: str
    reasoning: str
    suspected_cause: tuple[str, ...] = ()
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
        for cause in self.suspected_cause:
            if cause not in DIAGNOSIS_SUSPECTED_CAUSES:
                raise ValueError(
                    f"DiagnosisDecision.suspected_cause contains invalid cause "
                    f"{cause!r}; allowed {DIAGNOSIS_SUSPECTED_CAUSES!r}"
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
    causes = tuple(str(c) for c in data.get("suspected_cause", []) or [])
    return DiagnosisDecision(
        failure_modes=modes,
        suspected_cause=causes,
        confidence=str(data["confidence"]),
        reasoning=str(data["reasoning"]),
        latency_s=response.latency_s,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
    )
