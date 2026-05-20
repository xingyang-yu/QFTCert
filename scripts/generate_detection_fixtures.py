"""Phase 2c-a fixture generator (Step 4).

Produces two paired files for both the smoke and the MVP datasets:

    fixtures/detection_smoke.jsonl
    fixtures/detection_smoke.generation.jsonl
    fixtures/detection_mvp.jsonl
    fixtures/detection_mvp.generation.jsonl

Both fixture files are deterministic given the seeds baked into this
script — re-running this script must reproduce byte-identical output so
the committed JSONL files stay verifiable. The generation log records
every attempt (accepted + discarded) for full audit-trail.

Run from repo root::

    python -m scripts.generate_detection_fixtures
    python -m scripts.generate_detection_fixtures --smoke-only
    python -m scripts.generate_detection_fixtures --output-dir tmp/

No LLM calls; this is a pure verifier-grounded pipeline.
"""

from __future__ import annotations

import argparse
import itertools
import sys
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Callable, Iterable

# Allow `python scripts/generate_detection_fixtures.py` from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dualitycert.benchmark import (  # noqa: E402
    Fixture,
    GenerationLogEntry,
    write_fixtures_jsonl,
    write_generation_log,
)
from dualitycert.benchmark.generators import (  # noqa: E402
    attempt_positive,
    attempt_r_naive,
    attempt_rank_perturb,
    attempt_w_drop,
    attempt_w_sign_swap,
    attempt_wrong_pair,
)
from dualitycert.core.objects import SuperpotentialTerm  # noqa: E402
from dualitycert.groups.u1 import u1_r  # noqa: E402
from dualitycert.qft.pure_quiver_builder import (  # noqa: E402
    arrow_names,
    build_pure_quiver,
    dp0_superpotential,
)
from dualitycert.qft.pure_quiver_json import pure_quiver_to_json  # noqa: E402


# ----------------------------------------------------------------------
# Seed theories (electric sources).
# ----------------------------------------------------------------------


def dp0_electric(N: int) -> dict:
    n01 = arrow_names(0, 1, 3)
    n12 = arrow_names(1, 2, 3)
    n20 = arrow_names(2, 0, 3)
    return pure_quiver_to_json(
        build_pure_quiver(
            ranks=(N, N, N),
            arrows={
                (0, 1): [Fraction(2, 3)] * 3,
                (1, 2): [Fraction(2, 3)] * 3,
                (2, 0): [Fraction(2, 3)] * 3,
            },
            superpotential=dp0_superpotential(n01, n12, n20),
            u1_globals=(u1_r(),),
        )
    )


def f0_phase_ii_electric(N: int) -> dict:
    def eps(a: int, b: int) -> int:
        if (a, b) == (0, 1):
            return 1
        if (a, b) == (1, 0):
            return -1
        return 0

    R_BD = Fraction(1, 2)
    R_DI = Fraction(1, 1)
    W: list[SuperpotentialTerm] = []
    for a, i, alpha, beta in itertools.product(range(2), repeat=4):
        sign = eps(a, alpha) * eps(i, beta)
        if sign == 0:
            continue
        W.append(
            SuperpotentialTerm(
                factors=(
                    (f"X01[{a}]", 1),
                    (f"X12[{i}]", 1),
                    (f"X20[{2 * alpha + beta}]", 1),
                ),
                coefficient=Fraction(sign),
            )
        )
    for a, i, alpha, beta in itertools.product(range(2), repeat=4):
        sign = eps(a, alpha) * eps(i, beta)
        if sign == 0:
            continue
        W.append(
            SuperpotentialTerm(
                factors=(
                    (f"X03[{a}]", 1),
                    (f"X32[{i}]", 1),
                    (f"X20[{2 * alpha + beta}]", 1),
                ),
                coefficient=Fraction(-sign),
            )
        )
    return pure_quiver_to_json(
        build_pure_quiver(
            ranks=(N, N, N, N),
            arrows={
                (0, 1): [R_BD] * 2,
                (0, 3): [R_BD] * 2,
                (2, 0): [R_DI] * 4,
                (1, 2): [R_BD] * 2,
                (3, 2): [R_BD] * 2,
            },
            superpotential=tuple(W),
            u1_globals=(u1_r(),),
        )
    )


