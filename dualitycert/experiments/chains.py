"""Depth-K Seiberg mutation chain-runner (Phase 2d).

Composes K valid single-node Seiberg moves from a seed theory T0 to a
final theory T_K, verifier-gating adjacent steps and the seed-to-final
pair. The single-step move reuses the existing engine
(`dualitycert.qft.mutation_engine` + `r_repair`); the depth-1 path is a
special case of the same composition, so the locked MVP depth-1 fixtures
are reproduced.

Terminology: ``depth`` / ``generated_depth`` is the CHAIN LENGTH (number
of single-node moves applied) — NOT a proven minimal mutation distance.
We make no shortest-path / minimal-duality-depth claim. Records expose it
as ``depth_requested`` / ``depth_realized``.

The runner RETURNS a `MutationChainResult` with `success=False` and a
precise `attrition_reason` on failure (it does not raise for physics /
verifier rejections), so the generation pipeline can record honest
attrition. It only raises `ValueError` for nonsensical input (depth < 1).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from random import Random
from typing import Any, Mapping

from dualitycert.benchmark.fixtures import sanitize_for_prompt
from dualitycert.experiments.config import ChainConfig, VerifierConfig
from dualitycert.experiments.verifier import run_verifier
from dualitycert.qft.mutation_engine import (
    MutationEngineError,
    integrate_fields,
    mutate_bare,
)
from dualitycert.qft.pure_quiver_json import (
    PureQuiverJSONError,
    pure_quiver_from_json,
)
from dualitycert.qft.r_repair import RRepairError, repair_r_charges


__all__ = [
    "ChainConstructionError",
    "DepthNotImplementedError",
    "MutationChainResult",
    "MutationStep",
    "SingleMutationResult",
    "apply_single_seiberg_mutation",
    "canonical_theory_hash",
    "generate_mutation_chain",
    "legal_mutation_nodes",
    "theory_size",
]


# Retained for backward-compatibility of imports; the chain-runner no
# longer raises this (depth >= 2 is implemented). It is unused by the
# current pipeline but kept so any external caller importing it does not
# break.
class DepthNotImplementedError(NotImplementedError):
    """Deprecated: depth >= 2 is now implemented by the chain-runner."""


class ChainConstructionError(ValueError):
    """Raised only for nonsensical input (e.g. depth < 1)."""


# ----------------------------------------------------------------------
# Single-step Seiberg move (reused by depth-1 and the chain-runner).
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class SingleMutationResult:
    """Outcome of one single-node Seiberg move (mutate -> integrate -> repair)."""

    ok: bool
    node: int
    theory: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    reason: str | None = None  # attrition-vocabulary reason when not ok


def apply_single_seiberg_mutation(
    theory: Mapping[str, Any],
    node: int,
    rng: Any | None = None,
    *,
    options: Mapping[str, Any] | None = None,
) -> SingleMutationResult:
    """Apply one single-node Seiberg duality move at `node`.

    Pipeline (identical to the locked depth-1 positive generation):
    `mutate_bare` -> `integrate_fields` -> `repair_r_charges`,
    returning the L2-nearest feasible representative. Deterministic given
    `(theory, node)`; `rng` / `options` are accepted for interface
    stability and currently unused.

    On any engine refusal or infeasible R-repair, returns
    ``ok=False`` with ``reason="single_step_mutation_failed"`` rather than
    raising, so the chain-runner can try another node.
    """

    try:
        bare = mutate_bare(dict(theory), node=node)
        integrated = integrate_fields(bare)
        repaired = repair_r_charges(integrated)
    except (MutationEngineError, RRepairError) as exc:
        return SingleMutationResult(
            ok=False,
            node=node,
            error=str(exc),
            reason="single_step_mutation_failed",
        )

    if repaired["status"] == "infeasible":
        return SingleMutationResult(
            ok=False,
            node=node,
            error=str(repaired.get("failure_reason")),
            reason="single_step_mutation_failed",
        )

    final = repaired["representative"]
    metadata = {
        "node": int(node),
        "magnetic_rank": int(final["ranks"][node]),
        "n_changed_r_fields": len(repaired.get("changed_fields", [])),
        "r_repair_status": repaired.get("status"),
    }
    return SingleMutationResult(ok=True, node=node, theory=final, metadata=metadata)


def legal_mutation_nodes(theory: Mapping[str, Any]) -> list[int]:
    """Nodes at which a single Seiberg move succeeds (full pipeline).

    Used by tests / introspection; the chain-runner enumerates lazily.
    """

    return [
        n
        for n in range(len(theory["ranks"]))
        if apply_single_seiberg_mutation(theory, n).ok
    ]


# ----------------------------------------------------------------------
# Chain data structures.
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class MutationStep:
    """One accepted step in a mutation chain."""

    step_index: int
    mutated_node_current_id: int
    pre_theory_hash: str
    post_theory_hash: str
    mutation_metadata: dict[str, Any]
    adjacent_verifier_status: str | None = None
    # Node indices are stable across single-node moves (no node is
    # added/removed), so the original id equals the current id.
    mutated_node_original_id: int | None = None
    rejected_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_index": self.step_index,
            "mutated_node_current_id": self.mutated_node_current_id,
            "mutated_node_original_id": (
                self.mutated_node_original_id
                if self.mutated_node_original_id is not None
                else self.mutated_node_current_id
            ),
            "pre_theory_hash": self.pre_theory_hash,
            "post_theory_hash": self.post_theory_hash,
            "mutation_metadata": dict(self.mutation_metadata),
            "adjacent_verifier_status": self.adjacent_verifier_status,
            "rejected_reason": self.rejected_reason,
        }


@dataclass(frozen=True)
class MutationChainResult:
    """Outcome of building one Seiberg mutation chain from a seed theory."""

    success: bool
    chain_id: str
    depth_requested: int
    depth_realized: int
    node_sequence: tuple[int, ...]
    theories: tuple[dict[str, Any], ...]  # T0 .. T_realized
    intermediate_hashes: tuple[str, ...]  # h0 .. h_realized
    final_theory: dict[str, Any] | None
    canonical_hash: str
    in_scope: bool
    steps: tuple[MutationStep, ...] = ()
    verifier_status_adjacent_steps: tuple[str | None, ...] = ()
    verifier_status_seed_to_final: str | None = None
    size_covariates: tuple[dict[str, Any], ...] = ()
    seed_id: int | None = None
    attrition_reason: str | None = None
    duplicate_of: str | None = None

    # --- back-compat / alias accessors -------------------------------

    @property
    def mutation_node_sequence(self) -> tuple[int, ...]:
        return self.node_sequence

    @property
    def final_theory_hash(self) -> str:
        return self.canonical_hash

    @property
    def stayed_in_scope(self) -> bool:
        return self.in_scope

    @property
    def intermediate_theories(self) -> tuple[dict[str, Any], ...]:
        """All chain theories T0..T_realized (back-compat name)."""

        return self.theories


# ----------------------------------------------------------------------
# Hashing + size.
# ----------------------------------------------------------------------


def canonical_theory_hash(theory_json: Mapping[str, Any]) -> str:
    """Provenance-independent fingerprint of a theory's physics content.

    Hashes the sanitized form (name + node_labels neutralized) so two
    theories that differ only in provenance collapse to the same hash.

    LIMITATION: this is a normalized-JSON hash, NOT a graph-isomorphism
    canonical form. Two theories that are isomorphic under a non-trivial
    node/arrow relabeling can still hash differently, so dedup here is
    sound (no false merges) but not complete (may keep isomorphic dups).
    """

    sanitized = sanitize_for_prompt(dict(theory_json), theory_label="T")
    payload = json.dumps(sanitized, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def theory_size(theory_json: Mapping[str, Any]) -> dict[str, int]:
    """Coarse size metrics used for budget checks + covariates."""

    arrows = theory_json.get("arrows", [])
    superpotential = theory_json.get("superpotential", [])
    token_estimate = len(json.dumps(dict(theory_json), sort_keys=True)) // 4
    return {
        "n_gauge_nodes": len(theory_json.get("ranks", [])),
        "n_fields": len(arrows),
        "n_superpotential_terms": len(superpotential),
        "json_token_estimate": token_estimate,
    }


def _exceeds_size(theory: Mapping[str, Any], cfg: ChainConfig) -> bool:
    s = theory_size(theory)
    return (
        s["n_gauge_nodes"] > cfg.max_gauge_nodes
        or s["n_fields"] > cfg.max_fields
        or s["n_superpotential_terms"] > cfg.max_superpotential_terms
        or s["json_token_estimate"] > cfg.max_json_token_estimate
    )


def _schema_ok(theory: Mapping[str, Any]) -> bool:
    try:
        pure_quiver_from_json(dict(theory))
    except (PureQuiverJSONError, ValueError, KeyError, TypeError):
        return False
    return True


def _node_order(n_nodes: int, rng: Any, prefer: int | None) -> list[int]:
    """Deterministic node visit order; `prefer` (if valid) goes first."""

    nodes = list(range(n_nodes))
    if isinstance(rng, Random):
        rng.shuffle(nodes)
    if prefer is not None and 0 <= prefer < n_nodes:
        nodes = [prefer] + [n for n in nodes if n != prefer]
    return nodes


# ----------------------------------------------------------------------
# Chain-runner.
# ----------------------------------------------------------------------


def generate_mutation_chain(
    seed_theory: Mapping[str, Any],
    depth: int,
    rng: Any,
    constraints: ChainConfig | Mapping[str, Any] | None = None,
    *,
    verifier_config: VerifierConfig | None = None,
    source_name: str = "",
    node: int | None = None,
    seed_id: int | None = None,
    step_fn: Any | None = None,
    verify_fn: Any | None = None,
    schema_fn: Any | None = None,
) -> MutationChainResult:
    """Build a length-`depth` Seiberg mutation chain from `seed_theory`.

    Composes `depth` single-node moves. At each step a node is chosen
    deterministically (using `rng`; the first step prefers `node` when
    given, so depth-1 reproduces the pinned MVP positives). A step is
    rejected — and another node tried — if the move fails, immediately
    backtracks (T_i == T_{i-2}), repeats an earlier state, exceeds the
    size budget, is schema-invalid, or fails adjacent verification.

    Returns a `MutationChainResult`; on any failure `success=False` and
    `attrition_reason` names the precise cause (it does not raise).
    """

    if depth < 1:
        raise ChainConstructionError(f"depth must be >= 1; got {depth!r}")

    cfg = (
        constraints
        if isinstance(constraints, ChainConfig)
        else ChainConfig.from_dict(dict(constraints or {}))
    )
    vcfg = verifier_config or VerifierConfig()
    # Test-injection hooks: stub the single-step move / verifier / schema
    # check to unit-test the composition logic without real physics.
    _step = step_fn or apply_single_seiberg_mutation
    _verify = verify_fn or run_verifier
    _schema = schema_fn or _schema_ok

    T0 = dict(seed_theory)
    theories: list[dict[str, Any]] = [T0]
    hashes: list[str] = [canonical_theory_hash(T0)]
    node_seq: list[int] = []
    steps: list[MutationStep] = []
    adjacent_status: list[str | None] = []

    def _fail(reason: str) -> MutationChainResult:
        realized = len(node_seq)
        return MutationChainResult(
            success=False,
            chain_id=_chain_id(source_name, seed_id, node_seq, hashes[-1], depth),
            depth_requested=depth,
            depth_realized=realized,
            node_sequence=tuple(node_seq),
            theories=tuple(theories) if cfg.save_intermediate_theories else (),
            intermediate_hashes=tuple(hashes),
            final_theory=None,
            canonical_hash="",
            in_scope=False,
            steps=tuple(steps),
            verifier_status_adjacent_steps=tuple(adjacent_status),
            verifier_status_seed_to_final=None,
            size_covariates=tuple(theory_size(t) for t in theories),
            seed_id=seed_id,
            attrition_reason=reason,
        )

    current = T0
    for i in range(1, depth + 1):
        order = _node_order(len(current["ranks"]), rng, prefer=node if i == 1 else None)
        last_reject: str | None = None
        accepted: tuple[dict[str, Any], MutationStep, str, str | None] | None = None
        attempts = 0

        for n in order:
            if attempts >= cfg.max_attempts_per_step:
                break
            attempts += 1

            smr = _step(current, n, rng)
            if not smr.ok:
                last_reject = smr.reason or "single_step_mutation_failed"
                continue
            cand = smr.theory
            chash = canonical_theory_hash(cand)

            if (
                cfg.forbid_immediate_backtracking
                and len(hashes) >= 2
                and chash == hashes[-2]
            ):
                last_reject = "immediate_backtracking_rejected"
                continue
            if (not cfg.allow_repeated_states) and chash in hashes:
                last_reject = "repeated_state_rejected"
                continue
            if _exceeds_size(cand, cfg):
                last_reject = "exceeds_size_budget"
                continue
            if not _schema(cand):
                last_reject = "intermediate_schema_invalid"
                continue

            adj_status: str | None = None
            if cfg.verify_adjacent_steps:
                adj = _verify(current, cand, vcfg)
                adj_status = adj.status
                if not adj.is_certified:
                    last_reject = (
                        "adjacent_verifier_failed"
                        if adj.is_failed
                        else "adjacent_verifier_unknown"
                    )
                    continue

            step = MutationStep(
                step_index=i,
                mutated_node_current_id=n,
                mutated_node_original_id=n,
                pre_theory_hash=hashes[-1],
                post_theory_hash=chash,
                mutation_metadata=dict(smr.metadata),
                adjacent_verifier_status=adj_status,
            )
            accepted = (cand, step, chash, adj_status)
            break

        if accepted is None:
            return _fail(last_reject or "no_valid_mutation_nodes")

        cand, step, chash, adj_status = accepted
        theories.append(cand)
        hashes.append(chash)
        node_seq.append(step.mutated_node_current_id)
        steps.append(step)
        adjacent_status.append(adj_status)
        current = cand

    final = current
    seed_to_final_status: str | None = None
    if cfg.verify_seed_to_final:
        out = _verify(T0, final, vcfg)
        seed_to_final_status = out.status
        if not out.is_certified:
            res = _fail(
                "final_verifier_failed" if out.is_failed else "final_verifier_unknown"
            )
            # _fail sets final_theory=None; re-attach the final + status so
            # callers can inspect what was rejected.
            return MutationChainResult(
                success=False,
                chain_id=res.chain_id,
                depth_requested=depth,
                depth_realized=len(node_seq),
                node_sequence=tuple(node_seq),
                theories=tuple(theories) if cfg.save_intermediate_theories else (),
                intermediate_hashes=tuple(hashes),
                final_theory=final,
                canonical_hash=hashes[-1],
                in_scope=False,
                steps=tuple(steps),
                verifier_status_adjacent_steps=tuple(adjacent_status),
                verifier_status_seed_to_final=seed_to_final_status,
                size_covariates=tuple(theory_size(t) for t in theories),
                seed_id=seed_id,
                attrition_reason=res.attrition_reason,
            )

    return MutationChainResult(
        success=True,
        chain_id=_chain_id(source_name, seed_id, node_seq, hashes[-1], depth),
        depth_requested=depth,
        depth_realized=len(node_seq),
        node_sequence=tuple(node_seq),
        theories=tuple(theories) if cfg.save_intermediate_theories else (T0, final),
        intermediate_hashes=tuple(hashes),
        final_theory=final,
        canonical_hash=hashes[-1],
        in_scope=True,
        steps=tuple(steps),
        verifier_status_adjacent_steps=tuple(adjacent_status),
        verifier_status_seed_to_final=seed_to_final_status,
        size_covariates=tuple(theory_size(t) for t in theories),
        seed_id=seed_id,
    )


def _chain_id(
    source_name: str,
    seed_id: int | None,
    node_seq,
    final_hash: str,
    depth: int,
) -> str:
    """Stable chain id from seed, depth, node sequence, and final hash."""

    seq = "-".join(str(n) for n in node_seq) or "none"
    sid = "seed" if seed_id is None else str(seed_id)
    src = source_name or "seed"
    return f"{src}:s{sid}:d{depth}:nodes[{seq}]:{final_hash[:12]}"
