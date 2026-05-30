"""Standardized perturbation operators (Deliverable 4).

Each operator is the *pure edit* only — it takes a candidate theory JSON
plus a seeded `random.Random` and returns `(edited_candidate, metadata)`
recording exactly what changed. Verifier gating is intentionally NOT
bundled in (unlike `dualitycert.benchmark.generators`, which gates at the
locked MVP cutoff): `dualitycert.experiments.generation` gates afterward
with whatever `VerifierConfig` the experiment chose, so an experiment can
generate at any chiral-ring cutoff L without re-touching these edits.

These edits mirror the six MVP operators in
`dualitycert.benchmark.generators` (drop / sign-swap / r-perturb /
rank-perturb / wrong-pair), kept thin so they stay faithful.

Class vocabulary (Deliverable 1 `FIXTURE_CLASSES`):

  - positive          : no edit; the true Seiberg-mutated dual
  - drop_w_term       : remove one superpotential term
  - flip_w_sign       : flip the sign of one W coefficient
  - r_charge_perturb  : add +/- 1/3 to one arrow's R-charge
  - rank_perturb      : add +/- 1 to one gauge node rank
  - trivial_rank      : alias of rank_perturb (secondary sanity set)
  - wrong_pair        : pair unrelated electric / candidate (handled in
                        generation, needs two theories)
"""

from __future__ import annotations

import random
from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Mapping


__all__ = [
    "PERTURBATION_REGISTRY",
    "PerturbationError",
    "PerturbationSpec",
    "REPAIRABLE_CLASSES",
    "SINGLE_POSITIVE_CLASSES",
    "apply_single_positive_edit",
]


class PerturbationError(ValueError):
    """The operator cannot apply to this candidate (e.g. empty W).

    Generation routes this to attrition with reason ``generator_discard``.
    """


@dataclass(frozen=True)
class PerturbationSpec:
    """Static description of one perturbation class."""

    name: str  # task vocabulary, also the stored `perturbation_class`
    benchmark_ptype: str  # the MVP `perturbation_type` analogue
    expected_label: str  # "CERTIFIED" | "FAILED"
    repairable: bool
    arity: str  # "none" | "single" | "pair"


PERTURBATION_REGISTRY: dict[str, PerturbationSpec] = {
    "positive": PerturbationSpec(
        "positive", "none", "CERTIFIED", repairable=False, arity="none"
    ),
    "drop_w_term": PerturbationSpec(
        "drop_w_term", "w_drop", "FAILED", repairable=True, arity="single"
    ),
    "flip_w_sign": PerturbationSpec(
        "flip_w_sign", "w_sign_swap", "FAILED", repairable=True, arity="single"
    ),
    "r_charge_perturb": PerturbationSpec(
        "r_charge_perturb", "r_naive", "FAILED", repairable=True, arity="single"
    ),
    "rank_perturb": PerturbationSpec(
        "rank_perturb", "rank_perturb", "FAILED", repairable=True, arity="single"
    ),
    "trivial_rank": PerturbationSpec(
        "trivial_rank", "rank_perturb", "FAILED", repairable=True, arity="single"
    ),
    "wrong_pair": PerturbationSpec(
        "wrong_pair", "wrong_pair", "FAILED", repairable=False, arity="pair"
    ),
}

# The repairable negative classes (the main repair dataset; Deliverable 6).
REPAIRABLE_CLASSES: tuple[str, ...] = tuple(
    name for name, spec in PERTURBATION_REGISTRY.items() if spec.repairable
)

# Classes whose edit acts on a single positive candidate.
SINGLE_POSITIVE_CLASSES: tuple[str, ...] = tuple(
    name for name, spec in PERTURBATION_REGISTRY.items() if spec.arity == "single"
)

_R_NAIVE_DELTAS: tuple[Fraction, ...] = (Fraction(1, 3), Fraction(-1, 3))


