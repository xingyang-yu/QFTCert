"""Endpoint-pool pair sampling (Phase 2d-ext).

The mutation engine is treated purely as a *benchmark generator*: the
benchmark task is endpoint QFTCert verification, not path reconstruction.
So fixtures need not always pair the seed `T0` with the chain end `T_K`.
Instead we build a pool of endpoint theories at depths 0..D per curated
seed (an "orbit"), then sample blind `(T_i, T_j)` pairs and verifier-gate
them.

pair_origin categories:
  - same_orbit_endpoint_pair  : (T_i, T_j) from one orbit -> positive iff CERTIFIED
  - perturbed_endpoint_pair   : a certified pair with one side perturbed -> FAILED negative
  - cross_orbit_pair          : different orbits -> FAILED negative
  - size_matched_cross_pair   : cross-orbit within size tolerance -> FAILED negative
  - wrong_pair                : legacy alias of cross-orbit
  - positive_seed_endpoint_pair : legacy (T0, T_K), handled by generation.py

Label source is always the endpoint verifier (`label_source="endpoint_qftcert"`).
Provenance (seed / depth / path / orbit) is recorded in the manifest's
`pair_metadata` but NEVER shown to the model (the runner sanitizes the two
theories at prompt time).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from random import Random
from typing import Any, Mapping

from dualitycert.experiments.chains import (
    apply_single_seiberg_mutation,
    canonical_theory_hash,
    theory_size,
)
from dualitycert.experiments.config import (
    EndpointPoolConfig,
    ExperimentConfig,
)
from dualitycert.experiments.manifest import (
    AttritionRecord,
    ManifestRecord,
    compute_size_covariates,
)
from dualitycert.experiments.perturbations import (
    PERTURBATION_REGISTRY,
    PerturbationError,
    apply_single_positive_edit,
)
from dualitycert.experiments.seeds import SeedSpec, default_seed_specs
from dualitycert.experiments.verifier import run_verifier


__all__ = [
    "EndpointTheory",
    "build_endpoint_pool",
    "generate_endpoint_pool_fixtures",
]


# The four repairable perturbation classes, cycled for perturbed negatives.
_PERTURB_CLASSES = ("drop_w_term", "flip_w_sign", "r_charge_perturb", "rank_perturb")


@dataclass(frozen=True)
class EndpointTheory:
    """One theory in the endpoint pool (mechanically reachable from a seed)."""

    theory_id: str
    seed_id: str
    orbit_id: str
    generation_depth: int
    mutation_sequence: tuple[int, ...]
    canonical_hash: str
    size_covariates: dict[str, int]
    theory: dict[str, Any]


# ----------------------------------------------------------------------
# Pool construction (mechanical; no verification).
# ----------------------------------------------------------------------


def build_endpoint_pool(
    seed_specs: list[SeedSpec],
    cfg: EndpointPoolConfig,
) -> list[EndpointTheory]:
    """Build the endpoint pool by mechanically expanding each seed orbit.

    Deterministic: nodes are visited in index order; theories are deduped
    by canonical hash within an orbit; expansion stops at
    `max_pool_depth` or `max_endpoints_per_orbit`. No verifier is called —
    labels are decided later, at pairing.
    """

    # Distinct seed theories (an orbit per (source, N)); ignore spec.node
    # here — the pool explores all legal nodes.
    orbit_seeds: dict[str, dict[str, Any]] = {}
    for spec in seed_specs:
        orbit_id = f"{spec.source_name}_N{spec.N}"
        orbit_seeds.setdefault(orbit_id, spec.electric())

    pool: list[EndpointTheory] = []
    for orbit_id, T0 in orbit_seeds.items():
        seen: set[str] = set()

        def _add(theory: dict[str, Any], depth: int, seq: list[int]):
            h = canonical_theory_hash(theory)
            if h in seen or len(seen) >= cfg.max_endpoints_per_orbit:
                return None
            seen.add(h)
            et = EndpointTheory(
                theory_id=f"{orbit_id}#d{depth}#{h[:10]}",
                seed_id=orbit_id,
                orbit_id=orbit_id,
                generation_depth=depth,
                mutation_sequence=tuple(seq),
                canonical_hash=h,
                size_covariates=theory_size(theory),
                theory=theory,
            )
            pool.append(et)
            return et

        _add(T0, 0, [])
        frontier: list[tuple[dict[str, Any], list[int]]] = [(T0, [])]
        for d in range(1, cfg.max_pool_depth + 1):
            next_frontier: list[tuple[dict[str, Any], list[int]]] = []
            for theory, seq in frontier:
                if len(seen) >= cfg.max_endpoints_per_orbit:
                    break
                for node in range(len(theory["ranks"])):
                    smr = apply_single_seiberg_mutation(theory, node)
                    if not smr.ok:
                        continue
                    et = _add(smr.theory, d, seq + [node])
                    if et is not None:
                        next_frontier.append((smr.theory, seq + [node]))
                    if len(seen) >= cfg.max_endpoints_per_orbit:
                        break
            frontier = next_frontier
    return pool


# ----------------------------------------------------------------------
# Fixture generation from the pool.
# ----------------------------------------------------------------------


def generate_endpoint_pool_fixtures(
    config: ExperimentConfig,
    *,
    out_dir: Path | str,
    seed_specs: list[SeedSpec] | None = None,
    generated_at: str = "",
    git_commit: str | None = None,
    generator_version: str = "qftcert-experiments/0.1",
    write: bool = True,
) -> tuple[list[ManifestRecord], list[AttritionRecord]]:
    """Sample + verifier-gate blind endpoint pairs into manifest/attrition.

    Returns `(manifest, attrition)`. Theory files are written under
    `<out_dir>/theories/` when `write=True`. The top-level manifest/CSV
    files are written by the caller (`generation.generate_fixtures`).
    """

    seed_specs = seed_specs if seed_specs is not None else default_seed_specs()
    ep = config.endpoint_pool
    out_dir = Path(out_dir)
    theories_dir = out_dir / "theories"

    pool = build_endpoint_pool(seed_specs, ep)
    by_orbit: dict[str, list[EndpointTheory]] = {}
    for et in pool:
        by_orbit.setdefault(et.orbit_id, []).append(et)

    rng = Random(_stable_seed(config.seed, "endpoint_pool"))
    manifest: list[ManifestRecord] = []
    attrition: list[AttritionRecord] = []
    seen_pair_keys: set[tuple[str, str]] = set()
    per_theory_count: dict[str, int] = {}
    per_orbit_count: dict[str, int] = {}
    orient_toggle = {"v": False}
    gen_meta_base = {
        "generated_at": generated_at,
        "generator_version": generator_version,
        "git_commit": git_commit,
    }

    def _budget_ok(a_id: str, b_id: str, orbit_key: str) -> bool:
        if per_orbit_count.get(orbit_key, 0) >= ep.max_pairs_per_orbit:
            return False
        if per_theory_count.get(a_id, 0) >= ep.max_pairs_per_theory:
            return False
        if per_theory_count.get(b_id, 0) >= ep.max_pairs_per_theory:
            return False
        return True

    def _emit(
        *,
        a_theory: dict[str, Any],
        b_theory: dict[str, Any],
        a_meta: dict[str, Any],
        b_meta: dict[str, Any],
        pair_origin: str,
        perturbation_class: str,
        expected_label: str,
        perturbation_metadata: Mapping[str, Any] | None = None,
        fixture_seed: int = 0,
    ) -> ManifestRecord | None:
        ha = canonical_theory_hash(a_theory)
        hb = canonical_theory_hash(b_theory)
        # Sampling-control skips (not attrition).
        if not ep.allow_same_hash_pair and ha == hb:
            return None
        if not ep.allow_same_theory_pair and a_meta["theory_id"] == b_meta["theory_id"]:
            return None
        pair_key = tuple(sorted((ha, hb)))
        if pair_key in seen_pair_keys:
            return None
        seen_pair_keys.add(pair_key)

        orbit_key = f"{a_meta['orbit_id']}|{b_meta['orbit_id']}"
        if not _budget_ok(a_meta["theory_id"], b_meta["theory_id"], orbit_key):
            return None

        # Orientation: balance A/B order (exact alternation) so the
        # lower-depth / seed theory is not always side A.
        swap = False
        if ep.balance_pair_orientation:
            swap = orient_toggle["v"]
            orient_toggle["v"] = not orient_toggle["v"]
        if swap:
            da_theory, db_theory = b_theory, a_theory
            da_meta, db_meta = b_meta, a_meta
        else:
            da_theory, db_theory = a_theory, b_theory
            da_meta, db_meta = a_meta, b_meta

        fid = f"ep_{pair_origin}_{ha[:6]}_{hb[:6]}"
        outcome = run_verifier(da_theory, db_theory, config.verifier, claim_name=fid)

        depth_a = int(da_meta["generation_depth"])
        depth_b = int(db_meta["generation_depth"])
        pair_meta = {
            "theory_id_a": da_meta["theory_id"],
            "theory_id_b": db_meta["theory_id"],
            "seed_id_a": da_meta["seed_id"],
            "seed_id_b": db_meta["seed_id"],
            "orbit_id_a": da_meta["orbit_id"],
            "orbit_id_b": db_meta["orbit_id"],
            "generation_depth_a": depth_a,
            "generation_depth_b": depth_b,
            "pair_generation_depth_max": max(depth_a, depth_b),
            "pair_generation_depth_sum": depth_a + depth_b,
            "pair_generation_depth_delta": abs(depth_a - depth_b),
            "pair_origin": pair_origin,
            "label_source": "endpoint_qftcert",
            "generation_history_shown_to_model": False,
            "pair_swapped": bool(swap),
            "mutation_sequence_a": list(da_meta.get("mutation_sequence", ())),
            "mutation_sequence_b": list(db_meta.get("mutation_sequence", ())),
        }
        gen_meta = {"rng_seed": int(fixture_seed), **gen_meta_base}

        if not outcome.in_scope:
            attrition.append(
                AttritionRecord(
                    fixture_id=fid,
                    seed_id=int(fixture_seed),
                    depth=max(depth_a, depth_b),
                    perturbation_class=perturbation_class,
                    attrition_reason=outcome.attrition_reason(),
                    detail=outcome.error or f"out-of-scope verdict {outcome.status}",
                    verifier_status=outcome.status,
                    generation_metadata=gen_meta,
                    source=orbit_key,
                )
            )
            return None
        if outcome.status != expected_label:
            attrition.append(
                AttritionRecord(
                    fixture_id=fid,
                    seed_id=int(fixture_seed),
                    depth=max(depth_a, depth_b),
                    perturbation_class=perturbation_class,
                    attrition_reason="unexpected_label",
                    detail=(
                        f"{pair_origin} expected {expected_label}, "
                        f"got {outcome.status}"
                    ),
                    verifier_status=outcome.status,
                    generation_metadata=gen_meta,
                    source=orbit_key,
                )
            )
            return None

        a_rel = f"theories/{fid}.A.json"
        b_rel = f"theories/{fid}.B.json"
        if write:
            _write_theory(theories_dir / f"{fid}.A.json", da_theory)
            _write_theory(theories_dir / f"{fid}.B.json", db_theory)

        spec = PERTURBATION_REGISTRY.get(perturbation_class)
        repairable = bool(spec and spec.repairable and outcome.status == "FAILED")
        record = ManifestRecord(
            fixture_id=fid,
            seed_id=int(fixture_seed),
            depth=max(depth_a, depth_b),
            perturbation_class=perturbation_class,
            label=outcome.status,
            repairable=repairable,
            theory_a_path=a_rel,
            theory_b_path=b_rel,
            sanitized=False,
            verifier_status=outcome.status,
            failed_obligations=outcome.failed_obligations,
            verifier_config_hash=config.verifier.config_hash(),
            verifier_config=config.verifier.to_dict(),
            size_covariates=compute_size_covariates(db_theory, electric=da_theory),
            generation_metadata=gen_meta,
            perturbation_metadata=dict(perturbation_metadata or {}),
            chain_depth=max(depth_a, depth_b),
            mutation_node_sequence=tuple(db_meta.get("mutation_sequence", ())),
            final_theory_hash=hb if not swap else ha,
            pair_metadata=pair_meta,
            source=orbit_key,
            split=config.split,
        )
        manifest.append(record)
        per_theory_count[a_meta["theory_id"]] = (
            per_theory_count.get(a_meta["theory_id"], 0) + 1
        )
        per_theory_count[b_meta["theory_id"]] = (
            per_theory_count.get(b_meta["theory_id"], 0) + 1
        )
        per_orbit_count[orbit_key] = per_orbit_count.get(orbit_key, 0) + 1
        return record

    def _meta(et: EndpointTheory) -> dict[str, Any]:
        return {
            "theory_id": et.theory_id,
            "seed_id": et.seed_id,
            "orbit_id": et.orbit_id,
            "generation_depth": et.generation_depth,
            "mutation_sequence": et.mutation_sequence,
        }

    # 1. same-orbit positives (CERTIFIED), collecting certified pairs.
    certified_pairs: list[tuple[EndpointTheory, EndpointTheory]] = []
    want_same = "same_orbit_endpoint_pair" in ep.pair_origins
    want_perturbed = "perturbed_endpoint_pair" in ep.pair_origins
    if want_same or want_perturbed:
        for orbit_id, members in sorted(by_orbit.items()):
            pairs = list(combinations(members, 2))
            # Prefer cross-depth pairs first when balancing depth.
            if ep.balance_depth_pairs:
                pairs.sort(
                    key=lambda p: (
                        -abs(p[0].generation_depth - p[1].generation_depth),
                        p[0].theory_id,
                        p[1].theory_id,
                    )
                )
            for a, b in pairs:
                rec = _emit(
                    a_theory=a.theory,
                    b_theory=b.theory,
                    a_meta=_meta(a),
                    b_meta=_meta(b),
                    pair_origin="same_orbit_endpoint_pair",
                    perturbation_class="positive",
                    expected_label="CERTIFIED",
                    fixture_seed=_stable_seed(config.seed, "same", a.theory_id, b.theory_id),
                )
                if rec is not None:
                    certified_pairs.append((a, b))

    # 2. perturbed negatives from certified same-orbit pairs.
    if want_perturbed:
        for idx, (a, b) in enumerate(certified_pairs):
            for k in range(ep.n_perturbed_per_certified):
                cls = _PERTURB_CLASSES[(idx + k) % len(_PERTURB_CLASSES)]
                pert_seed = _stable_seed(config.seed, "perturb", a.theory_id, b.theory_id, k)
                try:
                    edited, meta = apply_single_positive_edit(
                        cls, b.theory, Random(pert_seed)
                    )
                except PerturbationError:
                    continue
                b_meta = _meta(b)
                b_meta["theory_id"] = f"{b.theory_id}+{cls}"
                _emit(
                    a_theory=a.theory,
                    b_theory=edited,
                    a_meta=_meta(a),
                    b_meta=b_meta,
                    pair_origin="perturbed_endpoint_pair",
                    perturbation_class=cls,
                    expected_label="FAILED",
                    perturbation_metadata=meta,
                    fixture_seed=pert_seed,
                )

    # 3. cross-orbit negatives (+ size-matched subset).
    want_cross = "cross_orbit_pair" in ep.pair_origins
    want_size = "size_matched_cross_pair" in ep.pair_origins
    want_wrong = "wrong_pair" in ep.pair_origins
    if want_cross or want_size or want_wrong:
        orbits = sorted(by_orbit)
        for oa, ob in combinations(orbits, 2):
            for a in by_orbit[oa]:
                for b in by_orbit[ob]:
                    delta = abs(
                        a.size_covariates["n_fields"] - b.size_covariates["n_fields"]
                    )
                    if delta <= ep.size_match_tolerance:
                        origin = "size_matched_cross_pair"
                    else:
                        origin = "cross_orbit_pair"
                    if origin not in ep.pair_origins:
                        # fall back to wrong_pair alias if requested
                        if want_wrong:
                            origin = "wrong_pair"
                        else:
                            continue
                    _emit(
                        a_theory=a.theory,
                        b_theory=b.theory,
                        a_meta=_meta(a),
                        b_meta=_meta(b),
                        pair_origin=origin,
                        perturbation_class="wrong_pair",
                        expected_label="FAILED",
                        fixture_seed=_stable_seed(
                            config.seed, "cross", a.theory_id, b.theory_id
                        ),
                    )

    return manifest, attrition


# ----------------------------------------------------------------------
# Helpers.
# ----------------------------------------------------------------------


def _write_theory(path: Path, theory_json: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(theory_json), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _stable_seed(base: int, *parts: Any) -> int:
    key = f"{base}:" + ":".join(str(p) for p in parts)
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16)