# ----------------------------------------------------------------------
# Dataset specification.
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class PositiveSpec:
    """One positive-fixture slot."""

    source_name: str
    electric: dict
    node: int
    N: int


@dataclass(frozen=True)
class NegativeBudget:
    """Per-class negative target counts for one dataset."""

    w_drop: int
    w_sign_swap: int
    r_naive: int
    rank_perturb: int
    wrong_pair: int


@dataclass
class DatasetSpec:
    name: str
    positives: list[PositiveSpec]
    negatives: NegativeBudget
    rng_seed_base: int = 1000
    max_retries_per_slot: int = 20


# Locked positive sources for both datasets. Two families (dP_0 + F_0 II)
# so wrong-pair is meaningful, and N varies (3, 4) per Rule 8.
def _mvp_positives() -> list[PositiveSpec]:
    return [
        PositiveSpec("dp0_toric", dp0_electric(3), node=0, N=3),
        PositiveSpec("dp0_toric", dp0_electric(3), node=1, N=3),
        PositiveSpec("dp0_toric", dp0_electric(3), node=2, N=3),
        PositiveSpec("dp0_toric", dp0_electric(4), node=0, N=4),
        PositiveSpec("f0_phase_ii", f0_phase_ii_electric(3), node=0, N=3),
        PositiveSpec("f0_phase_ii", f0_phase_ii_electric(3), node=2, N=3),
    ]


def _smoke_positives() -> list[PositiveSpec]:
    return [
        PositiveSpec("dp0_toric", dp0_electric(3), node=0, N=3),
        PositiveSpec("f0_phase_ii", f0_phase_ii_electric(3), node=0, N=3),
    ]


MVP_SPEC = DatasetSpec(
    name="detection_mvp",
    positives=_mvp_positives(),
    negatives=NegativeBudget(
        w_drop=8,
        w_sign_swap=4,
        r_naive=8,
        rank_perturb=2,
        wrong_pair=2,
    ),
    rng_seed_base=10_000,
)


SMOKE_SPEC = DatasetSpec(
    name="detection_smoke",
    positives=_smoke_positives(),
    negatives=NegativeBudget(
        w_drop=2,
        w_sign_swap=1,
        r_naive=2,
        rank_perturb=1,
        wrong_pair=1,
    ),
    rng_seed_base=1_000,
)


# ----------------------------------------------------------------------
# Dataset builder.
# ----------------------------------------------------------------------


@dataclass
class DatasetResult:
    fixtures: list[Fixture] = field(default_factory=list)
    log_entries: list[GenerationLogEntry] = field(default_factory=list)


def build_dataset(spec: DatasetSpec) -> DatasetResult:
    """Construct a fully-gated dataset from a `DatasetSpec`.

    Deterministic given `spec.rng_seed_base`: the same spec produces the
    same accepted-fixture order and the same generation log.
    """

    result = DatasetResult()
    positives = _build_positives(spec, result)

    # Each negative class uses its own seed namespace so adding/removing
    # one class does not perturb the seeds of the others.
    cls_seed_base = spec.rng_seed_base

    _build_negatives_per_positive(
        spec=spec,
        positives=positives,
        result=result,
        target=spec.negatives.w_drop,
        seed_base=cls_seed_base,
        cls_name="w_drop",
        attempt_fn=attempt_w_drop,
    )
    cls_seed_base += 1000

    _build_negatives_per_positive(
        spec=spec,
        positives=positives,
        result=result,
        target=spec.negatives.w_sign_swap,
        seed_base=cls_seed_base,
        cls_name="w_sign_swap",
        attempt_fn=attempt_w_sign_swap,
    )
    cls_seed_base += 1000

    _build_negatives_per_positive(
        spec=spec,
        positives=positives,
        result=result,
        target=spec.negatives.r_naive,
        seed_base=cls_seed_base,
        cls_name="r_naive",
        attempt_fn=attempt_r_naive,
    )
    cls_seed_base += 1000

    _build_negatives_per_positive(
        spec=spec,
        positives=positives,
        result=result,
        target=spec.negatives.rank_perturb,
        seed_base=cls_seed_base,
        cls_name="rank_perturb",
        attempt_fn=attempt_rank_perturb,
    )
    cls_seed_base += 1000

    _build_wrong_pairs(
        spec=spec,
        positives=positives,
        result=result,
        target=spec.negatives.wrong_pair,
        seed_base=cls_seed_base,
    )

    return result


