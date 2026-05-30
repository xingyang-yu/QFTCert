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

    def to_dict(self) -> dict[str, Any]:
        return {
            "duality_profile": self.duality_profile,
            "chiral_ring_max_length": int(self.chiral_ring_max_length),
            "require_r_graded": bool(self.require_r_graded),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "VerifierConfig":
        return cls(
            duality_profile=str(data.get("duality_profile", "phase2c_a_detection")),
            chiral_ring_max_length=int(data.get("chiral_ring_max_length", 3)),
            require_r_graded=bool(data.get("require_r_graded", True)),
        )

    def bounded_chiral_ring_metadata(self) -> dict[str, Any]:
        """The `claim.metadata["bounded_chiral_ring"]` payload."""

        return {
            "max_length": int(self.chiral_ring_max_length),
            "require_r_graded": bool(self.require_r_graded),
        }

    def config_hash(self) -> str:
        return _hash_obj(self.to_dict())


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
