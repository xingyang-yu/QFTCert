"""Per-class fixture builders for the Phase 2c-a detection benchmark.

Six attempt-functions, one per fixture class, all sharing a single
verifier-gate (`gate_and_build_fixture` -> Rule 6 ambiguous-ground-truth
discard). Each function is a single attempt — the script driver wires
retries on top by iterating over seeds.

  - `attempt_positive`         : mutate_bare + integrate + repair at `node`
  - `attempt_w_drop`           : Type-4 W term dropped
  - `attempt_w_sign_swap`      : Type-4 W coefficient sign flipped
  - `attempt_r_naive`          : Type-3 single-field R perturb (no kernel)
  - `attempt_rank_perturb`     : Type-1/2 trivial rank flip
  - `attempt_wrong_pair`       : pair (electric_A, candidate_B) across seeds

All attempts return ``(Fixture | None, GenerationLogEntry)``. The log
entry is always populated so the generation log captures every attempt
(accepted + discarded) per Rule 10.

See `docs/phase2c_a_detection_plan.md` Rules 6 / 8 / 9 / 10 for the
locked semantics.
"""

from __future__ import annotations

import random
from copy import deepcopy
from fractions import Fraction
from typing import Any, Mapping

from dualitycert.benchmark.fixtures import (
    Fixture,
    FixtureMetadata,
    GenerationLogEntry,
)
from dualitycert.core.objects import DualityClaim
from dualitycert.qft.dualities import evaluate_claim
from dualitycert.qft.mutation_engine import (
    MutationEngineError,
    integrate_linear_fields,
    mutate_bare,
)
from dualitycert.qft.pure_quiver_json import (
    PureQuiverJSONError,
    pure_quiver_from_json,
)
from dualitycert.qft.r_repair import RRepairError, repair_r_charges


__all__ = [
    "DETECTION_DUALITY_PROFILE",
    "PROMPT_VISIBLE_FIELDS",
    "attempt_positive",
    "attempt_r_naive",
    "attempt_rank_perturb",
    "attempt_w_drop",
    "attempt_w_sign_swap",
    "attempt_wrong_pair",
    "evaluate_pair_ground_truth",
    "gate_and_build_fixture",
]


# Stamped onto every detection claim's metadata so the verifier registry
# can route checks consistently. None of the seiberg_sqcd-gated checks
# match this profile, so only pure-quiver / always-run obligations run —
# which is exactly the scope the benchmark targets.
DETECTION_DUALITY_PROFILE = "phase2c_a_detection"

PROMPT_VISIBLE_FIELDS: tuple[str, ...] = ("electric", "candidate")


# ----------------------------------------------------------------------
# Verifier ground truth + Rule-6 gate.
# ----------------------------------------------------------------------


def evaluate_pair_ground_truth(
    electric_json: Mapping[str, Any],
    candidate_json: Mapping[str, Any],
    *,
    claim_name: str = "phase2c_a detection pair",
) -> tuple[str, list[str]]:
    """Run `evaluate_claim` on a JSON (electric, candidate) pair.

    Returns ``(overall_status_value, failed_obligation_names)``. If
    either JSON is malformed at the builder level (e.g. wrong-pair
    breaks the pure-quiver label convention), returns
    ``("ERROR", [exception_message])`` so the caller can discard the
    attempt instead of crashing.
    """

    try:
        electric_theory = pure_quiver_from_json(dict(electric_json))
        candidate_theory = pure_quiver_from_json(dict(candidate_json))
    except (PureQuiverJSONError, ValueError) as exc:
        return ("ERROR", [str(exc)])

    claim = DualityClaim(
        name=claim_name,
        electric_theory=electric_theory,
        magnetic_theory=candidate_theory,
        metadata={
            "duality_profile": DETECTION_DUALITY_PROFILE,
            "bounded_chiral_ring": {"max_length": 3, "require_r_graded": True},
        },
    )
    cert = evaluate_claim(claim)
    return (
        cert.overall_status.value,
        [r.name for r in cert.failed_obligations],
    )


