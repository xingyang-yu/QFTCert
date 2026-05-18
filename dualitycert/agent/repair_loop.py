"""Minimal Claude-API repair loop.

The first end-to-end LLM-in-the-loop demo: load a (possibly broken) claim,
hand the verifier-generated repair prompt to Claude, parse the returned
JSON, re-verify, iterate until pass or max-iteration cutoff.

Intentionally small and verbose: every iteration's prompt, raw response,
and verifier result is recorded so the pipeline is auditable end-to-end.
The shape here is the contract a future production loop should preserve.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

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

SYSTEM_PROMPT = """You are a repair agent for QFTCert, a verifier for 4d N=1 supersymmetric gauge theory duality claims.

You will be given:
1. The current JSON claim (in the SQCD claim schema).
2. A repair prompt describing which implemented consistency obligations failed and suggested minimal edits.

Your task:
- Return a corrected JSON claim that addresses the failed obligations while preserving the stated conventions (baryon number normalization, R-charge formulas, etc.).
- Make the minimum necessary edit. Do not restructure unrelated fields.
- Output ONLY the corrected JSON object. No prose, no markdown fences, no commentary.
- The JSON must be parseable by `json.loads` and conform to the same schema as the input.

Reminders about the SQCD profile:
- Standard magnetic gauge rank is Nf - Nc.
- Baryon convention: B(Q) = 1/Nc, B(q) = 1/Nmag.
- R-charges: R(Q) = R(Qtilde) = 1 - Nc/Nf; R(q) = R(qtilde) = Nc/Nf; R(M) = 2(Nf-Nc)/Nf.
- Magnetic superpotential: W = M q qtilde, with M present iff magnetic.include_meson is true."""


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
    client: Any | None = None,
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
        client = _make_default_client()

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

        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        raw_text = _extract_text(response)

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


def _make_default_client() -> Any:
    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise RuntimeError(
            "anthropic SDK is not installed. Install with: "
            "pip install -e .[llm]"
        ) from exc
    return Anthropic()


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


def _extract_text(response: Any) -> str:
    """Extract the assistant's text from an Anthropic Messages response."""

    parts: list[str] = []
    for block in getattr(response, "content", []) or []:
        text = getattr(block, "text", None)
        if text is not None:
            parts.append(text)
    return "".join(parts).strip()


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
