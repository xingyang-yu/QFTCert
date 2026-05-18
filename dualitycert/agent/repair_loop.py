"""Verifier-in-the-loop repair cycle.

load claim -> evaluate -> (if failed) LLM repair -> re-evaluate, until
convergence or max-iteration cutoff.  The loop is model-agnostic: it
depends only on the LLMClient Protocol defined in dualitycert.agent.client.
Pass an AnthropicAdapter (default) or any other LLMClient-conforming object.

Every iteration records prompt, raw response, repaired JSON, and verifier
result so the pipeline is fully auditable.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from dualitycert.agent.client import AnthropicAdapter, LLMClient
from dualitycert.core.certificates import (
    OUTWARD_FAILED,
    OUTWARD_NONE,
    OUTWARD_PARTIAL,
    OUTWARD_PASSED,
    Certificate,
)
from dualitycert.qft.claims import build_claim_from_data
from dualitycert.qft.critic import build_repair_prompt
from dualitycert.qft.dualities import evaluate_claim


DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_ITERATIONS = 4
DEFAULT_MAX_TOKENS = 2048

PASSING_STATUSES = {OUTWARD_PASSED, OUTWARD_PARTIAL}

SYSTEM_PROMPT = """You are a theoretical physicist proposing a 4d N=1 supersymmetric gauge theory duality.

You will be given:
1. A JSON claim describing your candidate duality (electric theory, magnetic theory, symmetry map, operator map, superpotential).
2. A report from an automated verifier listing which consistency conditions your claim fails to satisfy, with the measured numerical evidence of each failure.

Your task:
- Modify the JSON claim so that the failed consistency conditions are satisfied.
- Use your physical reasoning. The verifier reports inconsistencies; it does NOT tell you what the correct values are. There is no oracle.
- Output ONLY the corrected JSON object. No prose, no markdown fences, no commentary.
- The JSON must be parseable by `json.loads` and use the same schema as the input.

About the verifier:
- It checks universal physics consistency conditions: anomaly cancellation, gauge invariance, R-charge balance (R(W) = 2 for SUSY), operator-map charge matching, etc.
- It reports each failed condition together with the principle being tested and the measured values.
- A PASS only means the implemented conditions are satisfied; it is not a proof of duality.
- Some conditions are marked out-of-scope (not implemented) and will not constrain your repair. Focus on the FAILED conditions."""


@dataclass(frozen=True)
class RepairIteration:
    """One iteration of the LLM repair loop."""

    iteration: int
    claim_data: dict[str, Any]
    outward_status: str
    failed_obligation_names: tuple[str, ...]
    prompt_sent: str | None
    llm_raw_response: str | None
    llm_repaired_data: dict[str, Any] | None
    parse_error: str | None


@dataclass(frozen=True)
class LLMRepairResult:
    """Full record of an end-to-end LLM repair attempt."""

    converged: bool
    final_outward_status: str
    iterations: tuple[RepairIteration, ...]
    final_certificate: Certificate
    model: str

    @property
    def iteration_count(self) -> int:
        return len(self.iterations)


def run_llm_repair_loop(
    initial_claim_data: dict[str, Any],
    *,
    client: LLMClient | None = None,
    model: str = DEFAULT_MODEL,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> LLMRepairResult:
    """Run claim -> verify -> (if failed) LLM repair -> re-verify, until converged.

    Returns a record of every iteration plus the final certificate. If the
    initial claim already passes, no LLM call is made (iteration 0 records
    the passing state and the loop exits).
    """

    if client is None:
        client = AnthropicAdapter()

    iterations: list[RepairIteration] = []
    current_data = json.loads(json.dumps(initial_claim_data))
    final_certificate: Certificate | None = None

    for iteration_idx in range(max_iterations + 1):
        claim = build_claim_from_data(current_data)
        certificate = evaluate_claim(claim)
        final_certificate = certificate
        failed_names = tuple(r.name for r in certificate.failed_obligations)

        if certificate.outward_status in PASSING_STATUSES:
            iterations.append(
                RepairIteration(
                    iteration=iteration_idx,
                    claim_data=current_data,
                    outward_status=certificate.outward_status,
                    failed_obligation_names=failed_names,
                    prompt_sent=None,
                    llm_raw_response=None,
                    llm_repaired_data=None,
                    parse_error=None,
                )
            )
            return LLMRepairResult(
                converged=True,
                final_outward_status=certificate.outward_status,
                iterations=tuple(iterations),
                final_certificate=certificate,
                model=model,
            )

        if iteration_idx == max_iterations:
            iterations.append(
                RepairIteration(
                    iteration=iteration_idx,
                    claim_data=current_data,
                    outward_status=certificate.outward_status,
                    failed_obligation_names=failed_names,
                    prompt_sent=None,
                    llm_raw_response=None,
                    llm_repaired_data=None,
                    parse_error="max_iterations reached without convergence",
                )
            )
            break

        repair_prompt = build_repair_prompt(claim, certificate)
        user_message = _compose_user_message(current_data, repair_prompt)

        raw_text = client.complete(
            model=model,
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            user=user_message,
        )

        repaired_data, parse_error = _parse_repaired_json(raw_text)

        iterations.append(
            RepairIteration(
                iteration=iteration_idx,
                claim_data=current_data,
                outward_status=certificate.outward_status,
                failed_obligation_names=failed_names,
                prompt_sent=user_message,
                llm_raw_response=raw_text,
                llm_repaired_data=repaired_data,
                parse_error=parse_error,
            )
        )

        if parse_error is not None or repaired_data is None:
            break
        current_data = repaired_data

    assert final_certificate is not None
    return LLMRepairResult(
        converged=False,
        final_outward_status=final_certificate.outward_status,
        iterations=tuple(iterations),
        final_certificate=final_certificate,
        model=model,
    )


def _compose_user_message(claim_data: dict[str, Any], repair_prompt: str) -> str:
    return (
        "Current claim JSON:\n"
        "```json\n"
        + json.dumps(claim_data, indent=2)
        + "\n```\n\n"
        "Verifier feedback:\n"
        + repair_prompt
        + "\n\nReturn the corrected JSON only."
    )


_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _parse_repaired_json(raw: str) -> tuple[dict[str, Any] | None, str | None]:
    """Best-effort extraction of a JSON object from the LLM's reply."""

    text = raw.strip()
    if not text:
        return None, "empty LLM response"

    fenced = _JSON_FENCE.findall(text)
    candidates = [c.strip() for c in fenced] if fenced else [text]

    last_error: str | None = None
    for candidate in candidates:
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = f"JSONDecodeError: {exc.msg} (line {exc.lineno})"
            continue
        if not isinstance(obj, dict):
            last_error = f"top-level JSON is {type(obj).__name__}, expected object"
            continue
        return obj, None
    return None, last_error or "no parseable JSON found"
