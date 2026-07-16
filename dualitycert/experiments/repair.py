"""Verifier-in-the-loop repair harness (Layer C, Deliverable 6 + 7).

Four arms, selected by `arm`:

  - single_shot_repair : one edit attempt, no feedback loop (K=1).
  - generic_retry      : up to K rounds; feedback is generic boilerplate
                         ("failed, try again") — controls for extra
                         attempts / tokens without grounded information.
  - llm_critic         : up to K rounds; a non-verifier-grounded critique
                         (interface + stub; an LLM critic client can be
                         injected, otherwise a fixed template is used).
  - verifier_feedback  : up to K rounds; structured verifier feedback
                         (failed obligation categories + residuals) at
                         the configured detail level.

Each round the model returns a structured `{action, patches, reasoning}`
(or a full revised Theory B). The candidate is validated, then verified
under a *feedback* verifier; success is judged by a *final-evaluation*
verifier that may be strictly stricter (anti-gaming guardrail). The
model never supplies verifier settings — they come only from the config,
and patches targeting verifier metadata are rejected.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from dualitycert.agent.client import LLMClient
from dualitycert.benchmark.fixtures import sanitize_for_prompt
from dualitycert.core.objects import DualityClaim
from dualitycert.experiments.chains import canonical_theory_hash
from dualitycert.experiments.config import ExperimentConfig, VerifierConfig
from dualitycert.experiments.jsonpatch import apply_patches
from dualitycert.experiments.manifest import ManifestRecord
from dualitycert.experiments.verifier import VerifierOutcome, run_verifier
from dualitycert.qft.critic import build_repair_prompt
from dualitycert.qft.dualities import evaluate_claim
from dualitycert.qft.pure_quiver_json import (
    PureQuiverJSONError,
    pure_quiver_from_json,
)


__all__ = [
    "ARMS",
    "REPAIR_DECISION_SCHEMA",
    "REPAIR_DECISION_SCHEMA_FULL",
    "REPAIR_SYSTEM_PROMPT",
    "REPAIR_SYSTEM_PROMPT_FULL",
    "REPAIR_TOOL_NAME",
    "RepairAction",
    "RepairResult",
    "RepairRoundLog",
    "apply_repair_action",
    "build_feedback",
    "build_repair_user_message",
    "run_repair_experiment",
    "run_repair_loop",
    "score_repair",
    "theory_edit_distance",
    "validate_theory_schema",
]


ARMS: tuple[str, ...] = (
    "single_shot_repair",
    "generic_retry",
    "llm_critic",
    "verifier_feedback",
)

REPAIR_TOOL_NAME = "repair_action"

REPAIR_DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["edit_candidate", "no_change", "abstain"],
            "description": (
                "edit_candidate: apply the patches (or full_theory). "
                "no_change: leave Theory B as-is. abstain: give up "
                "(repair impossible)."
            ),
        },
        "patches": {
            "type": "array",
            "description": (
                "RFC-6902 JSON Patch ops (add/remove/replace) against "
                "Theory B, e.g. {\"op\":\"replace\","
                "\"path\":\"/superpotential/0/coefficient\",\"value\":\"-1\"}."
            ),
            "items": {
                "type": "object",
                "properties": {
                    "op": {"type": "string", "enum": ["add", "remove", "replace"]},
                    "path": {"type": "string"},
                    "value": {},
                },
                "required": ["op", "path"],
            },
        },
        "full_theory": {
            "type": "object",
            "description": (
                "Optional: a complete revised Theory B (used instead of "
                "patches when wholesale rewriting is easier)."
            ),
        },
        "reasoning": {
            "type": "string",
            "maxLength": 300,
            "description": (
                "ONE short sentence (<200 characters) naming the edit. Do NOT "
                "restate the theories or derive anything here — a long "
                "reasoning string overflows the output budget and truncates "
                "the whole tool call."
            ),
        },
    },
    "required": ["action", "reasoning"],
}


REPAIR_DECISION_SCHEMA_FULL: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["edit_candidate", "no_change", "abstain"],
            "description": (
                "edit_candidate: replace Theory B with full_theory. "
                "no_change: leave Theory B as-is. abstain: give up "
                "(repair impossible)."
            ),
        },
        "full_theory": {
            "type": "object",
            "description": (
                "The COMPLETE revised Theory B as one JSON object with the "
                "same schema as the input (name, node_labels, ranks, "
                "u1_globals, arrows, superpotential, and singlets when "
                "present). Required when action is edit_candidate."
            ),
        },
        "reasoning": {
            "type": "string",
            "maxLength": 300,
            "description": (
                "ONE short sentence (<200 characters) naming the edit. Do NOT "
                "restate the theories or derive anything here — a long "
                "reasoning string overflows the output budget and truncates "
                "the whole tool call."
            ),
        },
    },
    "required": ["action", "reasoning"],
}


REPAIR_SYSTEM_PROMPT = """You are a theoretical physicist repairing a proposed 4d N=1 \
supersymmetric gauge theory duality.

