"""Verifier wrapper with an explicit chiral-ring cutoff knob (Deliverable 7).

This is the single place the experiment harness talks to the verifier.
It does three jobs the raw `evaluate_claim` does not:

  1. Threads a `VerifierConfig` (duality profile + bounded chiral-ring
     cutoff L) into `claim.metadata` so feedback and final-evaluation
     verifiers can use *different* L (the anti-gaming guardrail).
  2. Maps each failed obligation's name onto a coarse failure-mode
     category (anomaly / superpotential / r_charge / chiral_ring /
     rank / unknown) for diagnosis scoring.
  3. Collapses the verifier's status vocabulary into the gating verdict
     the harness cares about: in-scope (CERTIFIED / FAILED) vs.
     everything else (UNKNOWN / NOT_APPLICABLE / NOT_IMPLEMENTED /
     malformed) which routes to attrition.

The model never supplies verifier settings: the only inputs are the two
theory JSONs and a `VerifierConfig` chosen by the experiment config.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from dualitycert.core.objects import DualityClaim
from dualitycert.experiments.config import VerifierConfig
from dualitycert.qft.dualities import evaluate_claim
from dualitycert.qft.pure_quiver_json import (
    PureQuiverJSONError,
    pure_quiver_from_json,
)


__all__ = [
    "FAILURE_MODE_CATEGORIES",
    "OBLIGATION_CATEGORY_MAP",
    "VerifierOutcome",
    "categorize_obligation",
    "run_verifier",
]


# The closed set of diagnosis labels (also the model's `failure_modes`
# enum in `dualitycert.agent.diagnosis`).
FAILURE_MODE_CATEGORIES: tuple[str, ...] = (
    "anomaly",
    "superpotential",
    "r_charge",
    "chiral_ring",
    "rank",
    "unknown",
)


# Concrete obligation `name` strings observed in the committed fixtures,
# mapped to failure-mode categories. Substring fallbacks in
# `categorize_obligation` catch name drift, but exact entries are kept so
# intent is auditable. (There is no standalone "rank" obligation: rank
# perturbations surface through the anomaly obligations.)
OBLIGATION_CATEGORY_MAP: dict[str, str] = {
    "global anomaly matching": "anomaly",
    "magnetic gauge-global mixed anomaly cancellation": "anomaly",
    "magnetic gauge anomaly cancellation": "anomaly",
    "electric gauge anomaly cancellation": "anomaly",
    "magnetic superpotential consistency": "superpotential",
    "superpotential R-charge balance": "superpotential",
    "central charge matching from encoded R-symmetry": "r_charge",
    "a-maximization central charge matching": "r_charge",
    "superconformal R-charge audit": "r_charge",
    "R-charge balance": "r_charge",
    "bounded chiral-ring consistency": "chiral_ring",
}


def _is_gauge_singlet_field(field: Any) -> bool:
    """True if a Field carries no nontrivial gauge charge (a pure singlet)."""

    return all(rep.name == "singlet" for rep in field.gauge_reps.values())


def categorize_obligation(name: str) -> str:
    """Map an obligation name onto a failure-mode category.

    Exact map first, then substring heuristics for forward-compat with
    obligation renames, then "unknown".
    """

    if name in OBLIGATION_CATEGORY_MAP:
        return OBLIGATION_CATEGORY_MAP[name]
    low = name.lower()
    if "chiral" in low and "ring" in low:
        return "chiral_ring"
    if "anomaly" in low:
        return "anomaly"
    if "superpotential" in low:
        return "superpotential"
    if "r-charge" in low or "r_charge" in low or "r-symmetry" in low or "central charge" in low:
        return "r_charge"
    if "rank" in low:
        return "rank"
    return "unknown"


@dataclass(frozen=True)
class VerifierOutcome:
    """Result of running the verifier on one (electric, candidate) pair."""

    status: str  # CERTIFIED | FAILED | UNKNOWN | NOT_APPLICABLE | NOT_IMPLEMENTED | ERROR
    failed_obligations: tuple[dict[str, Any], ...] = ()
    error: str | None = None

    @property
    def in_scope(self) -> bool:
        """True iff the verdict is an unambiguous CERTIFIED / FAILED."""

        return self.status in {"CERTIFIED", "FAILED"}

    @property
    def is_certified(self) -> bool:
        return self.status == "CERTIFIED"

    @property
    def is_failed(self) -> bool:
        return self.status == "FAILED"

    @property
    def failed_obligation_names(self) -> tuple[str, ...]:
        return tuple(str(o["name"]) for o in self.failed_obligations)

    @property
    def failed_categories(self) -> tuple[str, ...]:
        """Sorted unique failure-mode categories of the failed obligations."""

        return tuple(sorted({str(o["category"]) for o in self.failed_obligations}))

    def attrition_reason(self) -> str:
        """Map an out-of-scope status onto an attrition reason string."""

        if self.status == "ERROR":
            return "verifier_error"
        if self.status == "NOT_APPLICABLE":
            return "NOT_APPLICABLE"
        if self.status == "NOT_IMPLEMENTED":
            return "OUT_OF_SCOPE"
        return "UNKNOWN"


def run_verifier(
    electric_json: Mapping[str, Any],
    candidate_json: Mapping[str, Any],
    config: VerifierConfig,
    *,
    claim_name: str = "experiment pair",
) -> VerifierOutcome:
    """Run the verifier on a JSON (electric, candidate) pair under `config`.

    Malformed JSON (e.g. a wrong-pair that violates the pure-quiver label
    convention) is caught and returned as status "ERROR" so callers route
    to attrition rather than crash.
    """

    try:
        electric_theory = pure_quiver_from_json(dict(electric_json))
        candidate_theory = pure_quiver_from_json(dict(candidate_json))
    except (PureQuiverJSONError, ValueError) as exc:
        return VerifierOutcome(status="ERROR", error=str(exc))

    # Resolve the chiral-ring grading policy. Under "auto", a candidate with
    # gauge singlets is a non-chiral (diagonal-meson) dual whose mesons shift
    # word-length, so length grading is invalid → use the duality-invariant
    # R-charge grading. Chiral duals (no singlets) keep the finer length mode.
    grading = config.chiral_ring_grading
    if grading == "auto":
        has_singlets = any(
            _is_gauge_singlet_field(f)
            for f in (*electric_theory.fields, *candidate_theory.fields)
        )
        grading = "r_charge" if has_singlets else "length"

    metadata: dict[str, Any] = {
        "duality_profile": config.duality_profile,
        "bounded_chiral_ring": config.bounded_chiral_ring_metadata(grading=grading),
    }
    # Judge ②a: enable the a-max superconformal R-charge gate. The claim must
    # then carry the superconformal R; the audit kills a wrong-R claim before
    # the duality comparison. Default policy ("given") leaves this off.
    if config.r_charge_policy == "superconformal":
        metadata["run_superconformal_audit"] = True

    claim = DualityClaim(
        name=claim_name,
        electric_theory=electric_theory,
        magnetic_theory=candidate_theory,
        metadata=metadata,
    )
    try:
        cert = evaluate_claim(claim)
    except Exception as exc:  # verifier raised — treat as attrition, not crash
        return VerifierOutcome(status="ERROR", error=f"{type(exc).__name__}: {exc}")

    failed = tuple(
        {"name": r.name, "category": categorize_obligation(r.name)}
        for r in cert.failed_obligations
    )
    return VerifierOutcome(status=cert.overall_status.value, failed_obligations=failed)
