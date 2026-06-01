"""Gauge-singlet field support (Stage 1 of direction I).

When a node is Seiberg-dualized and one of its neighbors is connected
both ways (a non-chiral / diagonal edge), the meson M_uu = Q̃_u Q_u
decomposes under SU(N_u) as adjoint ⊕ singlet. The pure-quiver schema
only carried the adjoint (Phi_u); these tests pin the singlet half being
emitted, threaded through the JSON / engine / R-repair, and counted by
the anomaly + central-charge obligations so that C^3/(Z_2 x Z_2)
certifies.

KNOWN BOUNDARY (Stage 2): the bounded chiral-ring obligation still returns
NOT_APPLICABLE on a theory with singlets (the chiral-ring machinery is
arrow/path-only). `test_c3_bounded_chiral_ring_is_not_yet_applicable`
documents that so a future fix flips it deliberately.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from dualitycert.core.objects import DualityClaim, SuperpotentialTerm
from dualitycert.core.status import Status
from dualitycert.experiments.seed_catalog import c3_z2z2_electric
from dualitycert.qft.dualities import evaluate_claim
from dualitycert.qft.mutation_engine import (
    integrate_fields,
    integrate_linear_fields,
    mutate_bare,
)
from dualitycert.qft.pure_quiver_builder import build_pure_quiver
from dualitycert.qft.pure_quiver_json import (
    pure_quiver_from_json,
    pure_quiver_to_json,
)
from dualitycert.qft.r_repair import repair_r_charges

from tests.test_mutation_engine import _electric_dp0


_BCR_META = {
    "duality_profile": "singlet_support_test",
    "bounded_chiral_ring": {"max_length": 3, "require_r_graded": True},
}


# ----------------------------------------------------------------------
# Schema: singlet fields survive the JSON round-trip.
# ----------------------------------------------------------------------


def test_singlet_round_trips_through_json():
    theory = build_pure_quiver(
        ranks=(2, 2),
        arrows={(0, 1): [Fraction(1, 3)], (1, 0): [Fraction(1, 3)]},
        superpotential=(
            SuperpotentialTerm(
                factors=(("S0[0]", 1), ("X01[0]", 1), ("X10[0]", 1)),
                coefficient=Fraction(1),
            ),
        ),
        singlets=(("S0[0]", Fraction(4, 3)),),
    )
    payload = pure_quiver_to_json(theory)
    assert payload["singlets"] == [{"label": "S0[0]", "r_charge": "4/3"}]
    # Round-trip is the identity at the JSON level.
    assert pure_quiver_to_json(pure_quiver_from_json(payload)) == payload
    # And the reconstructed field is a genuine gauge singlet.
    rebuilt = pure_quiver_from_json(payload)
    singlet = next(f for f in rebuilt.fields if f.name == "S0[0]")
    assert all(rep.name == "singlet" for rep in singlet.gauge_reps.values())
    assert singlet.r_charge == Fraction(4, 3)


def test_theories_without_singlets_omit_the_key():
    payload = pure_quiver_to_json(_electric_dp0())
    assert "singlets" not in payload


# ----------------------------------------------------------------------
# Engine: diagonal mesons emit a singlet; chiral mutations do not.
# ----------------------------------------------------------------------


def test_mutate_bare_emits_singlets_at_diagonal_mesons():
    seed = c3_z2z2_electric()
    bare = mutate_bare(dict(seed), node=0)
    singlets = bare.get("singlets", [])
    # Node 0's three neighbours each give one diagonal meson -> one singlet.
    assert {s["label"] for s in singlets} == {"S1[0]", "S2[0]", "S3[0]"}
    # R(S) = R_in + R_out = 2/3 + 2/3.
    assert all(Fraction(s["r_charge"]) == Fraction(4, 3) for s in singlets)
    # Each singlet has its Seiberg coupling S_u q q̃ in W.
    coupled = {
        f
        for term in bare["superpotential"]
        for f in term["factors"]
        if f.startswith("S")
    }
    assert coupled == {"S1[0]", "S2[0]", "S3[0]"}


def test_dp0_mutation_emits_no_singlets():
    """dp0 is chiral (cyclic), so the dualized node has no diagonal meson."""

    bare = mutate_bare(pure_quiver_to_json(_electric_dp0()), node=0)
    assert "singlets" not in bare


# ----------------------------------------------------------------------
# Integration + repair carry singlets through.
# ----------------------------------------------------------------------


def test_integrate_fields_reduces_c3_and_keeps_singlets():
    integ = integrate_fields(mutate_bare(dict(c3_z2z2_electric()), node=0))
    # General reduction clears every residual 2-cycle (mass term).
    assert not any(len(t["factors"]) == 2 for t in integ["superpotential"])
    assert len(integ.get("singlets", [])) == 3


def test_dp0_integrate_fields_equals_linear_pass():
    """dp0/F0 leave no quadratic terms after the linear pass, so the general
    reduction is a no-op and integrate_fields is byte-identical."""

    bare = mutate_bare(pure_quiver_to_json(_electric_dp0()), node=0)
    assert integrate_fields(bare) == integrate_linear_fields(bare)


def test_repair_pins_singlet_r_charge():
    integ = integrate_fields(mutate_bare(dict(c3_z2z2_electric()), node=0))
    repaired = repair_r_charges(integ)["representative"]
    singlets = repaired.get("singlets", [])
    assert len(singlets) == 3
    # R(S) is pinned to 4/3 by the S q q̃ coupling (R(W) = 2).
    assert all(Fraction(s["r_charge"]) == Fraction(4, 3) for s in singlets)


# ----------------------------------------------------------------------
# End-to-end: C^3/(Z_2 x Z_2) certifies on every node.
# ----------------------------------------------------------------------


def _magnetic(node: int):
    seed = c3_z2z2_electric()
    integ = integrate_fields(mutate_bare(dict(seed), node=node))
    return repair_r_charges(integ)["representative"]


@pytest.mark.parametrize("node", [0, 1, 2, 3])
def test_c3_certifies_on_every_node(node: int):
    electric = pure_quiver_from_json(c3_z2z2_electric())
    magnetic = pure_quiver_from_json(_magnetic(node))
    claim = DualityClaim(
        name=f"C3/(Z2xZ2) Seiberg node {node}",
        electric_theory=electric,
        magnetic_theory=magnetic,
        metadata=_BCR_META,
    )
    certificate = evaluate_claim(claim)
    assert certificate.overall_status == Status.CERTIFIED
    statuses = {r.name: r.status for r in certificate.obligation_results}
    assert statuses["global anomaly matching"] == Status.CERTIFIED
    assert statuses["central charge matching from encoded R-symmetry"] == (
        Status.CERTIFIED
    )


def test_c3_bcr_length_not_applicable_but_r_graded_certifies():
    """Length grading still rejects singlet theories (the locked default
    SKIPS the chiral ring), but the duality-invariant R-charge grading
    CERTIFIES the bounded chiral ring up to R=2 — the meson word-length
    shift is what blocked the length-graded comparison."""

    electric = pure_quiver_from_json(c3_z2z2_electric())
    magnetic = pure_quiver_from_json(_magnetic(0))

    length_claim = DualityClaim(
        name="C3/(Z2xZ2) Seiberg node 0",
        electric_theory=electric,
        magnetic_theory=magnetic,
        metadata=_BCR_META,
    )
    length_statuses = {
        r.name: r.status for r in evaluate_claim(length_claim).obligation_results
    }
    assert length_statuses["bounded chiral-ring consistency"] == Status.NOT_APPLICABLE

    r_claim = DualityClaim(
        name="C3/(Z2xZ2) Seiberg node 0",
        electric_theory=electric,
        magnetic_theory=magnetic,
        metadata={
            "duality_profile": "singlet_support_test",
            "bounded_chiral_ring": {
                "max_length": 3,
                "require_r_graded": True,
                "grading": "r_charge",
                "max_r_charge": "2",
            },
        },
    )
    r_statuses = {
        r.name: r.status for r in evaluate_claim(r_claim).obligation_results
    }
    assert r_statuses["bounded chiral-ring consistency"] == Status.CERTIFIED