def _build_positives(
    spec: DatasetSpec,
    result: DatasetResult,
) -> list[Fixture]:
    """Build positive fixtures. Each PositiveSpec is one slot."""

    positives: list[Fixture] = []
    for i, pos_spec in enumerate(spec.positives):
        fixture_id = (
            f"{pos_spec.source_name}_N{pos_spec.N}_node{pos_spec.node}"
            f"_positive_{i:03d}"
        )
        fix, log = attempt_positive(
            electric_json=pos_spec.electric,
            node=pos_spec.node,
            N=pos_spec.N,
            source_name=pos_spec.source_name,
            fixture_id=fixture_id,
            seed=spec.rng_seed_base + i,
        )
        result.log_entries.append(log)
        if fix is not None:
            result.fixtures.append(fix)
            positives.append(fix)
    return positives


def _build_negatives_per_positive(
    *,
    spec: DatasetSpec,
    positives: list[Fixture],
    result: DatasetResult,
    target: int,
    seed_base: int,
    cls_name: str,
    attempt_fn: Callable[..., tuple[Fixture | None, GenerationLogEntry]],
) -> None:
    """Round-robin over positives; for each slot, try seeds until accepted.

    For `w_drop`, `w_sign_swap`, `r_naive`, `rank_perturb`. Stops once
    `target` accepted negatives have been collected or the script has
    spent `len(positives) * max_retries_per_slot` attempts without
    progress (a generous finite bound).
    """

    if not positives or target <= 0:
        return

    accepted = 0
    slot = 0
    max_slots = max(target * 5, len(positives) * 3)
    while accepted < target and slot < max_slots:
        positive = positives[slot % len(positives)]
        slot_seed_base = seed_base + slot * spec.max_retries_per_slot
        for attempt_offset in range(spec.max_retries_per_slot):
            seed = slot_seed_base + attempt_offset
            fixture_id = (
                f"{positive.fixture_id}_{cls_name}_{slot:03d}_{attempt_offset:02d}"
            )
            fix, raw_log = attempt_fn(
                positive=positive,
                fixture_id=fixture_id,
                seed=seed,
            )
            if fix is None:
                # Genuine generator-level discard (empty W, etc.).
                result.log_entries.append(raw_log)
                continue
            if fix.ground_truth_label != "not_dual":
                # Silent miss (Rule 9): the perturbation did not break
                # the verifier. Rewrite the log entry as a discard with
                # the verifier verdict preserved for audit.
                result.log_entries.append(
                    GenerationLogEntry(
                        fixture_id=raw_log.fixture_id,
                        generation_status="discarded",
                        discard_reason=(
                            "silent_miss("
                            f"{fix.verifier_ground_truth['overall_status']})"
                        ),
                        prompt_visible_fields=(),
                        verifier_ground_truth=dict(fix.verifier_ground_truth),
                        metadata=raw_log.metadata,
                    )
                )
                continue
            # Genuine "not_dual" negative.
            result.log_entries.append(raw_log)
            result.fixtures.append(fix)
            accepted += 1
            break
        slot += 1