def gate_and_build_fixture(
    *,
    electric_json: Mapping[str, Any],
    candidate_json: Mapping[str, Any],
    fixture_id: str,
    metadata: FixtureMetadata,
) -> tuple[Fixture | None, GenerationLogEntry]:
    """Apply Rule 6 gating; package an accepted fixture or a discard log.

    Only ``CERTIFIED`` (-> label "dual") and ``FAILED`` (-> label
    "not_dual") are accepted. Every other status (``NOT_APPLICABLE``,
    ``UNKNOWN``, ``NOT_IMPLEMENTED``, the synthetic ``"ERROR"`` from
    malformed JSON) is discarded with a structured reason so the
    generation log can be audited.
    """

    overall, failed = evaluate_pair_ground_truth(electric_json, candidate_json)

    if overall == "CERTIFIED":
        gt = {"overall_status": "CERTIFIED", "failed_obligations": []}
        return _accepted(
            fixture_id=fixture_id,
            label="dual",
            verifier_ground_truth=gt,
            electric_json=electric_json,
            candidate_json=candidate_json,
            metadata=metadata,
        )

    if overall == "FAILED":
        gt = {"overall_status": "FAILED", "failed_obligations": list(failed)}
        return _accepted(
            fixture_id=fixture_id,
            label="not_dual",
            verifier_ground_truth=gt,
            electric_json=electric_json,
            candidate_json=candidate_json,
            metadata=metadata,
        )

    reason = f"ambiguous_ground_truth(overall={overall}"
    if failed:
        reason += f"; details={failed[0]!r}"
    reason += ")"
    return None, GenerationLogEntry(
        fixture_id=fixture_id,
        generation_status="discarded",
        discard_reason=reason,
        prompt_visible_fields=(),
        verifier_ground_truth=None,
        metadata=metadata,
    )


def _accepted(
    *,
    fixture_id: str,
    label: str,
    verifier_ground_truth: dict,
    electric_json: Mapping[str, Any],
    candidate_json: Mapping[str, Any],
    metadata: FixtureMetadata,
) -> tuple[Fixture, GenerationLogEntry]:
    fixture = Fixture(
        fixture_id=fixture_id,
        ground_truth_label=label,
        verifier_ground_truth=dict(verifier_ground_truth),
        electric=deepcopy(dict(electric_json)),
        candidate=deepcopy(dict(candidate_json)),
        metadata=metadata,
    )
    log = GenerationLogEntry(
        fixture_id=fixture_id,
        generation_status="accepted",
        discard_reason=None,
        prompt_visible_fields=PROMPT_VISIBLE_FIELDS,
        verifier_ground_truth=dict(verifier_ground_truth),
        metadata=metadata,
    )
    return fixture, log


def _discard(
    *,
    fixture_id: str,
    reason: str,
    metadata: FixtureMetadata,
) -> tuple[None, GenerationLogEntry]:
    return None, GenerationLogEntry(
        fixture_id=fixture_id,
        generation_status="discarded",
        discard_reason=reason,
        prompt_visible_fields=(),
        verifier_ground_truth=None,
        metadata=metadata,
    )


# ----------------------------------------------------------------------
# Positive (Rule 8): mutate_bare + integrate + repair at `node`.
# ----------------------------------------------------------------------


def attempt_positive(
    *,
    electric_json: Mapping[str, Any],
    node: int,
    source_name: str,
    N: int,
    fixture_id: str,
    seed: int,
) -> tuple[Fixture | None, GenerationLogEntry]:
    """One positive attempt: Seiberg-mutate at `node`, integrate, R-repair, gate.

    `seed` is stored for traceability; positive generation is otherwise
    deterministic given (electric_json, node).
    """

    metadata = FixtureMetadata(
        source=source_name,
        seed=seed,
        perturbation_type="none",
        extra={"mutation_node": int(node), "mutation_depth": 1, "N": int(N)},
    )

    try:
        bare = mutate_bare(dict(electric_json), node=node)
        integrated = integrate_linear_fields(bare)
        repaired = repair_r_charges(integrated)
    except MutationEngineError as exc:
        return _discard(
            fixture_id=fixture_id,
            reason=f"mutation_engine_error: {exc}",
            metadata=metadata,
        )
    except RRepairError as exc:
        return _discard(
            fixture_id=fixture_id,
            reason=f"r_repair_error: {exc}",
            metadata=metadata,
        )

    if repaired["status"] == "infeasible":
        return _discard(
            fixture_id=fixture_id,
            reason=f"r_repair_infeasible: {repaired['failure_reason']}",
            metadata=metadata,
        )

    candidate_json = repaired["representative"]
    return gate_and_build_fixture(
        electric_json=electric_json,
        candidate_json=candidate_json,
        fixture_id=fixture_id,
        metadata=metadata,
    )


