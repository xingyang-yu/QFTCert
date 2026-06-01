"""Verifier-gated fixture generation (Deliverable 3).

Generates candidate (electric, candidate) pairs for each
depth x perturbation_class cell, runs the verifier on every candidate
under the experiment's `VerifierConfig`, and keeps only unambiguous
CERTIFIED / FAILED records in the main manifest. Everything else
(UNKNOWN / NOT_APPLICABLE / OUT_OF_SCOPE / verifier errors / silent
misses / duplicates / depth>=2 cells the engine cannot build) goes to a
separate attrition manifest. Nothing invalid is silently included.

Determinism: every random choice is seeded from `config.seed` via a
stable sha256-derived sub-seed, so re-running with the same config
(and the same `generated_at` override) yields byte-identical manifests.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from random import Random
from typing import Any, Mapping

from dualitycert.benchmark.fixtures import sanitize_for_prompt
from dualitycert.experiments.chains import (
    MutationChainResult,
    _chain_id,
    canonical_theory_hash,
    generate_mutation_chain,
    seiberg_dual_consistent,
)
from dualitycert.experiments.config import ExperimentConfig
from dualitycert.experiments.manifest import (
    AttritionRecord,
    ManifestRecord,
    compute_size_covariates,
    write_attrition_jsonl,
    write_manifest_csv,
    write_manifest_jsonl,
)
from dualitycert.experiments.perturbations import (
    PERTURBATION_REGISTRY,
    PerturbationError,
    apply_single_positive_edit,
)
from dualitycert.experiments.seeds import SeedSpec, default_seed_specs
from dualitycert.experiments.verifier import VerifierOutcome, run_verifier


__all__ = [
    "GENERATOR_VERSION",
    "GenerationResult",
    "IncompleteCellsError",
    "generate_fixtures",
]


GENERATOR_VERSION = "qftcert-experiments/0.1"


class IncompleteCellsError(ValueError):
    """A strict run left one or more requested (depth x class) cells empty.

    Raised by `generate_fixtures` AFTER generation when
    `allow_incomplete_cells` is False and some requested cell produced
    zero main-manifest fixtures (e.g. the physics / verifier scope
    rejected every depth-K attempt). This keeps a paper run from silently
    claiming coverage it does not actually have; set
    `allow_incomplete_cells` to record honest attrition instead.
    """


@dataclass
class GenerationResult:
    manifest: list[ManifestRecord] = field(default_factory=list)
    attrition: list[AttritionRecord] = field(default_factory=list)
    out_dir: Path | None = None

    def label_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {"CERTIFIED": 0, "FAILED": 0}
        for r in self.manifest:
            counts[r.label] = counts.get(r.label, 0) + 1
        return counts

    def class_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.manifest:
            counts[r.perturbation_class] = counts.get(r.perturbation_class, 0) + 1
        return counts


def generate_fixtures(
    config: ExperimentConfig,
    *,
    out_dir: Path | str | None = None,
    seed_specs: list[SeedSpec] | None = None,
    generated_at: str | None = None,
    git_commit: str | None = None,
    allow_incomplete_cells: bool | None = None,
    write: bool = True,
) -> GenerationResult:
    """Generate a verifier-gated manifest + attrition manifest.

    Theory JSONs are written under `<out_dir>/theories/`; manifest paths
    are stored relative to `out_dir`. Pass `generated_at` to pin the
    timestamp (tests) and `git_commit` to avoid shelling out to git.

    Strict by default: if the config requests depths the mutation engine
    cannot build (depth >= 2) and neither `allow_incomplete_cells` nor
    `config.allow_incomplete_cells` is set, raises `IncompleteCellsError`
    before generating anything (so a paper run cannot silently ship
    partial depth coverage).
    """

    allow_incomplete = (
        config.allow_incomplete_cells
        if allow_incomplete_cells is None
        else allow_incomplete_cells
    )

    out_dir_path = Path(out_dir if out_dir is not None else config.output_dir)
    seed_specs = seed_specs if seed_specs is not None else default_seed_specs()
    generated_at = generated_at or datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )
    git_commit = git_commit if git_commit is not None else _git_commit()

    gen_meta_base: dict[str, Any] = {
        "generated_at": generated_at,
        "generator_version": GENERATOR_VERSION,
        "git_commit": git_commit,
    }

    result = GenerationResult(out_dir=out_dir_path)

    # Phase 2d-ext: endpoint-pool pairing is an additive alternative to the
    # legacy (T0, T_K) generation below. Default stays legacy.
    if config.pair_generation_mode == "endpoint_pool":
        from dualitycert.experiments.endpoint_pool import (
            generate_endpoint_pool_fixtures,
        )

        manifest, attrition = generate_endpoint_pool_fixtures(
            config,
            out_dir=out_dir_path,
            seed_specs=seed_specs,
            generated_at=generated_at,
            git_commit=git_commit,
            generator_version=GENERATOR_VERSION,
            write=write,
        )
        result.manifest.extend(manifest)
        result.attrition.extend(attrition)
        if write:
            _write_outputs(config, result, out_dir_path)
        return result

    seen_pair_hash: dict[str, str] = {}
    theories_dir = out_dir_path / "theories"

    def _gen_meta(seed_id: int) -> dict[str, Any]:
        return {"rng_seed": int(seed_id), **gen_meta_base}

    def _register(
        *,
        class_name: str,
        electric: Mapping[str, Any],
        candidate: Mapping[str, Any],
        outcome: VerifierOutcome,
        fixture_id: str,
        seed_id: int,
        depth: int,
        source: str,
        chain_id: str | None,
        perturbation_metadata: Mapping[str, Any],
        chain_depth: int = 1,
        mutation_node_sequence: tuple[int, ...] = (),
        intermediate_hashes: tuple[str, ...] = (),
        final_theory_hash: str = "",
    ) -> ManifestRecord | None:
        pair_hash = _pair_hash(electric, candidate)
        if pair_hash in seen_pair_hash:
            result.attrition.append(
                AttritionRecord(
                    fixture_id=fixture_id,
                    seed_id=seed_id,
                    depth=depth,
                    perturbation_class=class_name,
                    attrition_reason="duplicate",
                    detail=f"duplicate of {seen_pair_hash[pair_hash]}",
                    verifier_status=outcome.status,
                    generation_metadata=_gen_meta(seed_id),
                    mutation_chain_id=chain_id,
                    source=source,
                )
            )
            return None
        seen_pair_hash[pair_hash] = fixture_id

        a_rel = f"theories/{fixture_id}.A.json"
        b_rel = f"theories/{fixture_id}.B.json"
        if write:
            _write_theory(theories_dir / f"{fixture_id}.A.json", electric)
            _write_theory(theories_dir / f"{fixture_id}.B.json", candidate)

        spec = PERTURBATION_REGISTRY[class_name]
        record = ManifestRecord(
            fixture_id=fixture_id,
            seed_id=seed_id,
            depth=depth,
            perturbation_class=class_name,
            label=outcome.status,
            repairable=spec.repairable and outcome.status == "FAILED",
            theory_a_path=a_rel,
            theory_b_path=b_rel,
            sanitized=False,
            verifier_status=outcome.status,
            failed_obligations=outcome.failed_obligations,
            verifier_config_hash=config.verifier.config_hash(),
            verifier_config=config.verifier.to_dict(),
            size_covariates=compute_size_covariates(candidate, electric=electric),
            generation_metadata=_gen_meta(seed_id),
            perturbation_metadata=dict(perturbation_metadata),
            mutation_chain_id=chain_id,
            chain_depth=chain_depth,
            mutation_node_sequence=tuple(mutation_node_sequence),
            intermediate_hashes=tuple(intermediate_hashes),
            final_theory_hash=final_theory_hash,
            source=source,
            split=config.split,
        )
        result.manifest.append(record)
        return record

    def _attempt_chain(
        electric: Mapping[str, Any],
        depth: int,
        spec: SeedSpec,
        si: int,
    ) -> MutationChainResult:
        """Build a depth-K chain. depth=1 pins the seed node (MVP-exact);
        depth>=2 retries with fresh rng (unpinned node) up to the budget."""

        if depth == 1:
            chain_seed = _stable_seed(config.seed, depth, si, "chain")
            return generate_mutation_chain(
                electric, 1, Random(chain_seed), config.chain,
                verifier_config=config.verifier, source_name=spec.source_name,
                node=spec.node, seed_id=chain_seed,
            )
        last: MutationChainResult | None = None
        for attempt in range(config.chain.max_chain_attempts_per_cell):
            attempt_seed = _stable_seed(config.seed, depth, si, "chain", attempt)
            chain = generate_mutation_chain(
                electric, depth, Random(attempt_seed), config.chain,
                verifier_config=config.verifier, source_name=spec.source_name,
                node=None, seed_id=attempt_seed,
            )
            if chain.success:
                return chain
            last = chain
        return last  # all attempts failed; carries the last attrition_reason

    single_classes = [
        c
        for c in config.fixture_classes
        if PERTURBATION_REGISTRY[c].arity == "single"
    ]
    want_positive = "positive" in config.fixture_classes
    want_wrong_pair = "wrong_pair" in config.fixture_classes

    for depth in config.depths:
        positives_this_depth: list[tuple[str, dict, dict]] = []  # (source, e, c)

        for si, spec in enumerate(seed_specs):
            electric = spec.electric()
            base_id = f"{spec.source_name}_N{spec.N}_d{depth}_node{spec.node}"

            # Depth-1 positives whose seed has an irrational superconformal R
            # (dP_1 / Y^{p,q}): pick the consistent R rep so the magnetic R is
            # the exact duality image (TrR^3 / central charge match). Symmetric-R
            # seeds (dp0 / F_0 / C^3) are NOT shifted, so they fall through to the
            # locked chain path below byte-for-byte.
            consistent = (
                seiberg_dual_consistent(electric, spec.node) if depth == 1 else None
            )
            if (
                consistent is not None
                and consistent.ok
                and consistent.metadata.get("electric_r_shifted")
            ):
                chain_seed = _stable_seed(config.seed, depth, si, "chain")
                electric = consistent.electric
                positive_candidate = consistent.magnetic
                final_hash = canonical_theory_hash(positive_candidate)
                node_sequence: tuple[int, ...] = (int(spec.node),)
                depth_realized = 1
                intermediate_hashes = (canonical_theory_hash(electric), final_hash)
                chain_id = _chain_id(
                    spec.source_name, chain_seed, list(node_sequence), final_hash, 1
                )
                chain_seed_id: int = chain_seed
            else:
                chain = _attempt_chain(electric, depth, spec, si)
                if chain is None or not chain.success:
                    reason = (
                        chain.attrition_reason if chain is not None else "max_attempts_exceeded"
                    ) or "no_valid_mutation_nodes"
                    result.attrition.append(
                        AttritionRecord(
                            fixture_id=f"{base_id}_positive",
                            seed_id=(chain.seed_id if chain is not None else 0) or 0,
                            depth=depth,
                            perturbation_class="positive",
                            attrition_reason=reason,
                            detail=(
                                f"depth-{depth} chain failed: {reason} "
                                f"(realized {chain.depth_realized if chain else 0})"
                            ),
                            verifier_status=(
                                chain.verifier_status_seed_to_final if chain else None
                            ),
                            generation_metadata=_gen_meta(
                                (chain.seed_id if chain is not None else 0) or 0
                            ),
                            mutation_chain_id=chain.chain_id if chain is not None else None,
                            source=spec.source_name,
                        )
                    )
                    continue

                positive_candidate = chain.final_theory
                node_sequence = chain.node_sequence
                depth_realized = chain.depth_realized
                intermediate_hashes = chain.intermediate_hashes
                final_hash = chain.final_theory_hash
                chain_id = chain.chain_id
                chain_seed_id = chain.seed_id

            chain_fields = dict(
                chain_depth=depth_realized,
                mutation_node_sequence=node_sequence,
                intermediate_hashes=intermediate_hashes,
                final_theory_hash=final_hash,
            )
            pos_outcome = run_verifier(
                electric, positive_candidate, config.verifier, claim_name=base_id
            )
            if not pos_outcome.is_certified:
                reason = (
                    "unexpected_label"
                    if pos_outcome.in_scope
                    else pos_outcome.attrition_reason()
                )
                result.attrition.append(
                    AttritionRecord(
                        fixture_id=f"{base_id}_positive",
                        seed_id=chain_seed_id or 0,
                        depth=depth,
                        perturbation_class="positive",
                        attrition_reason=reason,
                        detail=(
                            pos_outcome.error
                            or f"positive expected CERTIFIED, got {pos_outcome.status}"
                        ),
                        verifier_status=pos_outcome.status,
                        generation_metadata=_gen_meta(chain_seed_id or 0),
                        mutation_chain_id=chain_id,
                        source=spec.source_name,
                    )
                )
                continue

            positives_this_depth.append(
                (spec.source_name, electric, positive_candidate)
            )

            if want_positive:
                _register(
                    class_name="positive",
                    electric=electric,
                    candidate=positive_candidate,
                    outcome=pos_outcome,
                    fixture_id=f"{base_id}_positive_00",
                    seed_id=_stable_seed(config.seed, depth, si, "positive", 0),
                    depth=depth,
                    source=spec.source_name,
                    chain_id=chain_id,
                    perturbation_metadata={
                        "mutation_node_sequence": list(node_sequence),
                        "mutation_depth": depth_realized,
                        "N": spec.N,
                    },
                    **chain_fields,
                )

            for cls in single_classes:
                pspec = PERTURBATION_REGISTRY[cls]
                for i in range(config.n_per_cell):
                    seed_i = _stable_seed(config.seed, depth, si, cls, i)
                    fid = f"{base_id}_{cls}_{i:02d}"
                    try:
                        edited, meta = apply_single_positive_edit(
                            cls, positive_candidate, Random(seed_i)
                        )
                    except PerturbationError as exc:
                        result.attrition.append(
                            AttritionRecord(
                                fixture_id=fid,
                                seed_id=seed_i,
                                depth=depth,
                                perturbation_class=cls,
                                attrition_reason="generator_discard",
                                detail=str(exc),
                                verifier_status=None,
                                generation_metadata=_gen_meta(seed_i),
                                mutation_chain_id=chain_id,
                                source=spec.source_name,
                            )
                        )
                        continue

                    outcome = run_verifier(
                        electric, edited, config.verifier, claim_name=fid
                    )
                    if not outcome.in_scope:
                        result.attrition.append(
                            AttritionRecord(
                                fixture_id=fid,
                                seed_id=seed_i,
                                depth=depth,
                                perturbation_class=cls,
                                attrition_reason=outcome.attrition_reason(),
                                detail=(
                                    outcome.error
                                    or f"out-of-scope verdict {outcome.status}"
                                ),
                                verifier_status=outcome.status,
                                generation_metadata=_gen_meta(seed_i),
                                mutation_chain_id=chain_id,
                                source=spec.source_name,
                            )
                        )
                        continue
                    if outcome.status != pspec.expected_label:
                        result.attrition.append(
                            AttritionRecord(
                                fixture_id=fid,
                                seed_id=seed_i,
                                depth=depth,
                                perturbation_class=cls,
                                attrition_reason="unexpected_label",
                                detail=(
                                    f"expected {pspec.expected_label}, "
                                    f"got {outcome.status} (silent miss)"
                                ),
                                verifier_status=outcome.status,
                                generation_metadata=_gen_meta(seed_i),
                                mutation_chain_id=chain_id,
                                source=spec.source_name,
                            )
                        )
                        continue

                    _register(
                        class_name=cls,
                        electric=electric,
                        candidate=edited,
                        outcome=outcome,
                        fixture_id=fid,
                        seed_id=seed_i,
                        depth=depth,
                        source=spec.source_name,
                        chain_id=chain_id,
                        perturbation_metadata=meta,
                        **chain_fields,
                    )

        if want_wrong_pair:
            _build_wrong_pairs(
                positives_this_depth,
                depth=depth,
                config=config,
                register=_register,
                attrition=result.attrition,
                gen_meta=_gen_meta,
            )

    # Strict completeness: every requested (depth x class) cell must have
    # produced at least one main fixture, else fail loudly (unless the
    # caller opted into incomplete coverage). This replaces the old
    # depth-preflight now that depth>=2 is actually attempted.
    empty = _empty_cells(config, result.manifest)
    if empty and not allow_incomplete:
        raise IncompleteCellsError(
            f"config '{config.name}': {len(empty)} requested (depth, class) "
            f"cell(s) produced zero main fixtures: {empty}. The physics / "
            "verifier scope rejected every attempt for these cells (see the "
            "attrition manifest for precise reasons). Pass "
            "allow_incomplete_cells=True to record honest attrition instead "
            "of failing."
        )

    if write:
        _write_outputs(config, result, out_dir_path)

    return result


def _empty_cells(
    config: ExperimentConfig, manifest: list[ManifestRecord]
) -> list[str]:
    """Requested (depth x class) cells with zero main-manifest fixtures."""

    filled = {(r.depth, r.perturbation_class) for r in manifest}
    missing = [
        f"d{depth}|{cls}"
        for depth in config.depths
        for cls in config.fixture_classes
        if (depth, cls) not in filled
    ]
    return sorted(missing)


# ----------------------------------------------------------------------
# Wrong-pair (cross-family) generation.
# ----------------------------------------------------------------------


def _build_wrong_pairs(
    positives: list[tuple[str, dict, dict]],
    *,
    depth: int,
    config: ExperimentConfig,
    register,
    attrition: list[AttritionRecord],
    gen_meta,
) -> None:
    by_family: dict[str, list[tuple[dict, dict]]] = {}
    for source, electric, candidate in positives:
        by_family.setdefault(source, []).append((electric, candidate))
    families = sorted(by_family)
    if len(families) < 2:
        return  # cannot form a cross-family wrong pair

    cross: list[tuple[dict, dict, str]] = []
    for fa, fb in combinations(families, 2):
        for electric_a, _ca in by_family[fa]:
            for _eb, candidate_b in by_family[fb]:
                cross.append((electric_a, candidate_b, f"{fa}_x_{fb}"))

    produced = 0
    for idx, (electric, candidate, source) in enumerate(cross):
        if produced >= config.n_per_cell:
            break
        fid = f"wrong_pair_d{depth}_{idx:03d}"
        seed_i = _stable_seed(config.seed, depth, "wrong_pair", idx)
        outcome = run_verifier(electric, candidate, config.verifier, claim_name=fid)
        if not outcome.in_scope:
            attrition.append(
                AttritionRecord(
                    fixture_id=fid,
                    seed_id=seed_i,
                    depth=depth,
                    perturbation_class="wrong_pair",
                    attrition_reason=outcome.attrition_reason(),
                    detail=outcome.error or f"out-of-scope verdict {outcome.status}",
                    verifier_status=outcome.status,
                    generation_metadata=gen_meta(seed_i),
                    source=source,
                )
            )
            continue
        if outcome.status != "FAILED":
            attrition.append(
                AttritionRecord(
                    fixture_id=fid,
                    seed_id=seed_i,
                    depth=depth,
                    perturbation_class="wrong_pair",
                    attrition_reason="unexpected_label",
                    detail=f"expected FAILED, got {outcome.status} (silent miss)",
                    verifier_status=outcome.status,
                    generation_metadata=gen_meta(seed_i),
                    source=source,
                )
            )
            continue
        rec = register(
            class_name="wrong_pair",
            electric=electric,
            candidate=candidate,
            outcome=outcome,
            fixture_id=fid,
            seed_id=seed_i,
            depth=depth,
            source=source,
            chain_id=None,
            perturbation_metadata={"cross_family": source},
            chain_depth=depth,
            final_theory_hash=canonical_theory_hash(candidate),
        )
        if rec is not None:
            produced += 1


# ----------------------------------------------------------------------
# Output writing + helpers.
# ----------------------------------------------------------------------


def _write_outputs(
    config: ExperimentConfig,
    result: GenerationResult,
    out_dir: Path,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_manifest_jsonl(out_dir / "manifest.jsonl", result.manifest)
    write_manifest_csv(out_dir / "manifest.csv", result.manifest)
    write_attrition_jsonl(out_dir / "attrition.jsonl", result.attrition)
    config.to_json_file(out_dir / "config.json")


def _write_theory(path: Path, theory_json: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(theory_json), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _pair_hash(
    electric: Mapping[str, Any], candidate: Mapping[str, Any]
) -> str:
    se = sanitize_for_prompt(dict(electric), theory_label="A")
    sc = sanitize_for_prompt(dict(candidate), theory_label="B")
    payload = json.dumps([se, sc], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _stable_seed(base: int, *parts: Any) -> int:
    """Deterministic 32-bit sub-seed from `base` and labels (run-stable)."""

    key = f"{base}:" + ":".join(str(p) for p in parts)
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode == 0:
            return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None
    return None