You are given Theory A (electric) and Theory B (a candidate dual that is \
NOT yet consistent). Edit Theory B so that it becomes a valid Seiberg \
dual of Theory A under the verifier scope (gauge anomaly cancellation, \
SU(N)^2 x U(1)_R mixed anomalies, R(W)=2 balance, F-term / superpotential \
consistency, bounded chiral-ring multiplicity matching).

Return your edit via the structured tool only:
  - action "edit_candidate" with a list of JSON Patch operations against \
Theory B (preferred), or a full revised Theory B in `full_theory`;
  - action "no_change" if Theory B is already correct;
  - action "abstain" if you believe no edit can make it consistent.

You may only edit the physics of Theory B (ranks, arrows/R-charges, \
superpotential). You cannot change the verifier or its settings. \
Theory B must remain a genuine dual DESCRIPTION distinct from Theory A: \
submitting a copy of Theory A as Theory B is not a repair (the identity \
pair trivially satisfies every consistency condition) and is scored as \
failure. Keep `reasoning` to ONE short sentence -- do your thinking \
silently; a long reasoning string overflows the output budget and \
truncates your entire tool call."""


REPAIR_SYSTEM_PROMPT_FULL = """You are a theoretical physicist repairing a proposed \
4d N=1 supersymmetric gauge theory duality.

You are given Theory A (electric) and Theory B (a candidate dual that is \
NOT yet consistent). Edit Theory B so that it becomes a valid Seiberg \
dual of Theory A under the verifier scope (gauge anomaly cancellation, \
SU(N)^2 x U(1)_R mixed anomalies, R(W)=2 balance, F-term / superpotential \
consistency, bounded chiral-ring multiplicity matching).

Return your edit via the structured tool only:
  - action "edit_candidate" with the COMPLETE revised Theory B in \
`full_theory` (the whole JSON object, same schema as the input — not a \
diff, not a fragment);
  - action "no_change" if Theory B is already correct;
  - action "abstain" if you believe no edit can make it consistent.