# ----------------------------------------------------------------------
# Type-4 W drop.
# ----------------------------------------------------------------------


def attempt_w_drop(
    *,
    positive: Fixture,
    fixture_id: str,
    seed: int,
) -> tuple[Fixture | None, GenerationLogEntry]:
    """Drop a random W term from the positive's candidate."""

    rng = random.Random(seed)
    candidate = deepcopy(positive.candidate)
    W = candidate["superpotential"]

    base_extra = {"source_fixture_id": positive.fixture_id}

    if not W:
        return _discard(
            fixture_id=fixture_id,
            reason="cannot_drop_W: candidate has no W terms",
            metadata=FixtureMetadata(
                source=positive.metadata.source,
                seed=seed,
                perturbation_type="w_drop",
                extra=base_extra,
            ),
        )

    idx = rng.randrange(len(W))
    dropped = W.pop(idx)
    candidate["superpotential"] = W

    metadata = FixtureMetadata(
        source=positive.metadata.source,
        seed=seed,
        perturbation_type="w_drop",
        extra={
            **base_extra,
            "dropped_term": list(dropped["factors"]),
            "dropped_coefficient": str(dropped["coefficient"]),
            "dropped_index": idx,
        },
    )

    return gate_and_build_fixture(
        electric_json=positive.electric,
        candidate_json=candidate,
        fixture_id=fixture_id,
        metadata=metadata,
    )


# ----------------------------------------------------------------------
# Type-4 W sign swap.
# ----------------------------------------------------------------------


def attempt_w_sign_swap(
    *,
    positive: Fixture,
    fixture_id: str,
    seed: int,
) -> tuple[Fixture | None, GenerationLogEntry]:
    """Flip the sign of a random W term's coefficient."""

    rng = random.Random(seed)
    candidate = deepcopy(positive.candidate)
    W = candidate["superpotential"]

    base_extra = {"source_fixture_id": positive.fixture_id}

    if not W:
        return _discard(
            fixture_id=fixture_id,
            reason="cannot_sign_swap: candidate has no W terms",
            metadata=FixtureMetadata(
                source=positive.metadata.source,
                seed=seed,
                perturbation_type="w_sign_swap",
                extra=base_extra,
            ),
        )

    idx = rng.randrange(len(W))
    term = W[idx]
    old_coeff = Fraction(term["coefficient"])
    new_coeff = -old_coeff
    term["coefficient"] = str(new_coeff)

    metadata = FixtureMetadata(
        source=positive.metadata.source,
        seed=seed,
        perturbation_type="w_sign_swap",
        extra={
            **base_extra,
            "flipped_term": list(term["factors"]),
            "old_coefficient": str(old_coeff),
            "new_coefficient": str(new_coeff),
            "flipped_index": idx,
        },
    )

    return gate_and_build_fixture(
        electric_json=positive.electric,
        candidate_json=candidate,
        fixture_id=fixture_id,
        metadata=metadata,
    )


# ----------------------------------------------------------------------
# Type-3 R naive.
# ----------------------------------------------------------------------


_R_NAIVE_DELTAS: tuple[Fraction, ...] = (Fraction(1, 3), Fraction(-1, 3))


