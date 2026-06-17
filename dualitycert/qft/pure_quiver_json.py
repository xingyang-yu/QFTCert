"""JSON I/O for pure-quiver theories (Phase 2c0 MVP).

The mutation engine operates on dict / JSON-compatible structures so it
stays independent of the verifier. This module is the bridge between
those dicts and the in-memory `Theory` objects the verifier consumes.

Schema (see `docs/phase2c0_mutation_engine.md` §1):

    {
      "name": str,
      "node_labels": [str, ...],
      "ranks": [int, ...],
      "u1_globals": ["U(1)_R"]  # MVP only supports this exact entry
      "arrows": [
        {"label": str, "source": int, "target": int, "r_charge": str},
        ...
      ],
      "superpotential": [
        {"factors": [str, ...], "coefficient": str},
        ...
      ]
    }

Conventions:
  - One arrow entry per copy (multiplicity-1 builder convention).
  - `label` must match what `build_pure_quiver` would auto-generate for
    that `(source, target)` edge given the arrow's position within the
    sorted-edges expansion. The round-trip enforces this.
  - `r_charge` and `coefficient` are encoded as strings to keep them
    rational across serialization (Fraction parses them losslessly).
  - `superpotential.factors` is a flattened sequence of machine labels
    (powers represented by repetition; mirrors
    `SuperpotentialTerm.field_names`).
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any, Mapping

from dualitycert.core.objects import (
    Field,
    SuperpotentialTerm,
    Theory,
    as_r_charge,
)
from dualitycert.groups.u1 import u1_r
from dualitycert.qft.pure_quiver_builder import arrow_names, build_pure_quiver


SUPPORTED_U1_GLOBALS: frozenset[str] = frozenset({"U(1)_R"})


class PureQuiverJSONError(ValueError):
    """Raised when the JSON payload is malformed for a pure-quiver."""


def pure_quiver_to_json(theory: Theory) -> dict[str, Any]:
    """Serialize a pure-quiver `Theory` to a JSON-compatible dict.

    Assumes the theory was produced by `build_pure_quiver` (every Field
    has multiplicity=1, names follow `X{i}{j}[k]` / `Phi{i}[k]`, only
    U(1)_R is attached as a global). For anything broader, the JSON
    cannot be reconstructed back through `build_pure_quiver` with
    matching labels — the caller should bend the theory builder.
    """

    node_labels = tuple(node.label for node in theory.gauge_nodes)
    ranks = [node.N for node in theory.gauge_nodes]

    arrows_payload: list[dict[str, Any]] = []
    singlets_payload: list[dict[str, Any]] = []
    # Group arrows by (source, target) so the JSON order is deterministic
    # and matches the builder's sorted-edges expansion.
    by_edge: dict[tuple[int, int], list[tuple[str, Fraction]]] = {}
    for f in theory.fields:
        if f.multiplicity != 1:
            raise PureQuiverJSONError(
                f"Field {f.name!r} has multiplicity {f.multiplicity}; "
                "pure_quiver_to_json requires the multiplicity-1 builder convention"
            )
        if _is_singlet_field(f):
            singlets_payload.append(
                {"label": f.name, "r_charge": str(f.r_charge)}
            )
            continue
        source_idx, target_idx = _edge_indices(f, node_labels)
        by_edge.setdefault((source_idx, target_idx), []).append((f.name, f.r_charge))

    for (i, j) in sorted(by_edge):
        for label, r_charge in by_edge[(i, j)]:
            arrows_payload.append(
                {
                    "label": label,
                    "source": i,
                    "target": j,
                    "r_charge": str(r_charge),
                }
            )

    superpotential_payload: list[dict[str, Any]] = []
    for term in theory.superpotential_terms:
        factors = list(term.field_names)
        superpotential_payload.append(
            {
                "factors": factors,
                "coefficient": str(term.coefficient),
            }
        )

    u1_payload = [sym.label for sym in theory.u1_globals()]
    for label in u1_payload:
        if label not in SUPPORTED_U1_GLOBALS:
            raise PureQuiverJSONError(
                f"u1 global {label!r} unsupported by pure_quiver JSON MVP "
                f"(supported: {sorted(SUPPORTED_U1_GLOBALS)})"
            )

    payload: dict[str, Any] = {
        "name": theory.name,
        "node_labels": list(node_labels),
        "ranks": ranks,
        "u1_globals": u1_payload,
        "arrows": arrows_payload,
        "superpotential": superpotential_payload,
    }
    if singlets_payload:
        payload["singlets"] = singlets_payload
    return payload


def pure_quiver_from_json(data: Mapping[str, Any]) -> Theory:
    """Build a pure-quiver `Theory` from a JSON-compatible dict.

    Reconstructs the theory through `build_pure_quiver` so that the
    machine labels in the JSON must match the builder's output. This
    constraint keeps engine-emitted JSON aligned with the rest of the
    codebase's label conventions.
    """

    _require_keys(
        data,
        {"name", "node_labels", "ranks", "arrows", "superpotential"},
    )

    node_labels = tuple(data["node_labels"])
    ranks = tuple(int(r) for r in data["ranks"])
    if len(node_labels) != len(ranks):
        raise PureQuiverJSONError(
            f"node_labels length {len(node_labels)} != ranks length {len(ranks)}"
        )

    u1_labels = list(data.get("u1_globals", []))
    for label in u1_labels:
        if label not in SUPPORTED_U1_GLOBALS:
            raise PureQuiverJSONError(
                f"u1 global {label!r} unsupported by pure_quiver JSON MVP"
            )
    u1_globals = tuple(u1_r() for _ in u1_labels)

    arrows_by_edge: dict[tuple[int, int], list[Fraction]] = {}
    arrow_labels_seen: dict[str, tuple[int, int]] = {}
    pending_labels: dict[tuple[int, int], list[str]] = {}
    for entry in data["arrows"]:
        _require_keys(entry, {"label", "source", "target", "r_charge"})
        i = int(entry["source"])
        j = int(entry["target"])
        if not (0 <= i < len(ranks) and 0 <= j < len(ranks)):
            raise PureQuiverJSONError(
                f"arrow {entry['label']!r} endpoints ({i}, {j}) out of range "
                f"for {len(ranks)}-node quiver"
            )
        label = entry["label"]
        if label in arrow_labels_seen:
            raise PureQuiverJSONError(
                f"duplicate arrow label {label!r}"
            )
        arrow_labels_seen[label] = (i, j)
        arrows_by_edge.setdefault((i, j), []).append(as_r_charge(entry["r_charge"]))
        pending_labels.setdefault((i, j), []).append(label)

    # Validate labels against build_pure_quiver's naming convention.
    for (i, j), labels in pending_labels.items():
        expected = arrow_names(i, j, len(labels))
        if tuple(labels) != expected:
            raise PureQuiverJSONError(
                f"edge ({i}, {j}) labels {labels!r} do not match builder's "
                f"expected naming {list(expected)}; reorder or rename so the "
                f"JSON aligns with build_pure_quiver"
            )

    singlets: list[tuple[str, Fraction]] = []
    singlet_labels_seen: set[str] = set()
    for entry in data.get("singlets", []):
        _require_keys(entry, {"label", "r_charge"})
        label = entry["label"]
        if label in arrow_labels_seen or label in singlet_labels_seen:
            raise PureQuiverJSONError(f"duplicate field label {label!r}")
        singlet_labels_seen.add(label)
        singlets.append((label, as_r_charge(entry["r_charge"])))

    known_labels = set(arrow_labels_seen) | singlet_labels_seen
    superpotential_terms: list[SuperpotentialTerm] = []
    for entry in data["superpotential"]:
        _require_keys(entry, {"factors", "coefficient"})
        factors_list = list(entry["factors"])
        for f_label in factors_list:
            if f_label not in known_labels:
                raise PureQuiverJSONError(
                    f"W term references unknown field label {f_label!r}; "
                    f"known labels: {sorted(known_labels)}"
                )
        # Compact into (label, power) factor tuples, preserving order of
        # first appearance so closed-walk validation downstream sees the
        # exact traversal order encoded in the JSON.
        compact: list[tuple[str, int]] = []
        idx = 0
        while idx < len(factors_list):
            run_label = factors_list[idx]
            run = 1
            while (
                idx + run < len(factors_list)
                and factors_list[idx + run] == run_label
            ):
                run += 1
            compact.append((run_label, run))
            idx += run
        superpotential_terms.append(
            SuperpotentialTerm(
                factors=tuple(compact),
                coefficient=Fraction(entry["coefficient"]),
            )
        )

    theory = build_pure_quiver(
        ranks=ranks,
        arrows=arrows_by_edge,
        superpotential=tuple(superpotential_terms),
        node_labels=node_labels,
        u1_globals=u1_globals,
        singlets=tuple(singlets),
    )
    # build_pure_quiver names the Theory generically; restore the JSON
    # `name` so round-trips compose to the identity.
    return Theory(
        name=str(data["name"]),
        gauge_nodes=theory.gauge_nodes,
        fields=theory.fields,
        superpotential_terms=theory.superpotential_terms,
        global_symmetries=theory.global_symmetries,
    )


def _is_singlet_field(field: Field) -> bool:
    """True if the field carries no nontrivial gauge charge (a pure singlet)."""

    return all(rep.name == "singlet" for rep in field.gauge_reps.values())


def _edge_indices(field: Field, node_labels: tuple[str, ...]) -> tuple[int, int]:
    """Resolve an `Arrow`-like Field's (source, target) gauge-node indices."""

    fund_nodes: list[int] = []
    antifund_nodes: list[int] = []
    adjoint_nodes: list[int] = []
    for label, rep in field.gauge_reps.items():
        try:
            idx = node_labels.index(label)
        except ValueError as exc:
            raise PureQuiverJSONError(
                f"Field {field.name!r} references gauge node {label!r} "
                f"not present in theory.gauge_nodes"
            ) from exc
        if rep.name == "fundamental":
            fund_nodes.append(idx)
        elif rep.name == "antifundamental":
            antifund_nodes.append(idx)
        elif rep.name == "adjoint":
            adjoint_nodes.append(idx)
        elif rep.name == "singlet":
            continue
        else:
            raise PureQuiverJSONError(
                f"Field {field.name!r} carries unsupported rep {rep.name!r}"
            )
    if adjoint_nodes:
        if len(adjoint_nodes) != 1 or fund_nodes or antifund_nodes:
            raise PureQuiverJSONError(
                f"Field {field.name!r} has malformed adjoint configuration"
            )
        i = adjoint_nodes[0]
        return (i, i)
    if len(antifund_nodes) != 1 or len(fund_nodes) != 1:
        raise PureQuiverJSONError(
            f"Field {field.name!r} is not a bifundamental "
            f"(antifund: {antifund_nodes}, fund: {fund_nodes})"
        )
    return (antifund_nodes[0], fund_nodes[0])


def _require_keys(payload: Mapping[str, Any], required: set[str]) -> None:
    missing = required - set(payload)
    if missing:
        raise PureQuiverJSONError(f"missing keys: {sorted(missing)}")
