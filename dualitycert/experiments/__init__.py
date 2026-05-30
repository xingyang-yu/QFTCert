"""Paper-scale experiment harness for QFTCert (Phase 2c paper push).

This package sits on top of the locked Phase 2c-a detection MVP
(`dualitycert.benchmark`) and the verifier core (`dualitycert.qft`)
without modifying either. It adds the reproducible experiment
framework described in the paper plan:

  - config      : typed experiment configs + JSON serialization (D1)
  - manifest    : canonical fixture-record schema, JSONL + CSV (D2)
  - verifier    : thin verifier wrapper + obligation->category map,
                  with an explicit bounded-chiral-ring cutoff knob (D7)
  - perturbations: registry over the six MVP operators (D4)
  - chains      : generate_mutation_chain interface (depth=1 wired; D3)
  - generation  : verifier-gated depth x class fixture generation (D3)
  - single_shot : detection + diagnosis runner (Layer A/B) (D5)
  - repair      : verifier-in-the-loop repair runner (Layer C) (D6)
  - scoring     : detection / diagnosis / repair scoring (D5/D6)
  - stats       : Wilson CIs + tidy per-cell CSV export (D8)

Nothing here is imported by the MVP modules; the dependency direction
is strictly experiments -> {benchmark, agent, qft, core}.
"""

from __future__ import annotations

from dualitycert.experiments.config import (
    ExperimentConfig,
    ModelConfig,
    RepairConfig,
    VerifierConfig,
)
from dualitycert.experiments.manifest import (
    ATTRITION_REASONS,
    AttritionRecord,
    ManifestRecord,
    SizeCovariates,
    read_attrition_jsonl,
    read_manifest_jsonl,
    write_attrition_jsonl,
    write_manifest_csv,
    write_manifest_jsonl,
)

__all__ = [
    "ATTRITION_REASONS",
    "AttritionRecord",
    "ExperimentConfig",
    "ManifestRecord",
    "ModelConfig",
    "RepairConfig",
    "SizeCovariates",
    "VerifierConfig",
    "read_attrition_jsonl",
    "read_manifest_jsonl",
    "write_attrition_jsonl",
    "write_manifest_csv",
    "write_manifest_jsonl",
]