def attempt_r_naive(
    *,
    positive: Fixture,
    fixture_id: str,
    seed: int,
    delta_choices: tuple[Fraction, ...] = _R_NAIVE_DELTAS,
) -> tuple[Fixture | None, GenerationLogEntry]:
    """Perturb one random arrow's R-charge by ±1/3 (no W kernel projection)."""

    rng = random.Random(seed)
    candidate = deepcopy(positive.candidate)
    arrows = candidate["arrows"]

    base_extra = {"source_fixture_id": positive.fixture_id}

    if not arrows:
        return _discard(
            fixture_id=fixture_id,
            reason="cannot_r_naive: candidate has no arrows",
            metadata=FixtureMetadata(
                source=positive.metadata.source,
                seed=seed,
                perturbation_type="r_naive",
                extra=base_extra,
            ),
        )

    idx = rng.randrange(len(arrows))
    arrow = arrows[idx]
    old_r = Fraction(arrow["r_charge"])
    delta = rng.choice(delta_choices)
    new_r = old_r + delta
    arrow["r_charge"] = str(new_r)

    metadata = FixtureMetadata(
        source=positive.metadata.source,
        seed=seed,
        perturbation_type="r_naive",
        extra={
            **base_extra,
            "perturbed_field": arrow["label"],
            "delta": str(delta),
            "old_r": str(old_r),
            "new_r": str(new_r),
        },
    )

    return gate_and_build_fixture(
        electric_json=positive.electric,
        candidate_json=candidate,
        fixture_id=fixture_id,
        metadata=metadata,
    )


# ----------------------------------------------------------------------
# Type-1/2 trivial: rank perturbation.
# ----------------------------------------------------------------------


def attempt_rank_perturb(
    *,
    positive: Fixture,
    fixture_id: str,
    seed: int,
) -> tuple[Fixture | None, GenerationLogEntry]:
    """Add ±1 to one gauge node's rank.

    SU(N≥2) is required by downstream builders, so an N=2 node with a
    proposed delta=-1 is bumped to delta=+1.
    """

    rng = random.Random(seed)
    candidate = deepcopy(positive.candidate)
    ranks = candidate["ranks"]

    base_extra = {"source_fixture_id": positive.fixture_id}

    if not ranks:
        return _discard(
            fixture_id=fixture_id,
            reason="cannot_rank_perturb: candidate has no gauge nodes",
            metadata=FixtureMetadata(
                source=positive.metadata.source,
                seed=seed,
                perturbation_type="rank_perturb",
                extra=base_extra,
            ),
        )

    idx = rng.randrange(len(ranks))
    delta = rng.choice([1, -1])
    if ranks[idx] + delta < 2:
        delta = 1
    old_rank = int(ranks[idx])
    new_rank = old_rank + delta
    ranks[idx] = new_rank

    metadata = FixtureMetadata(
        source=positive.metadata.source,
        seed=seed,
        perturbation_type="rank_perturb",
        extra={
            **base_extra,
            "node_index": idx,
            "old_rank": old_rank,
            "new_rank": new_rank,
            "delta": delta,
        },
    )

    return gate_and_build_fixture(
        electric_json=positive.electric,
        candidate_json=candidate,
        fixture_id=fixture_id,
        metadata=metadata,
    )


# ----------------------------------------------------------------------
# Wrong-pair: mix electric from one positive with candidate from another.
# ----------------------------------------------------------------------


def attempt_wrong_pair(
    *,
    electric_from: Fixture,
    candidate_from: Fixture,
    fixture_id: str,
    seed: int,
) -> tuple[Fixture | None, GenerationLogEntry]:
    """Pair an unrelated electric and candidate from two different positives."""

    metadata = FixtureMetadata(
        source=(
            f"{electric_from.metadata.source}_x_{candidate_from.metadata.source}"
        ),
        seed=seed,
        perturbation_type="wrong_pair",
        extra={
            "source_electric_id": electric_from.fixture_id,
            "source_candidate_id": candidate_from.fixture_id,
        },
    )

    return gate_and_build_fixture(
        electric_json=electric_from.electric,
        candidate_json=candidate_from.candidate,
        fixture_id=fixture_id,
        metadata=metadata,
    )
