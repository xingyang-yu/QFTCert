"""Typed experiment configuration (Deliverable 1).

Configs are plain JSON files (the repo has no YAML dependency and
`dependencies = []` in pyproject, so we stay stdlib-only) loaded into
frozen dataclasses. Three canonical configs ship under `configs/`:

  - configs/mvp.json            — reproduces the locked depth=1 MVP
  - configs/paper_detection.json — paper-scale detection / diagnosis
  - configs/paper_repair.json    — paper-scale repair loop

Design notes:

  - `VerifierConfig.chiral_ring_max_length` is the bounded chiral-ring
    cutoff L. It is threaded into `claim.metadata["bounded_chiral_ring"]`
    by `dualitycert.experiments.verifier`. Feedback and final-eval
    verifiers can carry *different* L so the repair guardrail in
    Deliverable 7 can be expressed declaratively.
  - Provider/model live in `ModelConfig`, but nothing here requires a
    network call: the harness defaults to provider "dryrun" so configs
    are exercisable offline.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


__all__ = [
    "FIXTURE_CLASSES",
    "FEEDBACK_MODES",
    "FEEDBACK_DETAIL_LEVELS",
    "PAIR_GENERATION_MODES",
    "PAIR_ORIGINS",
    "ChainConfig",
    "EndpointPoolConfig",
    "ModelConfig",
    "VerifierConfig",
    "RepairConfig",
    "ExperimentConfig",
]


# Locked vocabulary for the paper. `trivial_rank` is an alias-flavored
# secondary of `rank_perturb` (a sanity perturbation); `wrong_pair` is
# the OOD / impossible-repair stress set. The detection MVP only needs
# the first six; repair focuses on the four repairable negatives.
FIXTURE_CLASSES: tuple[str, ...] = (
    "positive",
    "drop_w_term",
    "flip_w_sign",
    "r_charge_perturb",
    "rank_perturb",
    "trivial_rank",
    "wrong_pair",
)

FEEDBACK_MODES: tuple[str, ...] = (
    "none",
    "generic_retry",
    "llm_critic",
    "verifier_feedback",
)

FEEDBACK_DETAIL_LEVELS: tuple[str, ...] = ("coarse", "medium", "detailed")

# How candidate (electric, candidate) pairs are formed (Phase 2d-ext).
#   legacy_seed_endpoint : always (T0, T_K) — the original behavior.
#   endpoint_pool        : sample blind (T_i, T_j) from an endpoint pool.
PAIR_GENERATION_MODES: tuple[str, ...] = ("legacy_seed_endpoint", "endpoint_pool")

# pair_origin taxonomy for endpoint-pool fixtures.
PAIR_ORIGINS: tuple[str, ...] = (
    "same_orbit_endpoint_pair",
    "perturbed_endpoint_pair",
    "cross_orbit_pair",
    "size_matched_cross_pair",
    "wrong_pair",
    "positive_seed_endpoint_pair",  # legacy back-compat
)


@dataclass(frozen=True)
class ModelConfig:
    """LLM provider/model selection. Tests stay provider-free via 'dryrun'."""

    provider: str = "dryrun"
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 2048

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "max_tokens": int(self.max_tokens),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ModelConfig":
        return cls(
            provider=str(data.get("provider", "dryrun")),
            model=str(data.get("model", "claude-sonnet-4-6")),
            max_tokens=int(data.get("max_tokens", 2048)),
        )


@dataclass(frozen=True)
class VerifierConfig:
    """Verifier settings, including the bounded chiral-ring cutoff L.

    `duality_profile` is stamped onto the claim metadata so the registry
    routes the right obligation set (the MVP uses
    "phase2c_a_detection"). `chiral_ring_max_length` is L; the verifier
    caps it at 8 (design doc P6).
    """

    duality_profile: str = "phase2c_a_detection"
    chiral_ring_max_length: int = 3
    require_r_graded: bool = True
    # Bounded chiral-ring grading axis: "length" (locked word-length blocks),
    # "r_charge" (duality-invariant R-charge buckets, needed for non-chiral
    # duals whose mesons shift word-length), or "auto" (use r_charge iff the
    # candidate has gauge singlets, i.e. a diagonal-meson / non-chiral dual).
    chiral_ring_grading: str = "auto"
    # R-charge cutoff for r_charge grading (string-encoded Fraction).
    chiral_ring_max_r_charge: str = "2"
    # How the claim's R-charge is treated (judge ① vs ②a):
    #   "given"         : trust the claimed R (only consistency is checked) — the
    #                     locked default; the structural checks use it directly.
    #   "superconformal": the claim must provide the SUPERCONFORMAL R; a-max
    #                     audits it (kill before duality if wrong) and the
    #                     structural checks run on a rational-feasible proxy.
    r_charge_policy: str = "given"

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "duality_profile": self.duality_profile,
            "chiral_ring_max_length": int(self.chiral_ring_max_length),
            "require_r_graded": bool(self.require_r_graded),
            "chiral_ring_grading": str(self.chiral_ring_grading),
            "chiral_ring_max_r_charge": str(self.chiral_ring_max_r_charge),
        }
        # Only serialize when non-default so existing ("given") configs keep a
        # byte-for-byte identical dict and config_hash.
        if self.r_charge_policy != "given":
            payload["r_charge_policy"] = str(self.r_charge_policy)
        return payload

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "VerifierConfig":
        return cls(
            duality_profile=str(data.get("duality_profile", "phase2c_a_detection")),
            chiral_ring_max_length=int(data.get("chiral_ring_max_length", 3)),
            require_r_graded=bool(data.get("require_r_graded", True)),
            chiral_ring_grading=str(data.get("chiral_ring_grading", "auto")),
            chiral_ring_max_r_charge=str(data.get("chiral_ring_max_r_charge", "2")),
            r_charge_policy=str(data.get("r_charge_policy", "given")),
        )

    def bounded_chiral_ring_metadata(
        self, *, grading: str | None = None
    ) -> dict[str, Any]:
        """The `claim.metadata["bounded_chiral_ring"]` payload.

        `grading` is the resolved comparison axis ("length" / "r_charge");
        when omitted, the config's own value is used (an unresolved "auto"
        falls back to length so a theory-blind caller keeps locked behavior).
        Only "r_charge" adds the `grading` / `max_r_charge` keys, so the
        length-graded payload is byte-for-byte unchanged.
        """

        payload: dict[str, Any] = {
            "max_length": int(self.chiral_ring_max_length),
            "require_r_graded": bool(self.require_r_graded),
        }
        resolved = grading if grading is not None else self.chiral_ring_grading
        if resolved == "r_charge":
            payload["grading"] = "r_charge"
            payload["max_r_charge"] = str(self.chiral_ring_max_r_charge)
        return payload

    def config_hash(self) -> str:
        return _hash_obj(self.to_dict())


@dataclass(frozen=True)
class ChainConfig:
    """Constraints for the depth-K Seiberg mutation chain-runner (Phase 2d).

    `generated_depth` (chain length) is the number of single-node Seiberg
    steps composed — NOT a proven minimal mutation distance. Size budgets
    send oversized chains to attrition rather than truncating them.
    """

    max_chain_attempts_per_cell: int = 8
    max_attempts_per_step: int = 8
    max_gauge_nodes: int = 12
    max_fields: int = 80
    max_superpotential_terms: int = 160
    max_json_token_estimate: int = 8000
    allow_repeated_states: bool = False
    forbid_immediate_backtracking: bool = True
    verify_adjacent_steps: bool = True
    verify_seed_to_final: bool = True
    save_intermediate_theories: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_chain_attempts_per_cell": int(self.max_chain_attempts_per_cell),
            "max_attempts_per_step": int(self.max_attempts_per_step),
            "max_gauge_nodes": int(self.max_gauge_nodes),
            "max_fields": int(self.max_fields),
            "max_superpotential_terms": int(self.max_superpotential_terms),
            "max_json_token_estimate": int(self.max_json_token_estimate),
            "allow_repeated_states": bool(self.allow_repeated_states),
            "forbid_immediate_backtracking": bool(self.forbid_immediate_backtracking),
            "verify_adjacent_steps": bool(self.verify_adjacent_steps),
            "verify_seed_to_final": bool(self.verify_seed_to_final),
            "save_intermediate_theories": bool(self.save_intermediate_theories),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ChainConfig":
        d = cls()
        return cls(
            max_chain_attempts_per_cell=int(
                data.get("max_chain_attempts_per_cell", d.max_chain_attempts_per_cell)
            ),
            max_attempts_per_step=int(
                data.get("max_attempts_per_step", d.max_attempts_per_step)
            ),
            max_gauge_nodes=int(data.get("max_gauge_nodes", d.max_gauge_nodes)),
            max_fields=int(data.get("max_fields", d.max_fields)),
            max_superpotential_terms=int(
                data.get("max_superpotential_terms", d.max_superpotential_terms)
            ),
            max_json_token_estimate=int(
                data.get("max_json_token_estimate", d.max_json_token_estimate)
            ),
            allow_repeated_states=bool(
                data.get("allow_repeated_states", d.allow_repeated_states)
            ),
            forbid_immediate_backtracking=bool(
                data.get(
                    "forbid_immediate_backtracking", d.forbid_immediate_backtracking
                )
            ),
            verify_adjacent_steps=bool(
                data.get("verify_adjacent_steps", d.verify_adjacent_steps)
            ),
            verify_seed_to_final=bool(
                data.get("verify_seed_to_final", d.verify_seed_to_final)
            ),
            save_intermediate_theories=bool(
                data.get("save_intermediate_theories", d.save_intermediate_theories)
            ),
        )


@dataclass(frozen=True)
class EndpointPoolConfig:
    """Controls for endpoint-pool pair sampling (Phase 2d-ext).

    The mutation engine is treated purely as a benchmark generator: we
    build a pool of endpoint theories at depths 0..`max_pool_depth` per
    curated seed (orbit), then sample blind (T_i, T_j) pairs and
    verifier-gate them. Provenance (seed/depth/path/orbit) is recorded in
    the manifest but never shown to the model.
    """

    max_pool_depth: int = 1
    max_endpoints_per_orbit: int = 16
    max_pairs_per_theory: int = 6
    max_pairs_per_orbit: int = 40
    balance_pair_orientation: bool = True
    balance_depth_pairs: bool = True
    allow_same_theory_pair: bool = False
    allow_same_hash_pair: bool = False
    size_match_tolerance: int = 8
    n_perturbed_per_certified: int = 1
    pair_origins: tuple[str, ...] = (
        "same_orbit_endpoint_pair",
        "perturbed_endpoint_pair",
        "cross_orbit_pair",
        "size_matched_cross_pair",
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_pool_depth": int(self.max_pool_depth),
            "max_endpoints_per_orbit": int(self.max_endpoints_per_orbit),
            "max_pairs_per_theory": int(self.max_pairs_per_theory),
            "max_pairs_per_orbit": int(self.max_pairs_per_orbit),
            "balance_pair_orientation": bool(self.balance_pair_orientation),
            "balance_depth_pairs": bool(self.balance_depth_pairs),
            "allow_same_theory_pair": bool(self.allow_same_theory_pair),
            "allow_same_hash_pair": bool(self.allow_same_hash_pair),
            "size_match_tolerance": int(self.size_match_tolerance),
            "n_perturbed_per_certified": int(self.n_perturbed_per_certified),
            "pair_origins": list(self.pair_origins),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EndpointPoolConfig":
        d = cls()
        return cls(
            max_pool_depth=int(data.get("max_pool_depth", d.max_pool_depth)),
            max_endpoints_per_orbit=int(
                data.get("max_endpoints_per_orbit", d.max_endpoints_per_orbit)
            ),
            max_pairs_per_theory=int(
                data.get("max_pairs_per_theory", d.max_pairs_per_theory)
            ),
            max_pairs_per_orbit=int(
                data.get("max_pairs_per_orbit", d.max_pairs_per_orbit)
            ),
            balance_pair_orientation=bool(
                data.get("balance_pair_orientation", d.balance_pair_orientation)
            ),
            balance_depth_pairs=bool(
                data.get("balance_depth_pairs", d.balance_depth_pairs)
            ),
            allow_same_theory_pair=bool(
                data.get("allow_same_theory_pair", d.allow_same_theory_pair)
            ),
            allow_same_hash_pair=bool(
                data.get("allow_same_hash_pair", d.allow_same_hash_pair)
            ),
            size_match_tolerance=int(
                data.get("size_match_tolerance", d.size_match_tolerance)
            ),
            n_perturbed_per_certified=int(
                data.get("n_perturbed_per_certified", d.n_perturbed_per_certified)
            ),
            pair_origins=tuple(
                str(p) for p in data.get("pair_origins", d.pair_origins)
            ),
        )


@dataclass(frozen=True)
class RepairConfig:
    """Repair-loop knobs (Deliverable 6 + 7).

    `feedback_verifier` / `final_eval_verifier` may differ from the
    top-level experiment verifier — this is exactly the anti-gaming
    guardrail (a model may repair against a lenient L_feedback but is
    scored on a stricter L_eval). When either is None the experiment's
    top-level verifier is used (resolved by `ExperimentConfig`).
    """

    max_rounds: int = 5
    feedback_mode: str = "verifier_feedback"
    feedback_detail: str = "medium"
    feedback_verifier: VerifierConfig | None = None
    final_eval_verifier: VerifierConfig | None = None
    # Challenge mode (do-no-harm measurement): when True the repair loop
    # does NOT short-circuit an already-consistent candidate — the model
    # must explicitly choose no_change / abstain / edit, so harm rate and
    # unnecessary-edit rate are observable. Default False (production
    # guardrail: never touch a passing candidate).
    force_model_on_certified: bool = False

    def __post_init__(self) -> None:
        if self.feedback_mode not in FEEDBACK_MODES:
            raise ValueError(
                f"RepairConfig.feedback_mode {self.feedback_mode!r} not in "
                f"{FEEDBACK_MODES!r}"
            )
        if self.feedback_detail not in FEEDBACK_DETAIL_LEVELS:
            raise ValueError(
                f"RepairConfig.feedback_detail {self.feedback_detail!r} not in "
                f"{FEEDBACK_DETAIL_LEVELS!r}"
            )
        if self.max_rounds < 1:
            raise ValueError(
                f"RepairConfig.max_rounds must be >= 1; got {self.max_rounds}"
            )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "max_rounds": int(self.max_rounds),
            "feedback_mode": self.feedback_mode,
            "feedback_detail": self.feedback_detail,
            "force_model_on_certified": bool(self.force_model_on_certified),
        }
        if self.feedback_verifier is not None:
            out["feedback_verifier"] = self.feedback_verifier.to_dict()
        if self.final_eval_verifier is not None:
            out["final_eval_verifier"] = self.final_eval_verifier.to_dict()
        return out

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RepairConfig":
        fb = data.get("feedback_verifier")
        fe = data.get("final_eval_verifier")
        return cls(
            max_rounds=int(data.get("max_rounds", 5)),
            feedback_mode=str(data.get("feedback_mode", "verifier_feedback")),
            feedback_detail=str(data.get("feedback_detail", "medium")),
            feedback_verifier=VerifierConfig.from_dict(fb) if fb is not None else None,
            final_eval_verifier=(
                VerifierConfig.from_dict(fe) if fe is not None else None
            ),
            force_model_on_certified=bool(
                data.get("force_model_on_certified", False)
            ),
        )


@dataclass(frozen=True)
class ExperimentConfig:
    """Top-level experiment configuration.

    `depths` may request depth >= 2 even though the mutation chain runner
    only implements depth 1 today — generation routes the unimplemented
    cells to the attrition manifest (it never fabricates them). See
    `dualitycert.experiments.chains`.
    """

    name: str
    depths: tuple[int, ...] = (1, 2, 3, 4)
    fixture_classes: tuple[str, ...] = FIXTURE_CLASSES
    n_per_cell: int = 1
    seed: int = 12345
    verifier: VerifierConfig = field(default_factory=VerifierConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    repair: RepairConfig = field(default_factory=RepairConfig)
    chain: ChainConfig = field(default_factory=ChainConfig)
    endpoint_pool: EndpointPoolConfig = field(default_factory=EndpointPoolConfig)
    # "legacy_seed_endpoint" (default, original (T0,T_K)) or "endpoint_pool".
    pair_generation_mode: str = "legacy_seed_endpoint"
    output_dir: str = "runs/experiments"
    split: str = "eval"
    notes: str = ""
    # When False (default, "strict"), generation preflight-fails if any
    # requested depth exceeds the mutation engine's capability — so a
    # paper run cannot silently claim depth 1-4 coverage while only
    # producing depth=1. Set True to allow depth>=2 cells to route to
    # attrition (development / smoke mode).
    allow_incomplete_cells: bool = False

    def __post_init__(self) -> None:
        for cls_name in self.fixture_classes:
            if cls_name not in FIXTURE_CLASSES:
                raise ValueError(
                    f"ExperimentConfig.fixture_classes contains unknown class "
                    f"{cls_name!r}; allowed: {FIXTURE_CLASSES!r}"
                )
        for d in self.depths:
            if int(d) < 1:
                raise ValueError(f"depths must be >= 1; got {d!r}")
        if self.pair_generation_mode not in PAIR_GENERATION_MODES:
            raise ValueError(
                f"pair_generation_mode {self.pair_generation_mode!r} not in "
                f"{PAIR_GENERATION_MODES!r}"
            )

    # -- resolved verifier helpers (Deliverable 7) ----------------------

    def feedback_verifier(self) -> VerifierConfig:
        return self.repair.feedback_verifier or self.verifier

    def final_eval_verifier(self) -> VerifierConfig:
        return self.repair.final_eval_verifier or self.verifier

    # -- serialization --------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "depths": [int(d) for d in self.depths],
            "fixture_classes": list(self.fixture_classes),
            "n_per_cell": int(self.n_per_cell),
            "seed": int(self.seed),
            "verifier": self.verifier.to_dict(),
            "model": self.model.to_dict(),
            "repair": self.repair.to_dict(),
            "chain": self.chain.to_dict(),
            "endpoint_pool": self.endpoint_pool.to_dict(),
            "pair_generation_mode": self.pair_generation_mode,
            "output_dir": self.output_dir,
            "split": self.split,
            "notes": self.notes,
            "allow_incomplete_cells": bool(self.allow_incomplete_cells),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ExperimentConfig":
        return cls(
            name=str(data["name"]),
            depths=tuple(int(d) for d in data.get("depths", (1, 2, 3, 4))),
            fixture_classes=tuple(
                str(c) for c in data.get("fixture_classes", FIXTURE_CLASSES)
            ),
            n_per_cell=int(data.get("n_per_cell", 1)),
            seed=int(data.get("seed", 12345)),
            verifier=VerifierConfig.from_dict(data.get("verifier", {})),
            model=ModelConfig.from_dict(data.get("model", {})),
            repair=RepairConfig.from_dict(data.get("repair", {})),
            chain=ChainConfig.from_dict(data.get("chain", {})),
            endpoint_pool=EndpointPoolConfig.from_dict(data.get("endpoint_pool", {})),
            pair_generation_mode=str(
                data.get("pair_generation_mode", "legacy_seed_endpoint")
            ),
            output_dir=str(data.get("output_dir", "runs/experiments")),
            split=str(data.get("split", "eval")),
            notes=str(data.get("notes", "")),
            allow_incomplete_cells=bool(data.get("allow_incomplete_cells", False)),
        )

    @classmethod
    def from_json_file(cls, path: Path | str) -> "ExperimentConfig":
        text = Path(path).read_text(encoding="utf-8")
        return cls.from_dict(json.loads(text))

    def to_json_file(self, path: Path | str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def config_hash(self) -> str:
        return _hash_obj(self.to_dict())


def _hash_obj(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
