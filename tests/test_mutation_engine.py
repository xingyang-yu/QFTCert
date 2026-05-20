"""Phase 2c0 mutation-engine tests.

Three layers, matching the design doc §4 oracle / adversarial / failure
characterization:

  - Bare-mutation structural sanity (field counts, label conventions).
  - End-to-end MVP oracle: integrate(mutate_bare(electric)) structurally
    equals build_dp0_magnetic_effective AND certifies bounded chiral-ring
    against electric dP_0 at L=3 r_graded.
  - Bare-mutation legitimate FAIL — pins that integration is required.
  - W-drop adversarial on engine output still FAILS at length=3 R=2
    (Phase 2b Type-4 regression, restated for engine-produced theory).
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from dualitycert.core.objects import DualityClaim, Theory
from dualitycert.core.status import Status
from dualitycert.groups.u1 import u1_r
from dualitycert.qft.dualities import evaluate_claim
from dualitycert.qft.mutation_engine import (
    MutationEngineError,
    integrate_linear_fields,
    mutate_bare,
)
from dualitycert.qft.pure_quiver_builder import (
    arrow_names,
    build_dp0_magnetic_effective,
    build_pure_quiver,
    dp0_superpotential,
)
from dualitycert.qft.pure_quiver_json import (
    pure_quiver_from_json,
    pure_quiver_to_json,
)


# ----------------------------------------------------------------------
# Fixtures.
# ----------------------------------------------------------------------


def _electric_dp0() -> Theory:
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


def _w_term_signature(superpotential):
    """Return a multiset signature of W terms (factor multiset, coefficient)."""

    return sorted(
        (tuple(sorted(t["factors"])), str(Fraction(t["coefficient"])))
        for t in superpotential
    )


def _arrow_signature(arrows):
    """Tuple of (label, source, target, r_charge) sorted."""

    return sorted(
        (a["label"], a["source"], a["target"], str(Fraction(a["r_charge"])))
        for a in arrows
    )


# ----------------------------------------------------------------------
# Layer 1: bare-mutation structural sanity.
# ----------------------------------------------------------------------


def test_mutate_bare_dp0_node0_produces_expected_edge_topology():
    electric_json = pure_quiver_to_json(_electric_dp0())
    bare = mutate_bare(electric_json, node=0)

    assert bare["ranks"] == [6, 3, 3]
    # 3 q̃ + 3 q + 3 X12 (unchanged) + 9 bare mesons = 18 arrows.
    assert len(bare["arrows"]) == 18
    # 6 mass terms (inherited from 6 ε permutations of electric W) +
    # 9 bare Seiberg coupling terms = 15.
    assert len(bare["superpotential"]) == 15

    edges = {(a["source"], a["target"]) for a in bare["arrows"]}
    assert edges == {(0, 2), (1, 0), (1, 2), (2, 1)}


def test_mutate_bare_assigns_canonical_per_edge_labels():
    bare = mutate_bare(pure_quiver_to_json(_electric_dp0()), node=0)
    by_edge = {}
    for a in bare["arrows"]:
        by_edge.setdefault((a["source"], a["target"]), []).append(a["label"])
    assert by_edge[(0, 2)] == ["X02[0]", "X02[1]", "X02[2]"]
    assert by_edge[(1, 0)] == ["X10[0]", "X10[1]", "X10[2]"]
    assert by_edge[(1, 2)] == ["X12[0]", "X12[1]", "X12[2]"]
    assert [l for l in by_edge[(2, 1)]] == [f"X21[{k}]" for k in range(9)]


def test_mutate_bare_reversed_arrow_r_charges_dualize():
    bare = mutate_bare(pure_quiver_to_json(_electric_dp0()), node=0)
    by_edge = {}
    for a in bare["arrows"]:
        by_edge.setdefault((a["source"], a["target"]), []).append(a)
    # Reversed in-arrows X_CA[c]: original R=2/3 → reversed R = 1 - 2/3 = 1/3.
    for a in by_edge[(0, 2)]:
        assert Fraction(a["r_charge"]) == Fraction(1, 3)
    # Reversed out-arrows X_AB[a]: 1 - 2/3 = 1/3.
    for a in by_edge[(1, 0)]:
        assert Fraction(a["r_charge"]) == Fraction(1, 3)
    # Mesons R = R(X_CA) + R(X_AB) = 2/3 + 2/3 = 4/3.
    for a in by_edge[(2, 1)]:
        assert Fraction(a["r_charge"]) == Fraction(4, 3)
    # Untouched X_BC keeps R = 2/3.
    for a in by_edge[(1, 2)]:
        assert Fraction(a["r_charge"]) == Fraction(2, 3)


def test_mutate_bare_rejects_isolated_node():
    """Mutation at a node with no in/out arrows is undefined."""

    isolated_json = {
        "name": "isolated",
        "node_labels": ["SU(3)_0", "SU(3)_1"],
        "ranks": [3, 3],
        "u1_globals": ["U(1)_R"],
        "arrows": [
            {"label": "X01[0]", "source": 0, "target": 1, "r_charge": "1/2"},
        ],
        "superpotential": [],
    }
    with pytest.raises(MutationEngineError, match="in-degree"):
        mutate_bare(isolated_json, node=1)  # node 1 has only one in-arrow


def test_mutate_bare_rejects_anomaly_mismatch():
    """In-flavor and out-flavor counts must match (cubic anomaly)."""

    payload = {
        "name": "anomaly mismatch",
        "node_labels": ["SU(3)_0", "SU(3)_1", "SU(3)_2"],
        "ranks": [3, 3, 3],
        "u1_globals": ["U(1)_R"],
        "arrows": [
            {"label": "X10[0]", "source": 1, "target": 0, "r_charge": "1/2"},
            {"label": "X10[1]", "source": 1, "target": 0, "r_charge": "1/2"},
            {"label": "X02[0]", "source": 0, "target": 2, "r_charge": "1/2"},
        ],
        "superpotential": [],
    }
    with pytest.raises(MutationEngineError, match="cubic-anomaly-free"):
        mutate_bare(payload, node=0)


# ----------------------------------------------------------------------
# Layer 2: bare-mutation FAIL pinning (integration is necessary).
# ----------------------------------------------------------------------


def test_mutate_bare_alone_fails_bounded_chiral_ring_against_electric():
    """Without integration, the engine output legitimately FAILs.

    This pins the necessity of `integrate_linear_fields`: bare mutation
    leaves X_BC plus the full 9-component meson matrix in the magnetic
    theory, which over-counts chiral-ring operators relative to the
    electric side. The Phase 2c0 MVP oracle is integrate(bare(...)),
    not bare(...) alone.
    """

    electric = _electric_dp0()
    bare = mutate_bare(pure_quiver_to_json(electric), node=0)
    magnetic_bare = pure_quiver_from_json(bare)

    claim = DualityClaim(
        name="dP_0 engine bare (pre-integration)",
        electric_theory=electric,
        magnetic_theory=magnetic_bare,
        metadata={
            "duality_profile": "dp0_engine_bare_L3",
            "bounded_chiral_ring": {"max_length": 3, "require_r_graded": True},
        },
    )
    certificate = evaluate_claim(claim)

    assert certificate.overall_status == Status.FAILED

    # Anomaly + W-consistency still CERTIFY on bare output (it's the
    # chiral-ring layer that catches the missing integration step).
    statuses = {
        r.name: r.status
        for r in certificate.obligation_results
    }
    assert statuses["electric gauge anomaly cancellation"] == Status.CERTIFIED
    assert statuses["magnetic gauge anomaly cancellation"] == Status.CERTIFIED
    assert statuses["electric superpotential consistency"] == Status.CERTIFIED
    assert statuses["magnetic superpotential consistency"] == Status.CERTIFIED
    assert statuses["bounded chiral-ring consistency"] == Status.FAILED


# ----------------------------------------------------------------------
# Layer 3: MVP oracle — integrate(bare) reproduces effective + certifies.
# ----------------------------------------------------------------------


def test_mvp_oracle_structural_match_to_build_dp0_magnetic_effective():
    """Engine output (post-integration) matches the hand-built fixture.

    Both theories have:
      - ranks [6, 3, 3];
      - 12 arrows on 3 edges (0,2)/(1,0)/(2,1) with the same R-charges;
      - the same 9 W terms (as a multiset of (factor-multiset, coeff)).
    The W-term *order* may differ — the engine groups by (α, β)
    iteration, the builder groups by (diagonal-then-off-diagonal).
    """

    electric = _electric_dp0()
    engine_json = integrate_linear_fields(
        mutate_bare(pure_quiver_to_json(electric), node=0)
    )
    expected_json = pure_quiver_to_json(build_dp0_magnetic_effective(N=3))

    assert engine_json["ranks"] == expected_json["ranks"]
    assert _arrow_signature(engine_json["arrows"]) == _arrow_signature(
        expected_json["arrows"]
    )
    assert _w_term_signature(
        engine_json["superpotential"]
    ) == _w_term_signature(expected_json["superpotential"])


def test_mvp_oracle_certifies_bounded_chiral_ring_against_electric_at_L3():
    """The headline scientific test: engine output and electric dP_0
    Seiberg-duality CERTIFY under bounded chiral-ring at L=3 r_graded.

    This is the Phase 2c0 acceptance gate. It says: the mutation engine
    correctly reproduces the dP_0 magnetic dual at the chiral-ring level,
    using only mechanical Seiberg mutation + linear F-equation
    elimination — no hand-coded dP_0 knowledge.
    """

    electric = _electric_dp0()
    magnetic = pure_quiver_from_json(
        integrate_linear_fields(
            mutate_bare(pure_quiver_to_json(electric), node=0)
        )
    )
    claim = DualityClaim(
        name="dP_0 engine MVP oracle",
        electric_theory=electric,
        magnetic_theory=magnetic,
        metadata={
            "duality_profile": "dp0_engine_oracle_L3",
            "bounded_chiral_ring": {"max_length": 3, "require_r_graded": True},
        },
    )
    certificate = evaluate_claim(claim)

    assert certificate.overall_status == Status.CERTIFIED

    bcr_result = next(
        r
        for r in certificate.obligation_results
        if r.name == "bounded chiral-ring consistency"
    )
    assert bcr_result.status == Status.CERTIFIED
    # Block (length=3, R=2) on both sides should have dim 10 = dim Sym^3(C^3).
    details = bcr_result.details
    tested = details.get("tested_blocks", [])
    target = next(
        b for b in tested if int(b["length"]) == 3 and Fraction(b["r_charge"]) == 2
    )
    assert int(target["electric_dim"]) == 10
    assert int(target["magnetic_dim"]) == 10


# ----------------------------------------------------------------------
# Layer 4: adversarial regression on engine output.
# ----------------------------------------------------------------------


def test_w_drop_on_engine_output_fails_at_length_3_r_charge_2():
    """Type-4 adversarial regression: drop one W term from the engine's
    effective output, verify bounded chiral-ring FAILS at (length=3,
    R=2) with magnetic dim > electric dim.

    Same flavor as `test_dp0_duality_with_magnetic_W_diagonal_dropped...`
    but pointed at the engine-produced effective theory rather than the
    hand-built fixture. The +4 dim increment matches the +4 surviving
    cyclic words when one cubic W monomial's three cyclic derivatives
    each lose one path (Phase 2b sediment).
    """

    electric = _electric_dp0()
    engine_json = integrate_linear_fields(
        mutate_bare(pure_quiver_to_json(electric), node=0)
    )
    # Find and drop a diagonal W term (e.g. X10[0] X02[0] X21[0]).
    perturbed_W = [
        t
        for t in engine_json["superpotential"]
        if tuple(t["factors"]) != ("X10[0]", "X02[0]", "X21[0]")
    ]
    assert len(perturbed_W) == len(engine_json["superpotential"]) - 1

    adv_json = dict(engine_json)
    adv_json["superpotential"] = perturbed_W
    magnetic_adv = pure_quiver_from_json(adv_json)

    claim = DualityClaim(
        name="dP_0 engine adversarial (diagonal W dropped)",
        electric_theory=electric,
        magnetic_theory=magnetic_adv,
        metadata={
            "duality_profile": "dp0_engine_w_dropped",
            "bounded_chiral_ring": {"max_length": 3, "require_r_graded": True},
        },
    )
    certificate = evaluate_claim(claim)

    assert certificate.overall_status == Status.FAILED

    bcr_result = next(
        r
        for r in certificate.obligation_results
        if r.name == "bounded chiral-ring consistency"
    )
    assert bcr_result.status == Status.FAILED
    failed = bcr_result.details["failed_blocks"]
    target = next(
        b for b in failed if int(b["length"]) == 3 and Fraction(b["r_charge"]) == 2
    )
    assert int(target["electric_dim"]) == 10
    # Phase 2b sediment: dropping one cubic W term raises the magnetic
    # dimension by 4 because each of the three cyclic derivatives loses
    # one path-monomial.
    assert int(target["magnetic_dim"]) == 14
