"""Mutation-chain runner interface (Deliverable 3).

The eventual interface the paper wants is::

    generate_mutation_chain(seed_theory, depth, rng, constraints)
        -> MutationChainResult

with the final theory, the sequence of mutation node IDs, intermediate
theories, an in-scope flag, and dedup metadata.

Today the single-node Seiberg engine (`dualitycert.qft.mutation_engine`)
supports exactly one mutation step, so:

  - depth == 1 is wired end-to-end (mutate -> integrate -> R-repair);
  - depth >= 2 raises `DepthNotImplementedError`. We deliberately do NOT
    fabricate deep chains — generation catches this and routes the cell
    to the attrition manifest with reason "depth_not_implemented".

When the engine grows multi-step support, only the depth >= 2 branch
here changes; configs already request depths [1, 2, 3, 4].
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from dualitycert.benchmark.fixtures import sanitize_for_prompt
from dualitycert.qft.mutation_engine import (
    MutationEngineError,
    integrate_linear_fields,
    mutate_bare,
)
from dualitycert.qft.r_repair import RRepairError, repair_r_charges


__all__ = [
    "ChainConstructionError",
    "DepthNotImplementedError",
    "MutationChainResult",
    "canonical_theory_hash",
    "generate_mutation_chain",
]


class DepthNotImplementedError(NotImplementedError):
    """Requested mutation depth exceeds the engine's current capability."""


class ChainConstructionError(ValueError):
    """The chain could not be built (infeasible R-repair, engine refusal)."""


@dataclass(frozen=True)
class MutationChainResult:
    """Outcome of building one Seiberg mutation chain from a seed theory."""

    final_theory: dict[str, Any]
    node_sequence: tuple[int, ...]
    intermediate_theories: tuple[dict[str, Any], ...]
    in_scope: bool
    chain_id: str
    canonical_hash: str
    duplicate_of: str | None = None


def canonical_theory_hash(theory_json: Mapping[str, Any]) -> str:
    """Provenance-independent fingerprint of a theory's physics content.

    Hashes the sanitized form (name + node_labels neutralized) so two
    theories that differ only in human-readable provenance collapse to
    the same hash — the right granularity for dedup.
    """

    sanitized = sanitize_for_prompt(dict(theory_json), theory_label="T")
    payload = json.dumps(sanitized, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generate_mutation_chain(
    seed_theory: Mapping[str, Any],
    depth: int,
    rng: Any,
    *,
    source_name: str = "",
    node: int | None = None,
    constraints: Mapping[str, Any] | None = None,
) -> MutationChainResult:
    """Build a Seiberg mutation chain of the requested `depth` from a seed.

    `rng` is accepted for forward-compat (depth >= 2 will choose a random
    mutation sequence); at depth 1 the chain is deterministic given
    `(seed_theory, node)`, so `rng` is unused. `node` (or
    `constraints["node"]`, default 0) selects the gauge node to dualize.
    """

    if depth < 1:
        raise ValueError(f"depth must be >= 1; got {depth!r}")
    if depth >= 2:
        raise DepthNotImplementedError(
            f"mutation chain depth {depth} is not implemented: the single-node "
            "Seiberg engine supports depth=1 only. Configs may request higher "
            "depths; generation routes them to attrition until the engine "
            "supports multi-step chains."
        )

    constraints = dict(constraints or {})
    if node is None:
        node = int(constraints.get("node", 0))

    try:
        bare = mutate_bare(dict(seed_theory), node=node)
        integrated = integrate_linear_fields(bare)
        repaired = repair_r_charges(integrated)
    except (MutationEngineError, RRepairError) as exc:
        raise ChainConstructionError(str(exc)) from exc

    if repaired["status"] == "infeasible":
        raise ChainConstructionError(
            f"R-repair infeasible for depth-1 chain at node {node}: "
            f"{repaired['failure_reason']}"
        )

    final_theory = repaired["representative"]
    chain_id = f"{source_name or 'seed'}:d1:node{node}"
    return MutationChainResult(
        final_theory=final_theory,
        node_sequence=(int(node),),
        intermediate_theories=(bare, integrated),
        in_scope=True,
        chain_id=chain_id,
        canonical_hash=canonical_theory_hash(final_theory),
    )