def _build_wrong_pairs(
    *,
    spec: DatasetSpec,
    positives: list[Fixture],
    result: DatasetResult,
    target: int,
    seed_base: int,
) -> None:
    """Wrong-pair across families only — same-family routes through dual."""

    if target <= 0:
        return

    # Group positives by source family.
    by_source: dict[str, list[Fixture]] = {}
    for p in positives:
        by_source.setdefault(p.metadata.source, []).append(p)
    families = sorted(by_source)
    if len(families) < 2:
        # Not enough variety; nothing to do (script logs nothing — every
        # generation attempt is gated, this is a structural skip).
        return

    # Enumerate all cross-family (electric_family_a, candidate_family_b) pairs.
    cross_pairs: list[tuple[Fixture, Fixture]] = []
    for fa, fb in itertools.combinations(families, 2):
        for ea in by_source[fa]:
            for cb in by_source[fb]:
                cross_pairs.append((ea, cb))
            for eb in by_source[fb]:
                for ca in by_source[fa]:
                    cross_pairs.append((eb, ca))

    accepted = 0
    for i, (electric_from, candidate_from) in enumerate(cross_pairs):
        if accepted >= target:
            break
        fixture_id = (
            f"wrong_pair_{electric_from.fixture_id}__x__"
            f"{candidate_from.fixture_id}_{i:03d}"
        )
        fix, raw_log = attempt_wrong_pair(
            electric_from=electric_from,
            candidate_from=candidate_from,
            fixture_id=fixture_id,
            seed=seed_base + i,
        )
        if fix is None:
            result.log_entries.append(raw_log)
            continue
        if fix.ground_truth_label != "not_dual":
            result.log_entries.append(
                GenerationLogEntry(
                    fixture_id=raw_log.fixture_id,
                    generation_status="discarded",
                    discard_reason=(
                        "silent_miss("
                        f"{fix.verifier_ground_truth['overall_status']})"
                    ),
                    prompt_visible_fields=(),
                    verifier_ground_truth=dict(fix.verifier_ground_truth),
                    metadata=raw_log.metadata,
                )
            )
            continue
        result.log_entries.append(raw_log)
        result.fixtures.append(fix)
        accepted += 1


# ----------------------------------------------------------------------
# Driver.
# ----------------------------------------------------------------------


def write_dataset(spec: DatasetSpec, *, output_dir: Path) -> DatasetResult:
    result = build_dataset(spec)
    fixtures_path = output_dir / f"{spec.name}.jsonl"
    log_path = output_dir / f"{spec.name}.generation.jsonl"
    write_fixtures_jsonl(fixtures_path, result.fixtures)
    write_generation_log(log_path, result.log_entries)
    return result


def _summarize(spec: DatasetSpec, result: DatasetResult) -> str:
    accepted = len(result.fixtures)
    discarded = sum(
        1 for entry in result.log_entries if entry.generation_status == "discarded"
    )
    by_class: dict[str, int] = {}
    by_label: dict[str, int] = {"dual": 0, "not_dual": 0}
    for fix in result.fixtures:
        ptype = fix.metadata.perturbation_type
        by_class[ptype] = by_class.get(ptype, 0) + 1
        by_label[fix.ground_truth_label] += 1
    lines = [
        f"[{spec.name}] accepted={accepted} discarded={discarded}",
        f"  labels: dual={by_label['dual']}, not_dual={by_label['not_dual']}",
        f"  by perturbation_type:",
    ]
    for k in ("none", "w_drop", "w_sign_swap", "r_naive", "rank_perturb", "wrong_pair"):
        lines.append(f"    {k}: {by_class.get(k, 0)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default="fixtures",
        type=Path,
        help="Directory to write JSONL files into (default: fixtures/).",
    )
    parser.add_argument(
        "--smoke-only",
        action="store_true",
        help="Generate only the smoke set (skip the MVP set).",
    )
    parser.add_argument(
        "--mvp-only",
        action="store_true",
        help="Generate only the MVP set (skip the smoke set).",
    )
    args = parser.parse_args(argv)

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    specs: list[DatasetSpec] = []
    if not args.mvp_only:
        specs.append(SMOKE_SPEC)
    if not args.smoke_only:
        specs.append(MVP_SPEC)

    for spec in specs:
        result = write_dataset(spec, output_dir=output_dir)
        print(_summarize(spec, result))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
