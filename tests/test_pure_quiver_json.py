"""Round-trip tests for the pure-quiver JSON schema (Phase 2c0)."""

from __future__ import annotations

from fractions import Fraction

import pytest

from dualitycert.qft.pure_quiver_builder import (
    arrow_names,
    build_dp0_magnetic_effective,
    build_pure_quiver,
    dp0_superpotential,
)
from dualitycert.qft.pure_quiver_json import (
    PureQuiverJSONError,
    pure_quiver_from_json,
    pure_quiver_to_json,
)
from dualitycert.groups.u1 import u1_r


def _build_dp0_electric():
    n01 = arrow_names(0, 1, 3)
    n12 = arrow_names(1, 2, 3)
    n20 = arrow_names(2, 0, 3)
    return build_pure_quiver(
        ranks=(3, 3, 3),
        arrows={
            (0, 1): [Fraction(2, 3)] * 3,
            (1, 2): [Fraction(2, 3)] * 3,
            (2, 0): [Fraction(2, 3)] * 3,
        },
        superpotential=dp0_superpotential(n01, n12, n20),
        u1_globals=(u1_r(),),
    )


def _theory_signature(theory):
    """Return a hashable snapshot of a Theory's structural data."""

    return (
        tuple((n.label, n.N) for n in theory.gauge_nodes),
        tuple(
            (
                f.name,
                f.r_charge,
                tuple(sorted((k, v.name) for k, v in f.gauge_reps.items())),
                f.multiplicity,
            )
            for f in theory.fields
        ),
        tuple(
            (tuple(term.factors), term.coefficient)
            for term in theory.superpotential_terms
        ),
        tuple(sym.label for sym in theory.global_symmetries),
    )


def test_round_trip_dp0_electric_preserves_structure():
    original = _build_dp0_electric()
    payload = pure_quiver_to_json(original)
    rebuilt = pure_quiver_from_json(payload)
    assert _theory_signature(rebuilt) == _theory_signature(original)


def test_round_trip_dp0_magnetic_effective_preserves_structure():
    original = build_dp0_magnetic_effective(N=3)
    payload = pure_quiver_to_json(original)
    rebuilt = pure_quiver_from_json(payload)
    assert _theory_signature(rebuilt) == _theory_signature(original)


def test_round_trip_preserves_theory_name():
    original = _build_dp0_electric()
    object.__setattr__(original, "name", "dP_0 electric (test name)")
    payload = pure_quiver_to_json(original)
    rebuilt = pure_quiver_from_json(payload)
    assert rebuilt.name == "dP_0 electric (test name)"


def test_to_json_shape_matches_schema():
    theory = build_dp0_magnetic_effective(N=3)
    payload = pure_quiver_to_json(theory)
    assert set(payload) >= {
        "name",
        "node_labels",
        "ranks",
        "u1_globals",
        "arrows",
        "superpotential",
    }
    assert payload["ranks"] == [6, 3, 3]
    assert payload["u1_globals"] == ["U(1)_R"]
    # 3 q̃ + 3 q + 6 M = 12 arrows.
    assert len(payload["arrows"]) == 12
    # 3 diagonal + 6 off-diagonal = 9 W terms.
    assert len(payload["superpotential"]) == 9


def test_arrow_labels_grouped_by_edge_in_canonical_order():
    payload = pure_quiver_to_json(build_dp0_magnetic_effective(N=3))
    labels = [a["label"] for a in payload["arrows"]]
    assert labels == [
        "X02[0]", "X02[1]", "X02[2]",
        "X10[0]", "X10[1]", "X10[2]",
        "X21[0]", "X21[1]", "X21[2]", "X21[3]", "X21[4]", "X21[5]",
    ]


def test_from_json_rejects_unknown_arrow_in_W():
    payload = pure_quiver_to_json(build_dp0_magnetic_effective(N=3))
    payload["superpotential"][0]["factors"][0] = "X02[99]"
    with pytest.raises(PureQuiverJSONError, match="unknown field label"):
        pure_quiver_from_json(payload)


def test_from_json_rejects_mismatched_label_naming():
    payload = pure_quiver_to_json(build_dp0_magnetic_effective(N=3))
    payload["arrows"][0]["label"] = "X02_funny[0]"
    with pytest.raises(PureQuiverJSONError, match="do not match builder"):
        pure_quiver_from_json(payload)


def test_from_json_rejects_duplicate_labels():
    payload = pure_quiver_to_json(build_dp0_magnetic_effective(N=3))
    payload["arrows"][1]["label"] = payload["arrows"][0]["label"]
    with pytest.raises(PureQuiverJSONError, match="duplicate arrow label"):
        pure_quiver_from_json(payload)


def test_from_json_rejects_missing_keys():
    payload = pure_quiver_to_json(build_dp0_magnetic_effective(N=3))
    del payload["arrows"]
    with pytest.raises(PureQuiverJSONError, match="missing keys"):
        pure_quiver_from_json(payload)


def test_from_json_rejects_unsupported_u1_global():
    payload = pure_quiver_to_json(build_dp0_magnetic_effective(N=3))
    payload["u1_globals"] = ["U(1)_B"]
    with pytest.raises(PureQuiverJSONError, match="unsupported"):
        pure_quiver_from_json(payload)


def test_from_json_rejects_endpoint_out_of_range():
    payload = pure_quiver_to_json(build_dp0_magnetic_effective(N=3))
    payload["arrows"][0]["target"] = 99
    with pytest.raises(PureQuiverJSONError, match="out of range"):
        pure_quiver_from_json(payload)
