"""The 4d N=1 superconformal index (Rastelli-Razamat conventions).

Anchors (see dualitycert/qft/superconformal_index.py):
  - the conifold SU(2) x SU(2): 1 + 10 u^2 + ... (4 mesons + 6 baryons at R=1);
  - C^3/(Z_2 x Z_2) electric (SU(2)^4): 1 + 18 u^4 + ... ;
  - index_matches detects equality (duality invariant) and inequality;
  - irrational R is out of scope (raises);
  - the opt-in index_matching obligation.

Skipped if sympy (the optional [amax] extra) is absent.
"""

from __future__ import annotations

import pytest

sympy = pytest.importorskip("sympy")

from dualitycert.core.objects import DualityClaim  # noqa: E402
from dualitycert.core.status import Status  # noqa: E402
from dualitycert.experiments.seeds import default_seed_specs  # noqa: E402
from dualitycert.qft.pure_quiver_json import pure_quiver_from_json  # noqa: E402
from dualitycert.qft.rcharges import index_matching_check  # noqa: E402
from dualitycert.qft.superconformal_index import (  # noqa: E402
    SuperconformalIndexError,
    index_matches,
    index_series,
)


# The conifold SU(2) x SU(2): A_i (0->1), B_j (1->0), R=1/2, W = eps eps ABAB.
CONIFOLD = {
    "name": "conifold",
    "node_labels": ["n0", "n1"],
    "ranks": [2, 2],
    "arrows": [
        {"label": "A1", "source": 0, "target": 1, "r_charge": "1/2"},
        {"label": "A2", "source": 0, "target": 1, "r_charge": "1/2"},
        {"label": "B1", "source": 1, "target": 0, "r_charge": "1/2"},
        {"label": "B2", "source": 1, "target": 0, "r_charge": "1/2"},
    ],
    "superpotential": [
        {"coefficient": "1", "factors": ["A1", "B1", "A2", "B2"]},
        {"coefficient": "-1", "factors": ["A1", "B2", "A2", "B1"]},
    ],
}


def test_conifold_mesons_and_baryons():
    # R=1 (u^2) gauge invariants: 4 mesons Tr(A_i B_j) + 6 SU(2) baryons
    # (det-A and det-B, each 3 symmetric components) = 10.
    series = index_series(CONIFOLD, 4)
    assert series[0] == 1
    assert series[2] == 10


def test_c3_z2z2_electric_index():
    c3 = next(s for s in default_seed_specs() if s.source_name == "c3_z2z2").electric()
    series = index_series(c3, 4)
    assert series[0] == 1
    assert series[4] == 18  # lowest gauge invariants at R=4/3


def test_index_matches_equal_and_unequal():
    ok, _ = index_matches(CONIFOLD, CONIFOLD, 4)
    assert ok
    perturbed = {
        **CONIFOLD,
        "arrows": [
            {**a, "r_charge": "2/3"} if a["label"] == "A1" else a
            for a in CONIFOLD["arrows"]
        ],
    }
    ok2, _ = index_matches(CONIFOLD, perturbed, 4)
    assert not ok2


def test_refined_index_recovers_unrefined_at_unit_fugacity():
    unref = index_series(CONIFOLD, 4)
    ref = index_series(CONIFOLD, 4, flavor_fugacities=True)
    subs = {
        s: 1
        for c in ref.values()
        if hasattr(c, "free_symbols")
        for s in c.free_symbols
    }
    for k in set(unref) | set(ref):
        r = ref.get(k, 0)
        r1 = sympy.expand(r.subs(subs)) if hasattr(r, "subs") else r
        assert sympy.expand(unref.get(k, 0) - r1) == 0


def test_refined_index_carries_flavor_characters():
    ref = index_series(CONIFOLD, 4, flavor_fugacities=True)
    # the R=1 (u^2) coefficient is a nontrivial flavor character (the 4 mesons
    # + 6 baryons split into distinct flavor-charge sectors), not a bare count.
    assert getattr(ref[2], "free_symbols", set())


def test_flavor_nodes_sqcd_su2_nf3():
    # SU(2) with Nf=3: gauge SU(2) (node 0) + two SU(3) GLOBAL flavor nodes
    # (1, 2). Q, Qtilde have R=1/3; the theory s-confines to 15 mesons/baryons
    # at R=2/3 (eq 4.2/4.3, the SU(6) antisymmetric). At flavor fugacity -> 1
    # the u^2 coefficient is 15 -- reproduced THROUGH the machine, not by hand.
    sqcd = {
        "ranks": [2],
        "arrows": [
            {"label": "Q", "source": 0, "target": 1, "r_charge": "1/3"},
            {"label": "Qt", "source": 0, "target": 2, "r_charge": "1/3"},
        ],
        "superpotential": [],
    }
    series = index_series(sqcd, 4, flavor_ranks=[3, 3])
    subs = {
        s: 1
        for c in series.values()
        if hasattr(c, "free_symbols")
        for s in c.free_symbols
    }
    at_unit = {
        k: sympy.expand(c.subs(subs)) if hasattr(c, "subs") else c
        for k, c in series.items()
    }
    assert at_unit[0] == 1
    assert at_unit[2] == 15


def test_derive_r_from_superpotential_matches_given_r():
    # dP_0 R is symmetry-forced to 2/3, so deriving R from {R(W)=2, anomaly}
    # reproduces the given-R index (input = field content + W, no manual R).
    dp0 = next(s for s in default_seed_specs() if s.source_name == "dp0_toric").electric()
    given = index_series(dp0, 4)
    derived = index_series(dp0, 4, derive_r="feasible")
    assert given == derived


def test_irrational_r_is_out_of_scope():
    bad = {
        "ranks": [2, 2],
        "arrows": [{"label": "X", "source": 0, "target": 1, "r_charge": "sqrt(2)/2"}],
        "superpotential": [],
    }
    with pytest.raises(SuperconformalIndexError):
        index_series(bad, 2)


# ----------------------------------------------------------------------
# The opt-in obligation.
# ----------------------------------------------------------------------


# The obligation goes through pure_quiver_from_json, whose builder enforces a
# strict arrow-naming convention, so use a seed theory (c3_z2z2: SU(2)^4, fast).
def _c3_json():
    return next(s for s in default_seed_specs() if s.source_name == "c3_z2z2").electric()


def _claim(electric_json, magnetic_json, **metadata):
    return DualityClaim(
        name="index test",
        electric_theory=pure_quiver_from_json(electric_json),
        magnetic_theory=pure_quiver_from_json(magnetic_json),
        metadata=metadata,
    )


def test_index_matching_is_opt_in():
    result = index_matching_check(_claim(_c3_json(), _c3_json()))
    assert result.status == Status.NOT_APPLICABLE


def test_index_matching_certifies_equal_indices():
    result = index_matching_check(
        _claim(_c3_json(), _c3_json(), run_index_matching=True, index_matching_order=4)
    )
    assert result.status == Status.CERTIFIED


def test_index_matching_fails_unequal_indices():
    electric = _c3_json()
    perturbed = {
        **electric,
        "arrows": [
            {**a, "r_charge": "1"} if i == 0 else a
            for i, a in enumerate(electric["arrows"])
        ],
    }
    result = index_matching_check(
        _claim(electric, perturbed, run_index_matching=True, index_matching_order=4)
    )
    assert result.status == Status.FAILED