You may only edit the physics of Theory B (ranks, arrows/R-charges, \
superpotential). You cannot change the verifier or its settings. \
Theory B must remain a genuine dual DESCRIPTION distinct from Theory A: \
submitting a copy of Theory A as Theory B is not a repair (the identity \
pair trivially satisfies every consistency condition) and is scored as \
failure. Keep `reasoning` to ONE short sentence -- do your thinking \
silently; a long reasoning string overflows the output budget and \
truncates your entire tool call."""


@dataclass(frozen=True)
class RepairAction:
    action: str
    patches: tuple[dict[str, Any], ...] = ()
    full_theory: dict[str, Any] | None = None
    reasoning: str = ""

    def __post_init__(self) -> None:
        if self.action not in {"edit_candidate", "no_change", "abstain"}:
            raise ValueError(
                f"RepairAction.action must be edit_candidate / no_change / "
                f"abstain; got {self.action!r}"
            )

    @classmethod
    def from_data(cls, data: Mapping[str, Any]) -> "RepairAction":
        return cls(
            action=str(data["action"]),
            patches=tuple(dict(p) for p in data.get("patches", []) or []),
            full_theory=(
                dict(data["full_theory"])
                if data.get("full_theory") is not None
                else None
            ),
            reasoning=str(data.get("reasoning", "")),
        )


@dataclass(frozen=True)
class RepairRoundLog:
    round: int
    feedback_status: str
    feedback_text: str
    action: str
    reasoning: str
    edit_applied: bool
    apply_error: str | None
    feedback_status_after: str | None
    final_status_after: str | None


@dataclass
class RepairResult:
    fixture_id: str
    depth: int
    perturbation_class: str
    repairable: bool
    label: str
    arm: str
    success: bool
    success_round: int | None
    n_rounds: int
    final_status: str | None
    generalization_to_final_check: bool | None
    abstained: bool
    invalid: bool
    out_of_scope: bool
    verifier_calls: int
    edit_distance: int
    # Copy-cheat guard: the identity pair (A, A) trivially CERTIFIES (the
    # verifier checks pair consistency, and every theory is consistent with
    # itself), so a model that replaces Theory B with a copy of Theory A
    # would otherwise score as success. Flagged + scored as failure.
    copied_electric: bool = False
    # do-no-harm challenge fields (None unless force_model_on_certified
    # and the candidate started consistent under the final verifier).
    started_certified: bool | None = None
    harmed: bool | None = None
    unnecessary_edit: bool | None = None
    rounds: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "depth": self.depth,
            "perturbation_class": self.perturbation_class,
            "repairable": self.repairable,
            "label": self.label,
            "arm": self.arm,
            "success": self.success,
            "success_round": self.success_round,
            "n_rounds": self.n_rounds,
            "final_status": self.final_status,
            "generalization_to_final_check": self.generalization_to_final_check,
            "abstained": self.abstained,
            "invalid": self.invalid,
            "out_of_scope": self.out_of_scope,
            "verifier_calls": self.verifier_calls,
            "edit_distance": self.edit_distance,
            "copied_electric": self.copied_electric,
            "started_certified": self.started_certified,
            "harmed": self.harmed,
            "unnecessary_edit": self.unnecessary_edit,
            "rounds": self.rounds,
        }


# ----------------------------------------------------------------------
# Arm helpers.
# ----------------------------------------------------------------------


def _arm_rounds(arm: str, max_rounds: int) -> int:
    return 1 if arm == "single_shot_repair" else max_rounds


def _feedback_kind(arm: str) -> str:
    return {
        "single_shot_repair": "none",
        "generic_retry": "generic",
        "llm_critic": "critic",
        "verifier_feedback": "verifier",
    }[arm]


# ----------------------------------------------------------------------
# Feedback construction.
# ----------------------------------------------------------------------


def build_feedback(
    *,
    arm: str,
    detail: str,
    electric: Mapping[str, Any],
    candidate: Mapping[str, Any],
    outcome: VerifierOutcome,
    feedback_verifier: VerifierConfig,
    critic_client: LLMClient | None = None,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 1024,
) -> str:
    kind = _feedback_kind(arm)
    if kind == "none":
        return ""
    if kind == "generic":
        return (
            "The candidate failed verification. Try a different edit to make "
            "Theory B a valid dual of Theory A."
        )
    if kind == "critic":
        return _critic_feedback(
            electric, candidate, critic_client, model=model, max_tokens=max_tokens
        )
    # verifier feedback at the configured detail level.
    if detail == "coarse":
        cats = ", ".join(outcome.failed_categories) or "(none reported)"
        return f"The candidate failed verification. Failing categories: {cats}."
    if detail == "detailed":
        return _detailed_feedback(electric, candidate, feedback_verifier)
    # medium (default): obligation names + categories, no measured values.
    lines = ["The candidate failed verification. Failed obligations:"]
    for o in outcome.failed_obligations:
        lines.append(f"  - {o['name']} (category: {o['category']})")
    if not outcome.failed_obligations:
        lines.append("  - (verifier reported no obligation names)")
    return "\n".join(lines)


def _critic_feedback(
    electric: Mapping[str, Any],
    candidate: Mapping[str, Any],
    critic_client: LLMClient | None,
    *,
    model: str,
    max_tokens: int,
) -> str:
    """Non-verifier-grounded critique (interface + stub).

    With a `critic_client`, asks it for free-form critique; the critic is
    NOT shown verifier obligations, so its feedback is not grounded in the
    oracle. Without one, returns a fixed non-grounded template.
    """

    if critic_client is None:
        return (
            "A reviewer is not convinced Theory B is a valid dual. Reconsider "
            "the gauge ranks, the R-charge assignments, and whether the "
            "superpotential closes consistently."
        )
    system = (
        "You are a skeptical physicist reviewing a proposed duality. You do "
        "NOT have access to any automated verifier. Give brief, qualitative "
        "critique of why Theory B may not be a valid dual of Theory A."
    )
    user = (
        "Theory A:\n"
        + _prompt_json(electric)
        + "\n\nTheory B:\n"
        + _prompt_json(candidate)
    )
    try:
        return critic_client.complete(
            model=model, system=system, user=user, max_tokens=max_tokens
        )
    except Exception as exc:  # critic failure should not crash the loop
        return f"(critic unavailable: {type(exc).__name__})"


def _detailed_feedback(
    electric: Mapping[str, Any],
    candidate: Mapping[str, Any],
    feedback_verifier: VerifierConfig,
) -> str:
    """Grounded, detailed feedback via the certificate's repair prompt."""

    try:
        e_theory = pure_quiver_from_json(dict(electric))
        c_theory = pure_quiver_from_json(dict(candidate))
    except (PureQuiverJSONError, ValueError) as exc:
        return f"The candidate failed verification (schema error: {exc})."
    claim = DualityClaim(
        name="repair feedback",
        electric_theory=e_theory,
        magnetic_theory=c_theory,
        metadata={
            "duality_profile": feedback_verifier.duality_profile,
            "bounded_chiral_ring": feedback_verifier.bounded_chiral_ring_metadata(),
        },
    )
    cert = evaluate_claim(claim)
    return build_repair_prompt(claim, cert)


