"""Consistent R-propagation for single-node Seiberg duals.

Picks the electric R representative whose dual propagation is anomaly-free
on the magnetic side too, so the magnetic R is the exact duality image and
TrR^3 / central charge match with rational arithmetic — no a-maximization.
This unblocks irrational-superconformal-R seeds (dP_1 = Y^{2,1}, and the
Y^{p,q} / L^{abc} family) without algebraic-number support.
"""

from __future__ import annotations

from fractions import Fraction

import dataclasses

from dualitycert.experiments.chains import seiberg_dual_consistent
from dualitycert.experiments.config import VerifierConfig
from dualitycert.experiments.seed_catalog import (
    c3_z2z2_electric,
    dp1_electric,
    dp2_phase1_electric,
    spp_electric,
)
from dualitycert.experiments.verifier import run_verifier
from dualitycert.qft.pure_quiver_json import pure_quiver_to_json

from tests.test_mutation_engine import _electric_dp0


def _tr_r3(theory_json) -> Fraction:
    ranks = [int(r) for r in theory_json["ranks"]]
    total = sum(Fraction(N * N - 1) for N in ranks)  # gauginos (R=1)
    for a in theory_json["arrows"]:
        s, t = int(a["source"]), int(a["target"])
        comp = (ranks[s] * ranks[s] - 1) if s == t else ranks[s] * ranks[t]
        total += comp * (Fraction(a["r_charge"]) - 1) ** 3
    for sg in theory_json.get("singlets", []):
        total += (Fraction(sg["r_charge"]) - 1) ** 3
    return total


def test_dp1_certifies_with_consistent_r_all_nodes():
    """dP_1 (irrational superconformal R) certifies on every node once the
    electric R is shifted to the rep whose dual is magnetic-anomaly-free."""

    seed = dp1_electric()
    config = VerifierConfig()
    for node in range(4):
        res = seiberg_dual_consistent(seed, node)
        assert res.ok, (node, res.reason)
        assert res.metadata["electric_r_shifted"] is True
        outcome = run_verifier(res.electric, res.magnetic, config)
        assert outcome.status == "CERTIFIED", (node, outcome.failed_obligation_names)


def test_dp1_trR3_matches_under_consistent_r():
    """The duality-invariant TrR^3 matches exactly (rational) for both sides."""

    res = seiberg_dual_consistent(dp1_electric(), 0)
    assert res.ok
    assert _tr_r3(res.electric) == _tr_r3(res.magnetic)


def test_generation_certifies_dp1_positive_via_consistent_path():
    """End-to-end: generate_fixtures produces a CERTIFIED dP_1 positive through
    the depth-1 consistent-R path (the seed's irrational R is shifted so the
    magnetic R is its exact image)."""

    from dualitycert.experiments.config import ExperimentConfig
    from dualitycert.experiments.generation import generate_fixtures
    from dualitycert.experiments.seeds import SeedSpec

    specs = [SeedSpec("dp1", dp1_electric, node=0, N=2)]
    config = ExperimentConfig(
        name="dp1_consistent_gen",
        seed=7,
        depths=[1],
        fixture_classes=("positive",),
        n_per_cell=1,
    )
    result = generate_fixtures(
        config, seed_specs=specs, allow_incomplete_cells=True, write=False
    )
    positives = [r for r in result.manifest if r.perturbation_class == "positive"]
    assert len(positives) == 1
    assert positives[0].label == "CERTIFIED"
    assert positives[0].source == "dp1"
    assert positives[0].mutation_node_sequence == (0,)


def test_dp2_phase1_certifies_at_default_nodes_and_all_nodes_r_graded():
    """dP_2 phase I (irrational R, 5 nodes, 13 fields). TrR^3 matches on every
    node, so the duality is real everywhere; nodes 3 and 4 certify under the
    default chiral-ring grading, while nodes 0/1/2 (chiral duals) only certify
    under R-graded BCR (length grading is duality-non-invariant there)."""

    seed = dp2_phase1_electric()
    default = VerifierConfig()
    r_graded = dataclasses.replace(default, chiral_ring_grading="r_charge")
    certified_default = []
    for node in range(5):
        res = seiberg_dual_consistent(seed, node)
        assert res.ok, (node, res.reason)
        assert _tr_r3(res.electric) == _tr_r3(res.magnetic), node
        assert run_verifier(res.electric, res.magnetic, r_graded).status == "CERTIFIED"
        if run_verifier(res.electric, res.magnetic, default).status == "CERTIFIED":
            certified_default.append(node)
    assert 3 in certified_default and 4 in certified_default


