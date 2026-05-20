"""Phase 2c0 mutation-engine tests.

Four layers, matching the design doc §4 oracle / adversarial / failure
characterization + the §5 boundary regression on F_0 phase II:

  - Bare-mutation structural sanity (field counts, label conventions).
  - End-to-end MVP oracle: integrate(mutate_bare(electric)) structurally
    equals build_dp0_magnetic_effective AND certifies bounded chiral-ring
    against electric dP_0 at L=3 r_graded.
  - Bare-mutation legitimate FAIL — pins that integration is required.
  - W-drop adversarial on engine output still FAILS at length=3 R=2
    (Phase 2b Type-4 regression, restated for engine-produced theory).
  - **F_0 phase II boundary regression**: engine reproduces the dual's
    topology (ranks, edge multiplicities, total chiral count) but the
    verifier (correctly) rejects the trial UV R assignment on
    SU(N)² × U(1)_R grounds. This is a *boundary* regression — it pins
    where Phase 2c0 stops and Phase 2c1 (R-charge repair) begins.
"""

from __future__ import annotations

import itertools
from fractions import Fraction

import pytest

from dualitycert.core.objects import (
    DualityClaim,
    SuperpotentialTerm,
    Theory,
)
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


# ----------------------------------------------------------------------
# Layer 5: F_0 phase II boundary regression.
#
# This is a *boundary* regression, not a failure regression. It pins
# where Phase 2c0's mechanical Seiberg mutation stops being a valid
# physical dual: the engine correctly reproduces the topology
# (rank changes, edge multiplicities, total chiral count) but the
# verifier (correctly) rejects the result on SU(N)² × U(1)_R grounds
# because the naive Seiberg `R(q̃) = 1 - R(Q)` formula gives a
# *trial UV R*, not the SCFT R of the dual. The R-repair step belongs
# to Phase 2c1 (see docs/phase2c0_mutation_engine.md §5).
# ----------------------------------------------------------------------