# ----------------------------------------------------------------------
# Applying a repair.
# ----------------------------------------------------------------------


_FORBIDDEN_PATCH_PREFIXES = ("/metadata", "/bounded_chiral_ring", "/duality_profile")


def apply_repair_action(
    current: Mapping[str, Any], action: RepairAction
) -> tuple[dict[str, Any], str | None]:
    """Apply a repair action; return (new_candidate, error).

    Anti-gaming: patches/`full_theory` that try to introduce verifier
    settings are rejected. The verifier config is always sourced from the
    experiment config, never from model output.
    """

    if action.action == "no_change":
        return dict(current), None
    if action.action == "abstain":
        return dict(current), "abstain"

    if action.full_theory is not None:
        candidate = dict(action.full_theory)
        for forbidden in ("metadata", "bounded_chiral_ring", "duality_profile"):
            if forbidden in candidate:
                return dict(current), (
                    f"rejected full_theory that injects verifier setting "
                    f"{forbidden!r}"
                )
        return candidate, None

    for p in action.patches:
        path = str(p.get("path", ""))
        if any(path.startswith(pre) for pre in _FORBIDDEN_PATCH_PREFIXES):
            return dict(current), (
                f"rejected patch targeting verifier setting path {path!r}"
            )
    new, err = apply_patches(dict(current), list(action.patches))
    return (new if err is None else dict(current)), err


def validate_theory_schema(theory_json: Mapping[str, Any]) -> str | None:
    """Return None if `theory_json` is a well-formed pure-quiver theory."""

    try:
        pure_quiver_from_json(dict(theory_json))
    except (PureQuiverJSONError, ValueError, KeyError, TypeError) as exc:
        return f"{type(exc).__name__}: {exc}"
    return None


# ----------------------------------------------------------------------
# Repair call.
# ----------------------------------------------------------------------


def _prompt_json(theory: Mapping[str, Any]) -> str:
    """Compact JSON for model prompts: ~44% fewer tokens than indent=2
    (whitespace dominates deeply-nested theory JSONs), which nearly doubles
    what a free-tier daily token budget can run. Artifact files on disk keep
    indent=2 for human readability."""

    return json.dumps(dict(theory), sort_keys=True, separators=(",", ":"))


def build_repair_user_message(
    electric: Mapping[str, Any],
    candidate: Mapping[str, Any],
    feedback_text: str,
    *,
    round_idx: int,
) -> str:
    parts = [
        "Theory A (electric, target):",
        _prompt_json(electric),
        "",
        "Theory B (candidate to repair):",
        _prompt_json(candidate),
        "",
        f"Repair round: {round_idx}",
    ]
    if feedback_text:
        parts += ["", "Feedback:", feedback_text]
    parts += [
        "",
        "Return a repair_action that makes Theory B a valid dual of Theory A.",
    ]
    return "\n".join(parts)


def _call_repair(
    client: LLMClient,
    electric: Mapping[str, Any],
    candidate: Mapping[str, Any],
    feedback_text: str,
    *,
    round_idx: int,
    model: str,
    max_tokens: int,
    edit_mode: str = "patches",
) -> tuple[RepairAction | None, str | None]:
    user = build_repair_user_message(
        electric, candidate, feedback_text, round_idx=round_idx
    )
    if edit_mode == "full_theory":
        system, schema = REPAIR_SYSTEM_PROMPT_FULL, REPAIR_DECISION_SCHEMA_FULL
    else:
        system, schema = REPAIR_SYSTEM_PROMPT, REPAIR_DECISION_SCHEMA
    try:
        response = client.complete_structured(
            model=model,
            system=system,
            user=user,
            schema=schema,
            tool_name=REPAIR_TOOL_NAME,
            max_tokens=max_tokens,
        )
        return RepairAction.from_data(response.data), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