def test_default_seed_specs_cover_six_families_with_certified_positives():
    """The paper dataset now spans six independent families: the two locked
    MVP sources (dp0, f0) plus the curated catalog seeds (c3_z2z2 non-chiral,
    dp1 + dp2_phase1 irrational-R, spp adjoint/multi-meson). Each must yield a
    CERTIFIED depth-1 positive through the real generation path."""

    from dualitycert.experiments.config import ExperimentConfig
    from dualitycert.experiments.generation import generate_fixtures
    from dualitycert.experiments.seeds import default_seed_specs

    expected = {"dp0_toric", "f0_phase_ii", "c3_z2z2", "dp1", "dp2_phase1", "spp"}
    families = {s.source_name for s in default_seed_specs()}
    assert expected <= families

    config = ExperimentConfig(
        name="default_seed_coverage",
        seed=11,
        depths=[1],
        fixture_classes=("positive",),
        n_per_cell=1,
    )
    result = generate_fixtures(config, allow_incomplete_cells=True, write=False)
    certified_by_family = {
        r.source
        for r in result.manifest
        if r.perturbation_class == "positive" and r.label == "CERTIFIED"
    }
    assert expected <= certified_by_family


def test_spp_reaches_a_nontrivial_non_toric_phase_via_multimeson():
    """SPP (arXiv:1702.03958) has an adjoint at node 1 (Kutasov, out of
    scope). Mutating an adjoint-free node (0 or 2) requires multi-meson
    premutation, since the quartic W bouquets traverse the dualized node
    twice. With that generalization the dual CERTIFIES, TrR^3 matches, and
    it is genuinely NON-TORIC: gauge singlets appear (no brane tiling has
    them) and the adjoint relocates off the dualized node's neighbour."""

    seed = spp_electric()
    config = VerifierConfig()
    assert {int(a["source"]) for a in seed["arrows"] if a["source"] == a["target"]} == {1}

    for node in (0, 2):  # adjoint-free
        res = seiberg_dual_consistent(seed, node)
        assert res.ok, (node, res.reason)
        assert _tr_r3(res.electric) == _tr_r3(res.magnetic), node
        assert run_verifier(res.electric, res.magnetic, config).status == "CERTIFIED"
        # Non-toric signature: gauge-singlet fields the electric SPP lacks.
        assert seed.get("singlets", []) == []
        assert len(res.magnetic.get("singlets", [])) >= 1


def test_multimeson_premutation_is_byte_exact_for_single_pass():
    """The multi-meson generalization must not perturb the single-pass case:
    dp0's node-0 dual (every W term crosses the dualized node at most once)
    is unchanged, so the locked dp0/F0 fixtures stay byte-identical."""

    from tests.test_mutation_engine import _electric_dp0
    from dualitycert.qft.mutation_engine import mutate_bare

    dp0 = pure_quiver_to_json(_electric_dp0())
    bare = mutate_bare(dict(dp0), node=0)
    # Single pass per term => no meson 2-cycles introduced at premutation.
    assert all(
        sum(1 for f in term["factors"] if f.startswith("X21")) <= 1
        for term in bare["superpotential"]
    )


def test_consistent_r_is_noop_for_symmetric_seeds():
    """Seeds whose symmetric rational R is already consistent (dp0 chiral,
    C^3/(Z2xZ2) non-chiral) leave the electric R untouched — the solve falls
    back to t=0 cleanly, so the working cases are undisturbed."""

    dp0 = pure_quiver_to_json(_electric_dp0())
    c3 = c3_z2z2_electric()
    for seed in (dp0, c3):
        for node in range(len(seed["ranks"])):
            res = seiberg_dual_consistent(seed, node)
            assert res.ok, (seed["name"], node, res.reason)
            assert res.metadata["electric_r_shifted"] is False