def _electric_f0_phase_ii_trial(N: int = 3) -> Theory:
    """Build an F_0-phase-II-style 4-node trial quiver.

    Topology (matching the green diagram the user shared):
      - nodes 0=TL, 1=TR, 2=BR, 3=BL, all rank N;
      - edges (single-direction each):
          0 → 1 (top, 2 copies), 0 → 3 (left, 2 copies),
          2 → 0 (diagonal BR→TL, 4 copies),
          1 → 2 (right, 2 copies), 3 → 2 (bottom, 2 copies);
      - R-charges: boundary chirals R = 1/2, diagonal R = 1, so each
        cubic W term has R(W) = 1/2 + 1/2 + 1 = 2 ✓.

    W is the natural ε×ε antisymmetric coupling of the two SU(2)-like
    flavor indices on the cubic walks through node 0:
      W = ε_{aα} ε_{iβ} X01[a] X12[i] X20[(α, β)]
        − ε_{aα} ε_{iβ} X03[a] X32[i] X20[(α, β)]
    with X20[k] = X20[(α, β)] for k = 2α + β. The relative minus
    between the two triangles is chosen so that the electric side's
    mixed anomaly + bounded chiral-ring both certify under self-equiv
    (verified at construction time, see test below).

    This is a *trial* fixture: it is what the engine sees as input;
    nothing in this test claims it is THE F_0 II SCFT (the exact R
    after mutation needs Phase 2c1 R-repair).
    """

    def eps(a: int, b: int) -> int:
        if (a, b) == (0, 1):
            return 1
        if (a, b) == (1, 0):
            return -1
        return 0

    R_BD = Fraction(1, 2)
    R_DI = Fraction(1, 1)

    W_terms: list[SuperpotentialTerm] = []
    for a, i, alpha, beta in itertools.product(range(2), repeat=4):
        sign = eps(a, alpha) * eps(i, beta)
        if sign == 0:
            continue
        W_terms.append(
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
        W_terms.append(
            SuperpotentialTerm(
                factors=(
                    (f"X03[{a}]", 1),
                    (f"X32[{i}]", 1),
                    (f"X20[{2 * alpha + beta}]", 1),
                ),
                coefficient=Fraction(-sign),
            )
        )

    return build_pure_quiver(
        ranks=(N, N, N, N),
        arrows={
            (0, 1): [R_BD] * 2,
            (0, 3): [R_BD] * 2,
            (2, 0): [R_DI] * 4,
            (1, 2): [R_BD] * 2,
            (3, 2): [R_BD] * 2,
        },
        superpotential=tuple(W_terms),
        u1_globals=(u1_r(),),
    )


def test_f0_phase_ii_electric_self_equivalence_certifies():
    """Sanity gate before the boundary test: the F_0 II trial fixture
    is internally consistent on its own (all anomalies cancel, W is
    R=2, bounded chiral-ring trivially self-equates). If this fails,
    the boundary test below is meaningless because we'd be feeding the
    engine a broken input.
    """

    electric = _electric_f0_phase_ii_trial(N=3)
    claim = DualityClaim(
        name="F_0 II trial (self)",
        electric_theory=electric,
        magnetic_theory=electric,
        metadata={
            "duality_profile": "f0_phase_ii_self",
            "bounded_chiral_ring": {"max_length": 3, "require_r_graded": True},
        },
    )
    certificate = evaluate_claim(claim)
    assert certificate.overall_status == Status.CERTIFIED


def test_f0_phase_ii_mutation_topology_matches_but_trial_r_fails_mixed_anomaly():
    """Phase 2c0 boundary regression on F_0 phase II.

    What this pins:
      (a) **Topology is reproduced.** The engine's mutation at node 0
          gives ranks [3N, N, N, N], the expected (2, 2, 6, 6, 4) edge
          multiplicities matching the purple diagram, and total chiral
          count 20.
      (b) **Trial R fails verifier.** The naive
          R(q̃) = 1 - R(Q) assignment makes the reversed diagonal
          carry R = 0, breaking SU(N)² × U(1)_R at the non-dualized
          nodes. evaluate_claim returns FAILED. Bounded chiral-ring is
          NOT_APPLICABLE in r_graded mode because P4 (upstream anomaly
          CERTIFIED) is violated.

    This is a *boundary regression*, not a failure regression:
      - the engine itself did the right thing within MVP scope;
      - the verifier did the right thing within its own scope;
      - the gap between them is exactly what Phase 2c1's R-repair
        is for (linear feasibility on `R(W)=2 ∧ Σ mixed anomalies = 0`,
        and only a-maximize when a unique SCFT R is needed by
        central-charge / unitarity obligations).
    """

    N = 3
    electric = _electric_f0_phase_ii_trial(N=N)
    engine_out = integrate_linear_fields(
        mutate_bare(pure_quiver_to_json(electric), node=0)
    )

    # ----- (a) Topology assertions: matches the purple diagram. -----
    assert engine_out["ranks"] == [3 * N, N, N, N]

    edge_multiplicities = {}
    for arrow in engine_out["arrows"]:
        key = (arrow["source"], arrow["target"])
        edge_multiplicities[key] = edge_multiplicities.get(key, 0) + 1

    # Top: 2 reversed quarks (1 → 0). Left: 2 reversed quarks (3 → 0).
    # Diagonal: 4 reversed in-arrows (0 → 2). Right and bottom: 6 each
    # (2 original directional arrows integrated out together with the
    # antisymmetric mesons; 6 symmetric mesons survive on the bypass
    # edges 2 → 1 and 2 → 3).
    assert edge_multiplicities == {
        (0, 2): 4,   # reversed diagonal (TL → BR)
        (1, 0): 2,   # reversed top    (TR → TL)
        (2, 1): 6,   # bypass mesons   (BR → TR) — matches purple right
        (2, 3): 6,   # bypass mesons   (BR → BL) — matches purple bottom
        (3, 0): 2,   # reversed left   (BL → TL)
    }

    assert len(engine_out["arrows"]) == 20  # total chiral count

    # ----- (b) Verifier rejects trial R on mixed-anomaly grounds. -----
    magnetic = pure_quiver_from_json(engine_out)
    claim = DualityClaim(
        name="F_0 II Seiberg dual at TL (trial R)",
        electric_theory=electric,
        magnetic_theory=magnetic,
        metadata={
            "duality_profile": "f0_phase_ii_trial_dual",
            "bounded_chiral_ring": {"max_length": 3, "require_r_graded": True},
        },
    )
    certificate = evaluate_claim(claim)

    assert certificate.overall_status == Status.FAILED

    by_name = {r.name: r for r in certificate.obligation_results}

    # The smoking gun: mixed anomaly fails on the magnetic side.
    assert (
        by_name["magnetic gauge-global mixed anomaly cancellation"].status
        == Status.FAILED
    )

    # Electric mixed anomaly should still cancel (that's what the
    # self-equivalence sanity test pinned).
    assert (
        by_name["electric gauge-global mixed anomaly cancellation"].status
        == Status.CERTIFIED
    )

    # Bounded chiral-ring should NOT be CERTIFIED — in r_graded mode it
    # routes through NOT_APPLICABLE because P4 is broken upstream. We
    # accept either NOT_APPLICABLE or FAILED here; what we forbid is a
    # spurious CERTIFIED in a state with broken anomalies.
    bcr = by_name["bounded chiral-ring consistency"]
    assert bcr.status != Status.CERTIFIED