def apply_single_positive_edit(
    class_name: str,
    candidate_json: Mapping[str, Any],
    rng: random.Random,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply the named single-positive edit; return (edited_candidate, metadata).

    The input is never mutated. Raises `PerturbationError` if the edit
    cannot apply (empty W / no arrows / no ranks), or `KeyError`-style
    `ValueError` for an unknown class.
    """

    if class_name in {"rank_perturb", "trivial_rank"}:
        return _edit_rank(candidate_json, rng)
    if class_name == "drop_w_term":
        return _edit_drop_w(candidate_json, rng)
    if class_name == "flip_w_sign":
        return _edit_flip_w_sign(candidate_json, rng)
    if class_name == "r_charge_perturb":
        return _edit_r_charge(candidate_json, rng)
    raise ValueError(
        f"apply_single_positive_edit: {class_name!r} is not a single-positive "
        f"class; expected one of {SINGLE_POSITIVE_CLASSES!r}"
    )


def _edit_drop_w(
    candidate_json: Mapping[str, Any], rng: random.Random
) -> tuple[dict[str, Any], dict[str, Any]]:
    cand = deepcopy(dict(candidate_json))
    W = cand["superpotential"]
    if not W:
        raise PerturbationError("cannot_drop_W: candidate has no W terms")
    idx = rng.randrange(len(W))
    dropped = W.pop(idx)
    cand["superpotential"] = W
    meta = {
        "dropped_term": list(dropped["factors"]),
        "dropped_coefficient": str(dropped["coefficient"]),
        "dropped_index": idx,
    }
    return cand, meta


def _edit_flip_w_sign(
    candidate_json: Mapping[str, Any], rng: random.Random
) -> tuple[dict[str, Any], dict[str, Any]]:
    cand = deepcopy(dict(candidate_json))
    W = cand["superpotential"]
    if not W:
        raise PerturbationError("cannot_sign_swap: candidate has no W terms")
    idx = rng.randrange(len(W))
    term = W[idx]
    old_coeff = Fraction(term["coefficient"])
    new_coeff = -old_coeff
    term["coefficient"] = str(new_coeff)
    meta = {
        "flipped_term": list(term["factors"]),
        "old_coefficient": str(old_coeff),
        "new_coefficient": str(new_coeff),
        "flipped_index": idx,
    }
    return cand, meta


def _edit_r_charge(
    candidate_json: Mapping[str, Any], rng: random.Random
) -> tuple[dict[str, Any], dict[str, Any]]:
    cand = deepcopy(dict(candidate_json))
    arrows = cand["arrows"]
    if not arrows:
        raise PerturbationError("cannot_r_perturb: candidate has no arrows")
    idx = rng.randrange(len(arrows))
    arrow = arrows[idx]
    old_r = Fraction(arrow["r_charge"])
    delta = rng.choice(_R_NAIVE_DELTAS)
    new_r = old_r + delta
    arrow["r_charge"] = str(new_r)
    meta = {
        "perturbed_field": arrow["label"],
        "delta": str(delta),
        "old_r": str(old_r),
        "new_r": str(new_r),
    }
    return cand, meta


def _edit_rank(
    candidate_json: Mapping[str, Any], rng: random.Random
) -> tuple[dict[str, Any], dict[str, Any]]:
    cand = deepcopy(dict(candidate_json))
    ranks = cand["ranks"]
    if not ranks:
        raise PerturbationError("cannot_rank_perturb: candidate has no gauge nodes")
    idx = rng.randrange(len(ranks))
    delta = rng.choice([1, -1])
    if ranks[idx] + delta < 2:  # SU(N>=2) floor required by the builder
        delta = 1
    old_rank = int(ranks[idx])
    new_rank = old_rank + delta
    ranks[idx] = new_rank
    meta = {
        "node_index": idx,
        "old_rank": old_rank,
        "new_rank": new_rank,
        "delta": delta,
    }
    return cand, meta
