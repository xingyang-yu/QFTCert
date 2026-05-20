"""Fixture schema, sanitizer, and JSONL I/O for the detection benchmark.

This module is the persistence and prompt-sanitization layer for Phase
2c-a. It is deliberately decoupled from the generators (they construct
fixtures) and the runner (it consumes them) so the fixture format can
evolve in isolation.

Locked conventions (see `docs/phase2c_a_detection_plan.md`):

  - Fixture JSON shape::

        {
          "fixture_id": str,
          "ground_truth_label": "dual" | "not_dual",
          "verifier_ground_truth": {
              "overall_status": "CERTIFIED" | "FAILED",
              "failed_obligations": [str, ...],
          },
          "electric":  <full pure-quiver theory JSON>,
          "candidate": <full pure-quiver theory JSON>,
          "metadata":  <free-form provenance dict>,
        }

    The fixture file is JSONL. Every record is `json.dumps(...,
    sort_keys=True, ensure_ascii=False)` so byte-equality with what we
    commit is checkable from the script alone.

  - `electric` and `candidate` are stored UNSANITIZED — the runner is
    responsible for calling `sanitize_for_prompt()` before forming the
    LLM prompt, so a fixture file is also a complete audit trail of
    what physics was actually present (not what the LLM saw). The
    sanitization is a runtime concern, not a storage concern.

  - The generation log (`fixtures/<dataset>.generation.jsonl`) lives
    next to the fixture file and records every generation *attempt*
    (accepted + discarded), with a `prompt_visible_fields` audit-trail
    field. Only `accepted` entries also appear in the fixture file.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping


__all__ = [
    "Fixture",
    "FixtureMetadata",
    "GenerationLogEntry",
    "fixture_from_dict",
    "fixture_set_hash",
    "fixture_to_dict",
    "generation_entry_from_dict",
    "generation_entry_to_dict",
    "read_fixtures_jsonl",
    "read_generation_log",
    "sanitize_for_prompt",
    "write_fixtures_jsonl",
    "write_generation_log",
]


# ----------------------------------------------------------------------
# Dataclasses (thin wrappers over the JSON shape).
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class FixtureMetadata:
    """Provenance for a single fixture, common-field portion.

    `extra` holds class-specific provenance (e.g. `dropped_term` for
    Type-4 W drops, `perturbed_field` / `delta` for Type-3 R naive).
    The runner aggregates by `perturbation_type` for the per-class
    accuracy table in `summary.json`.

    Standard `perturbation_type` values (locked, do not invent new ones
    without updating the metrics module):

      - ``"none"``         — positive fixture (real Seiberg-mutated dual)
      - ``"w_drop"``       — Type-4 W term dropped
      - ``"w_sign_swap"``  — Type-4 W coefficient sign flipped
      - ``"r_naive"``      — Type-3 single-field R perturb (no W kernel)
      - ``"rank_perturb"`` — Type-1/2 trivial rank flip
      - ``"wrong_pair"``   — unrelated (electric, candidate) pairing
    """

    source: str
    seed: int
    perturbation_type: str
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "source": self.source,
            "seed": int(self.seed),
            "perturbation_type": self.perturbation_type,
        }
        if self.extra:
            out["extra"] = dict(self.extra)
        return out

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FixtureMetadata":
        return cls(
            source=str(data["source"]),
            seed=int(data["seed"]),
            perturbation_type=str(data["perturbation_type"]),
            extra=dict(data.get("extra", {})),
        )


@dataclass(frozen=True)
class Fixture:
    """One (electric, candidate) blind-detection pair plus ground truth."""

    fixture_id: str
    ground_truth_label: str
    verifier_ground_truth: dict[str, Any]
    electric: dict[str, Any]
    candidate: dict[str, Any]
    metadata: FixtureMetadata

    def __post_init__(self) -> None:
        if self.ground_truth_label not in {"dual", "not_dual"}:
            raise ValueError(
                f"Fixture.ground_truth_label must be 'dual' or 'not_dual'; "
                f"got {self.ground_truth_label!r}"
            )
        overall = self.verifier_ground_truth.get("overall_status")
        if overall not in {"CERTIFIED", "FAILED"}:
            raise ValueError(
                f"Fixture.verifier_ground_truth.overall_status must be "
                f"'CERTIFIED' or 'FAILED' (Rule 6); got {overall!r}"
            )
        expected_label = "dual" if overall == "CERTIFIED" else "not_dual"
        if self.ground_truth_label != expected_label:
            raise ValueError(
                f"Fixture.ground_truth_label {self.ground_truth_label!r} does "
                f"not match verifier_ground_truth.overall_status {overall!r}; "
                f"expected {expected_label!r}"
            )


@dataclass(frozen=True)
class GenerationLogEntry:
    """One generation *attempt* record (accepted OR discarded)."""

    fixture_id: str
    generation_status: str          # "accepted" | "discarded"
    discard_reason: str | None
    prompt_visible_fields: tuple[str, ...]
    verifier_ground_truth: dict[str, Any] | None
    metadata: FixtureMetadata

    def __post_init__(self) -> None:
        if self.generation_status not in {"accepted", "discarded"}:
            raise ValueError(
                f"GenerationLogEntry.generation_status must be 'accepted' or "
                f"'discarded'; got {self.generation_status!r}"
            )
        if self.generation_status == "accepted" and self.discard_reason is not None:
            raise ValueError(
                "GenerationLogEntry: 'accepted' entries must have "
                "discard_reason=None"
            )
        if self.generation_status == "discarded" and self.discard_reason is None:
            raise ValueError(
                "GenerationLogEntry: 'discarded' entries must carry a "
                "non-None discard_reason"
            )


# ----------------------------------------------------------------------
# Sanitization (Rule 3).
# ----------------------------------------------------------------------


def sanitize_for_prompt(
    theory_json: Mapping[str, Any],
    *,
    theory_label: str,
) -> dict[str, Any]:
    """Strip provenance-leaking fields from a pure-quiver theory JSON.

    The detection benchmark blinds the LLM to anything that hints at
    where the theory came from (Seiberg-mutated? R-repaired? which
    seed?). This function returns a fresh dict whose physical content
    (ranks, arrow structure, R-charges, W coefficients) is preserved
    verbatim, but whose human-readable provenance fields are replaced
    with neutral placeholders.

    Stripped / replaced:
      - ``name``        → `theory_label` (e.g. "Theory A")
      - ``node_labels`` → ``[f"G{i}" for i in range(len(ranks))]``
        (kills strings like "SU(2N)_0" that leak the rank parametrization)

    Preserved verbatim:
      - ``ranks``           — integer list
      - ``u1_globals``      — optional list (defaults to [] if missing)
      - ``arrows``          — including the structural ``X{i}{j}[k]``
        labels; these are source/target indexers, not provenance.
      - ``superpotential``  — including coefficients (as stored strings)

    The input mapping is NOT mutated; the output is a fresh dict with
    fresh inner lists, so the runner can json.dumps() the result
    without worrying about aliasing.
    """

    ranks = [int(r) for r in theory_json["ranks"]]
    n = len(ranks)
    return {
        "name": theory_label,
        "node_labels": [f"G{i}" for i in range(n)],
        "ranks": ranks,
        "u1_globals": list(theory_json.get("u1_globals", [])),
        "arrows": [dict(a) for a in theory_json["arrows"]],
        "superpotential": [
            {"factors": list(t["factors"]), "coefficient": t["coefficient"]}
            for t in theory_json["superpotential"]
        ],
    }


# ----------------------------------------------------------------------
# Fixture <-> dict round-trip.
# ----------------------------------------------------------------------


def fixture_to_dict(fixture: Fixture) -> dict[str, Any]:
    """Convert a `Fixture` to its JSON-serializable dict form."""

    return {
        "fixture_id": fixture.fixture_id,
        "ground_truth_label": fixture.ground_truth_label,
        "verifier_ground_truth": _copy_verifier_ground_truth(
            fixture.verifier_ground_truth
        ),
        "electric": _deep_copy_json(fixture.electric),
        "candidate": _deep_copy_json(fixture.candidate),
        "metadata": fixture.metadata.to_dict(),
    }


def fixture_from_dict(data: Mapping[str, Any]) -> Fixture:
    """Inverse of `fixture_to_dict`; validates the shape."""

    return Fixture(
        fixture_id=str(data["fixture_id"]),
        ground_truth_label=str(data["ground_truth_label"]),
        verifier_ground_truth=_copy_verifier_ground_truth(
            data["verifier_ground_truth"]
        ),
        electric=_deep_copy_json(data["electric"]),
        candidate=_deep_copy_json(data["candidate"]),
        metadata=FixtureMetadata.from_dict(data["metadata"]),
    )


def generation_entry_to_dict(entry: GenerationLogEntry) -> dict[str, Any]:
    out: dict[str, Any] = {
        "fixture_id": entry.fixture_id,
        "generation_status": entry.generation_status,
        "discard_reason": entry.discard_reason,
        "prompt_visible_fields": list(entry.prompt_visible_fields),
        "metadata": entry.metadata.to_dict(),
    }
    if entry.verifier_ground_truth is not None:
        out["verifier_ground_truth"] = _copy_verifier_ground_truth(
            entry.verifier_ground_truth
        )
    else:
        out["verifier_ground_truth"] = None
    return out


def generation_entry_from_dict(data: Mapping[str, Any]) -> GenerationLogEntry:
    raw_gt = data.get("verifier_ground_truth")
    return GenerationLogEntry(
        fixture_id=str(data["fixture_id"]),
        generation_status=str(data["generation_status"]),
        discard_reason=(
            None if data.get("discard_reason") is None
            else str(data["discard_reason"])
        ),
        prompt_visible_fields=tuple(data.get("prompt_visible_fields", [])),
        verifier_ground_truth=(
            None if raw_gt is None else _copy_verifier_ground_truth(raw_gt)
        ),
        metadata=FixtureMetadata.from_dict(data["metadata"]),
    )


# ----------------------------------------------------------------------
# JSONL I/O.
# ----------------------------------------------------------------------


def write_fixtures_jsonl(path: Path | str, fixtures: Iterable[Fixture]) -> None:
    """Write an iterable of fixtures as one JSON object per line.

    Per Rule 10, records are serialized with ``sort_keys=True`` so two
    different generator runs that produce the same fixtures yield
    byte-identical output, and so that the file is diff-readable on
    re-generation.
    """

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        for fixture in fixtures:
            fh.write(_canonical_json(fixture_to_dict(fixture)))
            fh.write("\n")


def read_fixtures_jsonl(path: Path | str) -> list[Fixture]:
    """Read a JSONL fixture file. Skips blank lines."""

    p = Path(path)
    out: list[Fixture] = []
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
            out.append(fixture_from_dict(obj))
    return out


def write_generation_log(
    path: Path | str,
    entries: Iterable[GenerationLogEntry],
) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(_canonical_json(generation_entry_to_dict(entry)))
            fh.write("\n")


def read_generation_log(path: Path | str) -> list[GenerationLogEntry]:
    p = Path(path)
    out: list[GenerationLogEntry] = []
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
            out.append(generation_entry_from_dict(obj))
    return out


def fixture_set_hash(fixtures: Iterable[Fixture]) -> str:
    """Stable sha256 fingerprint of a fixture set.

    The runner pins this in `metadata.json` so a results file can be
    matched back to its source fixtures. Order of input matters: the
    detection benchmark is order-sensitive (different shufflings change
    the LLM's per-batch sampling), so we hash in input order.
    """

    h = hashlib.sha256()
    for fixture in fixtures:
        h.update(_canonical_json(fixture_to_dict(fixture)).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


# ----------------------------------------------------------------------
# Internal helpers.
# ----------------------------------------------------------------------


def _canonical_json(obj: Any) -> str:
    """Serialize `obj` deterministically (sort_keys, no indent, UTF-8)."""

    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def _deep_copy_json(obj: Any) -> Any:
    """Deep copy via json round-trip (suffices for our value types)."""

    return json.loads(json.dumps(obj))


def _copy_verifier_ground_truth(data: Mapping[str, Any]) -> dict[str, Any]:
    """Per Rule 6 the verifier ground truth has a fixed two-field shape."""

    overall = data["overall_status"]
    failed = list(data.get("failed_obligations", []))
    return {
        "overall_status": str(overall),
        "failed_obligations": [str(name) for name in failed],
    }