# ----------------------------------------------------------------------
# The loop.
# ----------------------------------------------------------------------


def run_repair_loop(
    record: ManifestRecord,
    *,
    theory_root: Path | str,
    client: LLMClient,
    config: ExperimentConfig,
    arm: str | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
    critic_client: LLMClient | None = None,
    force_model_on_certified: bool | None = None,
) -> RepairResult:
    """Run the repair loop for one fixture and return a structured result."""

    if arm is None:
        arm = (
            "single_shot_repair"
            if config.repair.feedback_mode == "none"
            else config.repair.feedback_mode
        )
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}; expected one of {ARMS!r}")

    model = model or config.model.model
    max_tokens = max_tokens or config.model.max_tokens
    rounds = _arm_rounds(arm, config.repair.max_rounds)
    detail = config.repair.feedback_detail
    feedback_vcfg = config.feedback_verifier()
    final_vcfg = config.final_eval_verifier()
    force_certified = (
        config.repair.force_model_on_certified
        if force_model_on_certified is None
        else force_model_on_certified
    )

    electric = sanitize_for_prompt(
        _load_theory(theory_root, record.theory_a_path), theory_label="Theory A"
    )
    original_candidate = sanitize_for_prompt(
        _load_theory(theory_root, record.theory_b_path), theory_label="Theory B"
    )
    current = json.loads(json.dumps(original_candidate))
    # Copy-cheat guard baseline. Exact canonical hash, deliberately NOT the
    # `theories_isomorphic` notion: for a self-dual electric (e.g. dP_1 at its
    # rank-preserving node) the TRUE magnetic dual is isomorphic to Theory A,
    # so an isomorphism-level guard would reject correct repairs. A verbatim
    # copy is the degenerate strategy worth catching; node-permuted copies
    # remain visible in the audit log.
    electric_hash = canonical_theory_hash(electric)

    rounds_log: list[RepairRoundLog] = []
    verifier_calls = 0
    success = False
    success_round: int | None = None
    final_status: str | None = None
    gen_to_final: bool | None = None
    abstained = False
    invalid = False
    out_of_scope = False
    copied_electric = False
    n_rounds = 0
    harmed: bool | None = None
    unnecessary_edit: bool | None = None

    # Challenge mode: record whether the candidate starts consistent under
    # the FINAL verifier, so harm / unnecessary edits are measurable.
    started_certified: bool | None = None
    if force_certified:
        started_certified = run_verifier(electric, current, final_vcfg).is_certified
        verifier_calls += 1
        harmed = False
        unnecessary_edit = False

    for r in range(1, rounds + 1):
        n_rounds = r

        fb_outcome = run_verifier(electric, current, feedback_vcfg)
        verifier_calls += 1

        # Already consistent under the feedback verifier: in production
        # mode, short-circuit (do-no-harm — never touch a passing
        # candidate). In challenge mode, fall through and force the model
        # to decide explicitly.
        if fb_outcome.is_certified and not force_certified:
            final_outcome = run_verifier(electric, current, final_vcfg)
            verifier_calls += 1
            final_status = final_outcome.status
            gen_to_final = bool(final_outcome.is_certified)
            success = bool(final_outcome.is_certified)
            success_round = r if success else None
            rounds_log.append(
                RepairRoundLog(
                    round=r,
                    feedback_status=fb_outcome.status,
                    feedback_text="(already consistent under feedback verifier)",
                    action="no_change",
                    reasoning="",
                    edit_applied=False,
                    apply_error=None,
                    feedback_status_after=fb_outcome.status,
                    final_status_after=final_outcome.status,
                )
            )
            break

        if fb_outcome.is_certified:
            feedback_text = (
                "The candidate currently PASSES verification. Decide whether "
                "any edit is warranted; no_change is acceptable."
            )
        else:
            feedback_text = build_feedback(
                arm=arm,
                detail=detail,
                electric=electric,
                candidate=current,
                outcome=fb_outcome,
                feedback_verifier=feedback_vcfg,
                critic_client=critic_client,
                model=model,
                max_tokens=max_tokens,
            )
        action, call_err = _call_repair(
            client,
            electric,
            current,
            feedback_text,
            round_idx=r,
            model=model,
            max_tokens=max_tokens,
            edit_mode=config.repair.edit_mode,
        )
        if action is None:
            invalid = True
            rounds_log.append(
                RepairRoundLog(
                    round=r,
                    feedback_status=fb_outcome.status,
                    feedback_text=feedback_text,
                    action="call_error",
                    reasoning="",
                    edit_applied=False,
                    apply_error=call_err,
                    feedback_status_after=None,
                    final_status_after=None,
                )
            )
            break

        if action.action == "abstain":
            abstained = True
            rounds_log.append(
                RepairRoundLog(
                    round=r,
                    feedback_status=fb_outcome.status,
                    feedback_text=feedback_text,
                    action="abstain",
                    reasoning=action.reasoning,
                    edit_applied=False,
                    apply_error=None,
                    feedback_status_after=None,
                    final_status_after=None,
                )
            )
            break

        new_candidate, apply_err = apply_repair_action(current, action)
        if apply_err is not None:
            invalid = True
            rounds_log.append(
                RepairRoundLog(
                    round=r,
                    feedback_status=fb_outcome.status,
                    feedback_text=feedback_text,
                    action=action.action,
                    reasoning=action.reasoning,
                    edit_applied=False,
                    apply_error=apply_err,
                    feedback_status_after=None,
                    final_status_after=None,
                )
            )
            break

        schema_err = validate_theory_schema(new_candidate)
        if schema_err is not None:
            invalid = True
            rounds_log.append(
                RepairRoundLog(
                    round=r,
                    feedback_status=fb_outcome.status,
                    feedback_text=feedback_text,
                    action=action.action,
                    reasoning=action.reasoning,
                    edit_applied=False,
                    apply_error=f"schema_invalid: {schema_err}",
                    feedback_status_after=None,
                    final_status_after=None,
                )
            )
            break

        if canonical_theory_hash(new_candidate) == electric_hash:
            copied_electric = True
            rounds_log.append(
                RepairRoundLog(
                    round=r,
                    feedback_status=fb_outcome.status,
                    feedback_text=feedback_text,
                    action=action.action,
                    reasoning=action.reasoning,
                    edit_applied=False,
                    apply_error=(
                        "copied_electric: the revised Theory B is a verbatim "
                        "copy of Theory A; the identity pair trivially "
                        "certifies, so this is not a repair"
                    ),
                    feedback_status_after=None,
                    final_status_after=None,
                )
            )
            break

        new_fb = run_verifier(electric, new_candidate, feedback_vcfg)
        new_final = run_verifier(electric, new_candidate, final_vcfg)
        verifier_calls += 2

        # Challenge accounting: if the candidate was passing at this
        # round's start and the model changed it anyway, that is an
        # unnecessary edit; if the change broke the final verifier, harm.
        if force_certified and fb_outcome.is_certified:
            changed = (
                action.action == "edit_candidate"
                and theory_edit_distance(current, new_candidate) > 0
            )
            if changed:
                unnecessary_edit = True
                if not new_final.is_certified:
                    harmed = True

        current = new_candidate

        rounds_log.append(
            RepairRoundLog(
                round=r,
                feedback_status=fb_outcome.status,
                feedback_text=feedback_text,
                action=action.action,
                reasoning=action.reasoning,
                edit_applied=True,
                apply_error=None,
                feedback_status_after=new_fb.status,
                final_status_after=new_final.status,
            )
        )

        final_status = new_final.status
        if new_fb.is_certified:
            gen_to_final = bool(new_final.is_certified)
            success = bool(new_final.is_certified)
            success_round = r if success else None
            break
        if not new_fb.in_scope:
            out_of_scope = True
            break
        # still failing in-scope: carry `current` forward to next round.

    edit_distance = theory_edit_distance(original_candidate, current)

    return RepairResult(
        fixture_id=record.fixture_id,
        depth=record.depth,
        perturbation_class=record.perturbation_class,
        repairable=record.repairable,
        label=record.label,
        arm=arm,
        success=success,
        success_round=success_round,
        n_rounds=n_rounds,
        final_status=final_status,
        generalization_to_final_check=gen_to_final,
        abstained=abstained,
        invalid=invalid,
        out_of_scope=out_of_scope,
        verifier_calls=verifier_calls,
        edit_distance=edit_distance,
        copied_electric=copied_electric,
        started_certified=started_certified,
        harmed=harmed,
        unnecessary_edit=unnecessary_edit,
        rounds=[_round_to_dict(rl) for rl in rounds_log],
    )


