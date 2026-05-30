"""Canonical fixture manifest schema (Deliverable 2).

Every generated or evaluated fixture is described by one
`ManifestRecord`. Records that the verifier could not adjudicate
cleanly (anything other than CERTIFIED / FAILED), duplicates, or cells
the mutation engine cannot yet build (depth >= 2) are recorded as
`AttritionRecord`s in a separate attrition manifest — they never enter
the main evaluation manifest.

Both manifests serialize as JSONL (preferred — nested
`failed_obligations`) and the main manifest also exports a flat CSV for
spreadsheet / R import.

Theory JSON is stored to files (under `<out>/theories/`) and referenced
by `theory_a_path` / `theory_b_path` so a manifest line stays small and
diff-readable; the single-shot and repair runners resolve those paths
relative to the manifest file.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping


__all__ = [
    "ATTRITION_REASONS",
    "AttritionRecord",
    "ManifestRecord",
    "SizeCovariates",
    "compute_size_covariates",
    "manifest_record_from_dict",
    "manifest_record_to_dict",
    "read_attrition_jsonl",
    "read_manifest_jsonl",
    "write_attrition_jsonl",
    "write_manifest_csv",
    "write_manifest_jsonl",
]


# Why fixtures get excluded from the main eval manifest. The first six
# are the deliverable-specified vocabulary; the last three are concrete
# operational reasons this harness emits (documented in docs/experiments.md).
ATTRITION_REASONS: tuple[str, ...] = (
    "UNKNOWN",
    "NOT_APPLICABLE",
    "OUT_OF_SCOPE",
    "verifier_error",
    "duplicate",
    "schema_invalid",
    "depth_not_implemented",  # mutation chain runner cannot build depth>=2 yet
    "unexpected_label",  # verifier verdict disagreed with the class's expectation
    "generator_discard",  # operator could not apply (e.g. empty W)
)


# ----------------------------------------------------------------------
# Size covariates.
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class SizeCovariates:
    """Difficulty covariates for one fixture (for mixed-effects modeling).

    Computed over the candidate (Theory B) — the object being judged —
    except `input_token_estimate`, a coarse whole-prompt proxy summed
    over both theories (~4 chars/token).
    """

    n_gauge_nodes: int
    n_fields: int
    n_superpotential_terms: int
    max_superpotential_monomial_length: int
    n_r_charge_bearing_fields: int
    input_token_estimate: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_gauge_nodes": int(self.n_gauge_nodes),
            "n_fields": int(self.n_fields),
            "n_superpotential_terms": int(self.n_superpotential_terms),
            "max_superpotential_monomial_length": int(
                self.max_superpotential_monomial_length
            ),
            "n_r_charge_bearing_fields": int(self.n_r_charge_bearing_fields),
            "input_token_estimate": (
                None
                if self.input_token_estimate is None
                else int(self.input_token_estimate)
            ),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SizeCovariates":
        ite = data.get("input_token_estimate")
        return cls(
            n_gauge_nodes=int(data["n_gauge_nodes"]),
            n_fields=int(data["n_fields"]),
            n_superpotential_terms=int(data["n_superpotential_terms"]),
            max_superpotential_monomial_length=int(
                data["max_superpotential_monomial_length"]
            ),
            n_r_charge_bearing_fields=int(data["n_r_charge_bearing_fields"]),
            input_token_estimate=None if ite is None else int(ite),
        )


def compute_size_covariates(
    candidate: Mapping[str, Any],
    *,
    electric: Mapping[str, Any] | None = None,
) -> SizeCovariates:
    """Compute covariates from the candidate theory JSON.

    `electric` is optional and only feeds the whole-prompt token
    estimate; when omitted the estimate covers the candidate alone.
    """

    ranks = list(candidate.get("ranks", []))
    arrows = list(candidate.get("arrows", []))
    superpotential = list(candidate.get("superpotential", []))
    max_mono = max((len(t.get("factors", [])) for t in superpotential), default=0)
    n_r = sum(1 for a in arrows if "r_charge" in a)

    estimate_chars = len(json.dumps(dict(candidate), sort_keys=True))
    if electric is not None:
        estimate_chars += len(json.dumps(dict(electric), sort_keys=True))

    return SizeCovariates(
        n_gauge_nodes=len(ranks),
        n_fields=len(arrows),
        n_superpotential_terms=len(superpotential),
        max_superpotential_monomial_length=max_mono,
        n_r_charge_bearing_fields=n_r,
        input_token_estimate=estimate_chars // 4,
    )


# ----------------------------------------------------------------------
# Main manifest record.
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class ManifestRecord:
    """One verifier-gated fixture in the main evaluation manifest."""

    fixture_id: str
    seed_id: int
    depth: int
    perturbation_class: str
    label: str  # "CERTIFIED" | "FAILED"
    repairable: bool
    theory_a_path: str
    theory_b_path: str
    sanitized: bool
    verifier_status: str
    failed_obligations: tuple[dict[str, Any], ...]
    verifier_config_hash: str
    verifier_config: dict[str, Any]
    size_covariates: SizeCovariates
    generation_metadata: dict[str, Any]
    perturbation_metadata: dict[str, Any] = field(default_factory=dict)
    mutation_chain_id: str | None = None
    source: str = ""
    split: str = "eval"

    def __post_init__(self) -> None:
        if self.label not in {"CERTIFIED", "FAILED"}:
            raise ValueError(
                f"ManifestRecord.label must be CERTIFIED or FAILED; "
                f"got {self.label!r}"
            )
        if self.verifier_status not in {"CERTIFIED", "FAILED"}:
            raise ValueError(
                f"ManifestRecord.verifier_status must be CERTIFIED or FAILED "
                f"(main manifest is verifier-gated); got {self.verifier_status!r}"
            )

    @property
    def ground_truth_label(self) -> str:
        """Detection label space: CERTIFIED->dual, FAILED->not_dual."""

        return "dual" if self.label == "CERTIFIED" else "not_dual"


def manifest_record_to_dict(record: ManifestRecord) -> dict[str, Any]:
    return {
        "fixture_id": record.fixture_id,
        "seed_id": int(record.seed_id),
        "mutation_chain_id": record.mutation_chain_id,
        "depth": int(record.depth),
        "perturbation_class": record.perturbation_class,
        "label": record.label,
        "repairable": bool(record.repairable),
        "theory_a_path": record.theory_a_path,
        "theory_b_path": record.theory_b_path,
        "sanitized": bool(record.sanitized),
        "verifier_status": record.verifier_status,
        "failed_obligations": [dict(o) for o in record.failed_obligations],
        "verifier_config_hash": record.verifier_config_hash,
        "verifier_config": dict(record.verifier_config),
        "size_covariates": record.size_covariates.to_dict(),
        "generation_metadata": dict(record.generation_metadata),
        "perturbation_metadata": dict(record.perturbation_metadata),
        "source": record.source,
        "split": record.split,
    }


def manifest_record_from_dict(data: Mapping[str, Any]) -> ManifestRecord:
    return ManifestRecord(
        fixture_id=str(data["fixture_id"]),
        seed_id=int(data["seed_id"]),
        depth=int(data["depth"]),
        perturbation_class=str(data["perturbation_class"]),
        label=str(data["label"]),
        repairable=bool(data["repairable"]),
        theory_a_path=str(data["theory_a_path"]),
        theory_b_path=str(data["theory_b_path"]),
        sanitized=bool(data["sanitized"]),
        verifier_status=str(data["verifier_status"]),
        failed_obligations=tuple(dict(o) for o in data.get("failed_obligations", [])),
        verifier_config_hash=str(data["verifier_config_hash"]),
        verifier_config=dict(data.get("verifier_config", {})),
        size_covariates=SizeCovariates.from_dict(data["size_covariates"]),
        generation_metadata=dict(data.get("generation_metadata", {})),
        perturbation_metadata=dict(data.get("perturbation_metadata", {})),
        mutation_chain_id=(
            None
            if data.get("mutation_chain_id") is None
            else str(data["mutation_chain_id"])
        ),
        source=str(data.get("source", "")),
        split=str(data.get("split", "eval")),
    )


# ----------------------------------------------------------------------
# Attrition record.
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class AttritionRecord:
    """One excluded generation attempt."""

    fixture_id: str
    seed_id: int
    depth: int
    perturbation_class: str
    attrition_reason: str
    detail: str
    verifier_status: str | None
    generation_metadata: dict[str, Any] = field(default_factory=dict)
    mutation_chain_id: str | None = None
    source: str = ""

    def __post_init__(self) -> None:
        if self.attrition_reason not in ATTRITION_REASONS:
            raise ValueError(
                f"AttritionRecord.attrition_reason {self.attrition_reason!r} "
                f"not in {ATTRITION_REASONS!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "seed_id": int(self.seed_id),
            "mutation_chain_id": self.mutation_chain_id,
            "depth": int(self.depth),
            "perturbation_class": self.perturbation_class,
            "attrition_reason": self.attrition_reason,
            "detail": self.detail,
            "verifier_status": self.verifier_status,
            "generation_metadata": dict(self.generation_metadata),
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AttritionRecord":
        return cls(
            fixture_id=str(data["fixture_id"]),
            seed_id=int(data["seed_id"]),
            depth=int(data["depth"]),
            perturbation_class=str(data["perturbation_class"]),
            attrition_reason=str(data["attrition_reason"]),
            detail=str(data.get("detail", "")),
            verifier_status=(
                None
                if data.get("verifier_status") is None
                else str(data["verifier_status"])
            ),
            generation_metadata=dict(data.get("generation_metadata", {})),
            mutation_chain_id=(
                None
                if data.get("mutation_chain_id") is None
                else str(data["mutation_chain_id"])
            ),
            source=str(data.get("source", "")),
        )


# ----------------------------------------------------------------------
# JSONL / CSV I/O.
# ----------------------------------------------------------------------


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def write_manifest_jsonl(
    path: Path | str, records: Iterable[ManifestRecord]
) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(_canonical_json(manifest_record_to_dict(record)))
            fh.write("\n")


def read_manifest_jsonl(path: Path | str) -> list[ManifestRecord]:
    p = Path(path)
    out: list[ManifestRecord] = []
    with p.open("r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{p}: line {lineno} is not valid JSON ({exc.msg})"
                ) from exc
            out.append(manifest_record_from_dict(obj))
    return out


def write_attrition_jsonl(
    path: Path | str, records: Iterable[AttritionRecord]
) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(_canonical_json(record.to_dict()))
            fh.write("\n")


def read_attrition_jsonl(path: Path | str) -> list[AttritionRecord]:
    p = Path(path)
    out: list[AttritionRecord] = []
    with p.open("r", encoding="utf-8") as fh:
        for lineno, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{p}: line {lineno} is not valid JSON ({exc.msg})"
                ) from exc
            out.append(AttritionRecord.from_dict(obj))
    return out


_CSV_COLUMNS: tuple[str, ...] = (
    "fixture_id",
    "seed_id",
    "mutation_chain_id",
    "depth",
    "perturbation_class",
    "label",
    "ground_truth_label",
    "repairable",
    "source",
    "split",
    "verifier_status",
    "verifier_config_hash",
    "failed_obligation_names",
    "failed_obligation_categories",
    "n_gauge_nodes",
    "n_fields",
    "n_superpotential_terms",
    "max_superpotential_monomial_length",
    "n_r_charge_bearing_fields",
    "input_token_estimate",
    "theory_a_path",
    "theory_b_path",
)


def write_manifest_csv(
    path: Path | str, records: Iterable[ManifestRecord]
) -> None:
    """Flat one-row-per-fixture CSV (nested obligations flattened to ';')."""

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(_CSV_COLUMNS))
        writer.writeheader()
        for r in records:
            names = ";".join(str(o.get("name", "")) for o in r.failed_obligations)
            cats = ";".join(
                str(o.get("category", "")) for o in r.failed_obligations
            )
            sc = r.size_covariates
            writer.writerow(
                {
                    "fixture_id": r.fixture_id,
                    "seed_id": r.seed_id,
                    "mutation_chain_id": r.mutation_chain_id or "",
                    "depth": r.depth,
                    "perturbation_class": r.perturbation_class,
                    "label": r.label,
                    "ground_truth_label": r.ground_truth_label,
                    "repairable": int(r.repairable),
                    "source": r.source,
                    "split": r.split,
                    "verifier_status": r.verifier_status,
                    "verifier_config_hash": r.verifier_config_hash,
                    "failed_obligation_names": names,
                    "failed_obligation_categories": cats,
                    "n_gauge_nodes": sc.n_gauge_nodes,
                    "n_fields": sc.n_fields,
                    "n_superpotential_terms": sc.n_superpotential_terms,
                    "max_superpotential_monomial_length": (
                        sc.max_superpotential_monomial_length
                    ),
                    "n_r_charge_bearing_fields": sc.n_r_charge_bearing_fields,
                    "input_token_estimate": (
                        "" if sc.input_token_estimate is None
                        else sc.input_token_estimate
                    ),
                    "theory_a_path": r.theory_a_path,
                    "theory_b_path": r.theory_b_path,
                }
            )
