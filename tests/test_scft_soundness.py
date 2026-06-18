"""Necessary-condition diagnostics for a unitary 4d N=1 SCFT.

Three checks the calculator gained so it can flag inputs that cannot be the
SCFT they claim to be:

  1. Hofman-Maldacena: a, c > 0 and 1/2 <= a/c <= 3/2 (the hard gate).
  2. Composite-operator unitarity: single-trace mesonic gauge invariants
     with R < 2/3 (candidate decoupling; broadens the v1 singlet scan).
  3. One-loop beta coefficient b0 per node (DIAGNOSTIC ONLY -- never gates;
     b0 < 0 is physically allowed, e.g. F_0 phase II / dP_2 phase I).

The b0 tests are sympy-free; the central-charge / obligation tests need the
optional [amax] extra.
"""

from __future__ import annotations

import copy
from fractions import Fraction

import pytest

from dualitycert.qft.a_maximization import (
    asymptotic_freedom_report,
    central_charge_scft_bounds,
    mesonic_unitarity_scan,
    one_loop_beta_coefficients,
)


# ----------------------------------------------------------------------
# 1. Hofman-Maldacena + positivity (pure, sympy-free).
# ----------------------------------------------------------------------


def test_hofman_maldacena_free_field_endpoints_pass():
    # Free chiral multiplet (a, c) = (1/48, 1/24) -> a/c = 1/2 (lower edge).
    assert central_charge_scft_bounds(1 / 48, 1 / 24)["ok"]
    # Free vector multiplet (a, c) = (3/16, 1/8) -> a/c = 3/2 (upper edge).
    assert central_charge_scft_bounds(3 / 16, 1 / 8)["ok"]


def test_hofman_maldacena_rejects_out_of_band_and_negative():
    assert not central_charge_scft_bounds(2.0, 1.0)["ok"]  # a/c = 2 > 3/2
    assert not central_charge_scft_bounds(0.4, 1.0)["ok"]  # a/c = 0.4 < 1/2
    assert not central_charge_scft_bounds(-1.0, 1.0)["a_positive"]
    assert not central_charge_scft_bounds(1.0, -1.0)["c_positive"]


# ----------------------------------------------------------------------
# 2. One-loop beta coefficients (pure, sympy-free) -- DIAGNOSTIC ONLY.
# ----------------------------------------------------------------------


def _dp0_json():
    # dP_0 = C^3/Z_3: SU(3)^3, 9 bifundamentals cyclically (3 per directed edge).
    arrows = []
    for k in range(3):
        for i in range(3):
            s, t = k, (k + 1) % 3
            arrows.append(
                {"label": f"X{s}{t}_{i}", "source": s, "target": t, "r_charge": "2/3"}
            )
    return {"ranks": [3, 3, 3], "arrows": arrows, "superpotential": []}


def test_b0_vanishes_for_orbifold_point_quiver():
    # All R = 2/3 (orbifold point) <=> the one-loop b0 vanishes at every node.
    b0 = one_loop_beta_coefficients(_dp0_json())
    assert all(b == 0 for b in b0.values()), b0


def test_b0_goes_negative_when_a_node_loses_asymptotic_freedom():
    bad = _dp0_json()
    bad["ranks"] = [1, 3, 3]  # starve node 0 of colors -> matter > 3 N
    b0 = one_loop_beta_coefficients(bad)
    assert b0[0] < 0
    report = asymptotic_freedom_report(bad)
    assert 0 in report["one_loop_ir_free_nodes"]
    # It is reported, not asserted to be a failure (see the obligation test).


# ----------------------------------------------------------------------
# 3. Composite (mesonic) unitarity scan (pure).
# ----------------------------------------------------------------------


def _two_node_two_cycle(r_each):
    return {
        "ranks": [2, 2],
        "arrows": [
            {"label": "X01", "source": 0, "target": 1, "r_charge": str(r_each)},
            {"label": "X10", "source": 1, "target": 0, "r_charge": str(r_each)},
        ],
        "superpotential": [],
    }


def test_mesonic_scan_flags_sub_bound_loop():
    tj = _two_node_two_cycle(Fraction(1, 10))  # meson X01*X10 has R = 1/5 < 2/3
    r = {"X01": Fraction(1, 10), "X10": Fraction(1, 10)}
    out = mesonic_unitarity_scan(tj, r)
    assert not out["ok"]
    assert out["below_bound"]
    assert out["below_bound"][0]["operator"] == ["X01", "X10"]


def test_mesonic_scan_passes_when_loops_above_bound():
    tj = _two_node_two_cycle(Fraction(2, 5))  # meson R = 4/5 >= 2/3
    r = {"X01": Fraction(2, 5), "X10": Fraction(2, 5)}
    assert mesonic_unitarity_scan(tj, r)["ok"]


# ----------------------------------------------------------------------
# The opt-in obligation (needs sympy for the central-charge gate).
# ----------------------------------------------------------------------

sympy = pytest.importorskip("sympy")

from dualitycert.core.objects import DualityClaim  # noqa: E402
from dualitycert.core.status import Status  # noqa: E402
from dualitycert.experiments.seeds import default_seed_specs  # noqa: E402
from dualitycert.qft.pure_quiver_json import pure_quiver_from_json  # noqa: E402
from dualitycert.qft.rcharges import scft_soundness_check  # noqa: E402


def _claim(theory_json, **metadata):
    t = pure_quiver_from_json(theory_json)
    return DualityClaim(
        name="scft test", electric_theory=t, magnetic_theory=t, metadata=metadata
    )


def _family(name):
    spec = next(s for s in default_seed_specs() if s.source_name == name)
    return spec.electric()


def test_soundness_is_opt_in():
    assert scft_soundness_check(_claim(_family("dp0_toric"))).status == Status.NOT_APPLICABLE


@pytest.mark.slow
def test_soundness_certifies_all_six_families():
    families = ["dp0_toric", "f0_phase_ii", "c3_z2z2", "dp1", "dp2_phase1", "spp"]
    for name in families:
        result = scft_soundness_check(_claim(_family(name), run_scft_soundness=True))
        assert result.status == Status.CERTIFIED, (name, result.message)


@pytest.mark.slow
def test_negative_b0_node_does_not_fail_soundness():
    # The physics fix: F_0 phase II has b0 < 0 at nodes 0 and 2 yet is a genuine
    # SCFT -> the one-loop b0 must NOT gate the soundness verdict.
    result = scft_soundness_check(_claim(_family("f0_phase_ii"), run_scft_soundness=True))
    assert result.status == Status.CERTIFIED
    assert result.details["electric"]["one_loop_ir_free_nodes"]  # b0<0 nodes present


@pytest.mark.slow
def test_soundness_reports_central_charge_data():
    result = scft_soundness_check(_claim(_family("dp1"), run_scft_soundness=True))
    detail = result.details["electric"]
    assert detail["hofman_maldacena_ok"] is True
    assert 0.5 <= detail["a_over_c"] <= 1.5