# ----------------------------------------------------------------------
# Experiment driver + scoring.
# ----------------------------------------------------------------------


@dataclass
class RepairExperimentResult:
    run_id: str
    run_dir: Path
    arm: str
    results: list[RepairResult] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


def run_repair_experiment(
    records: Sequence[ManifestRecord],
    *,
    theory_root: Path | str,
    client: LLMClient,
    config: ExperimentConfig,
    arm: str,
    out_dir: Path | str,
    run_id: str | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
    critic_client: LLMClient | None = None,
    repairable_only: bool = True,
    force_model_on_certified: bool | None = None,
    timestamp_override: str | None = None,
    resume: bool = False,
) -> RepairExperimentResult:
    """Run the repair loop over a manifest under `arm` and write artefacts."""

    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}; expected one of {ARMS!r}")

    selected = [
        r for r in records if (r.repairable or not repairable_only)
    ]
    if not selected:
        raise ValueError(
            "run_repair_experiment: no fixtures selected "
            "(set repairable_only=False to include positives / wrong_pair)"
        )

    if run_id is None:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(out_dir) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Results stream to disk as each fixture finishes (not in one dump at
    # the end) so a killed/hung run keeps its progress inspectable:
    # `wc -l repair_results.jsonl` is the live fixture count.
    results_path = run_dir / "repair_results.jsonl"
    results: list[RepairResult] = []
    done_ids: set[str] = set()
    if resume and results_path.exists():
        # Recover completed fixtures from an interrupted run with the same
        # run-id. `RepairResult(**d)` inverts `to_dict` (keys match fields
        # 1:1). A partial trailing line (process killed mid-write) stops
        # recovery there; that fixture and everything after it re-run.
        selected_ids = {r.fixture_id for r in selected}
        aliens = 0
        for line in results_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                prior = RepairResult(**json.loads(line))
            except (json.JSONDecodeError, TypeError):
                break
            if prior.fixture_id not in selected_ids:
                aliens += 1
                continue
            if prior.fixture_id in done_ids:
                continue
            done_ids.add(prior.fixture_id)
            results.append(prior)
        msg = (
            f"[run-repair-loop] resume: {len(done_ids)} fixtures already "
            f"complete, running the remaining {len(selected) - len(done_ids)}"
        )
        if aliens:
            msg += f" (dropped {aliens} records not in this manifest)"
        print(msg, file=sys.stderr, flush=True)
    with results_path.open("w", encoding="utf-8") as fh:
        for res in results:
            fh.write(json.dumps(res.to_dict(), sort_keys=True, ensure_ascii=False))
            fh.write("\n")
        fh.flush()
        for i, rec in enumerate(selected, 1):
            if rec.fixture_id in done_ids:
                continue
            res = run_repair_loop(
                rec,
                theory_root=theory_root,
                client=client,
                config=config,
                arm=arm,
                model=model,
                max_tokens=max_tokens,
                critic_client=critic_client,
                force_model_on_certified=force_model_on_certified,
            )
            results.append(res)
            fh.write(json.dumps(res.to_dict(), sort_keys=True, ensure_ascii=False))
            fh.write("\n")
            fh.flush()
            print(
                f"[run-repair-loop] {i}/{len(selected)} "
                f"fixture={res.fixture_id} final_status={res.final_status}",
                file=sys.stderr,
                flush=True,
            )
    summary = score_repair(results, max_rounds=config.repair.max_rounds)
    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    timestamp = timestamp_override or datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )
    (run_dir / "metadata.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "arm": arm,
                "model": model or config.model.model,
                "n_fixtures": len(selected),
                "max_rounds": config.repair.max_rounds,
                "feedback_detail": config.repair.feedback_detail,
                "feedback_verifier": config.feedback_verifier().to_dict(),
                "final_eval_verifier": config.final_eval_verifier().to_dict(),
                "timestamp": timestamp,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return RepairExperimentResult(
        run_id=run_id,
        run_dir=run_dir,
        arm=arm,
        results=results,
        summary=summary,
    )


def score_repair(
    results: Sequence[RepairResult],
    *,
    max_rounds: int = 5,
) -> dict[str, Any]:
    """Aggregate repair results: success@K, iterations, rates, breakdowns."""

    n = len(results)
    successes = [r for r in results if r.success]
    n_success = len(successes)

    def success_at(k: int) -> int:
        return sum(
            1
            for r in results
            if r.success and r.success_round is not None and r.success_round <= k
        )

    iterations_to_success = sorted(
        r.success_round for r in successes if r.success_round is not None
    )
    verifier_calls_total = sum(r.verifier_calls for r in results)
    verifier_calls_success = sum(r.verifier_calls for r in successes)

    final_status_counts: dict[str, int] = {}
    for r in results:
        key = r.final_status or "none"
        final_status_counts[key] = final_status_counts.get(key, 0) + 1

    # "passed feedback but failed final" = generalization gap.
    gen_gap = sum(
        1
        for r in results
        if r.generalization_to_final_check is False
    )

    positives = [r for r in results if r.label == "CERTIFIED"]
    do_no_harm_rate = (
        sum(1 for r in positives if r.final_status == "CERTIFIED") / len(positives)
        if positives
        else None
    )

    # Challenge-mode metrics (only over fixtures that started consistent).
    started = [r for r in results if getattr(r, "started_certified", None)]
    harm_rate = (
        sum(1 for r in started if getattr(r, "harmed", None)) / len(started)
        if started
        else None
    )
    unnecessary_edit_rate = (
        sum(1 for r in started if getattr(r, "unnecessary_edit", None)) / len(started)
        if started
        else None
    )

    summary: dict[str, Any] = {
        "n_fixtures": n,
        "n_success": n_success,
        "success_rate": (n_success / n) if n else 0.0,
        "success_at_1": (success_at(1) / n) if n else 0.0,
        "success_at_3": (success_at(3) / n) if n else 0.0,
        "success_at_5": (success_at(5) / n) if n else 0.0,
        "success_at_k": {
            str(k): (success_at(k) / n) if n else 0.0
            for k in range(1, max_rounds + 1)
        },
        "iterations_to_success": iterations_to_success,
        "mean_iterations_to_success": (
            sum(iterations_to_success) / len(iterations_to_success)
            if iterations_to_success
            else None
        ),
        "verifier_calls_total": verifier_calls_total,
        "verifier_calls_per_success": (
            verifier_calls_success / n_success if n_success else None
        ),
        "invalid_json_rate": (
            sum(1 for r in results if r.invalid) / n if n else 0.0
        ),
        "out_of_scope_rate": (
            sum(1 for r in results if r.out_of_scope) / n if n else 0.0
        ),
        "abstention_rate": (
            sum(1 for r in results if r.abstained) / n if n else 0.0
        ),
        "copied_electric_rate": (
            sum(1 for r in results if r.copied_electric) / n if n else 0.0
        ),
        "generalization_to_final_check_gap": gen_gap,
        "do_no_harm_rate": do_no_harm_rate,
        "n_started_certified": len(started),
        "harm_rate": harm_rate,
        "unnecessary_edit_rate": unnecessary_edit_rate,
        "mean_edit_distance": (
            sum(r.edit_distance for r in results) / n if n else 0.0
        ),
        "final_status_counts": final_status_counts,
        "success_rate_by_depth": _rate_by(results, lambda r: r.depth),
        "success_rate_by_class": _rate_by(results, lambda r: r.perturbation_class),
    }
    return summary


def _rate_by(
    results: Sequence[RepairResult], key: Callable[[RepairResult], Any]
) -> dict[str, float]:
    counts: dict[str, int] = {}
    succ: dict[str, int] = {}
    for r in results:
        k = str(key(r))
        counts[k] = counts.get(k, 0) + 1
        succ[k] = succ.get(k, 0) + int(r.success)
    return {k: (succ[k] / counts[k] if counts[k] else 0.0) for k in counts}


# ----------------------------------------------------------------------
# Edit distance + helpers.
# ----------------------------------------------------------------------


def theory_edit_distance(
    a: Mapping[str, Any], b: Mapping[str, Any]
) -> int:
    """Count of differing leaf values between two theory JSONs (symmetric)."""

    fa = dict(_flatten(a))
    fb = dict(_flatten(b))
    keys = set(fa) | set(fb)
    return sum(1 for k in keys if fa.get(k, _MISSING) != fb.get(k, _MISSING))


_MISSING = object()


def _flatten(obj: Any, prefix: str = "") -> Any:
    if isinstance(obj, dict):
        for k in obj:
            yield from _flatten(obj[k], f"{prefix}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _flatten(v, f"{prefix}/{i}")
    else:
        yield (prefix, obj)


def _round_to_dict(rl: RepairRoundLog) -> dict[str, Any]:
    return {
        "round": rl.round,
        "feedback_status": rl.feedback_status,
        "feedback_text": rl.feedback_text,
        "action": rl.action,
        "reasoning": rl.reasoning,
        "edit_applied": rl.edit_applied,
        "apply_error": rl.apply_error,
        "feedback_status_after": rl.feedback_status_after,
        "final_status_after": rl.final_status_after,
    }


def _load_theory(theory_root: Path | str, rel_path: str) -> dict[str, Any]:
    p = Path(theory_root) / rel_path
    return json.loads(p.read_text(encoding="utf-8"))
