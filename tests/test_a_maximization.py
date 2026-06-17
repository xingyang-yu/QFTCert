"""a-maximization validation ladder.

Pins the superconformal central charges + R-symmetry computed
*independently* by a-maximization, across the rational/irrational and
single-theory/dual quadrants:

  - rational control: dP_0 (a=99/16) and F_0 phase II (a=219/32);
  - irrational headline: dP_1 (a = -739/4 + 52*sqrt(13), the textbook
    del Pezzo 1 central charge);
  - duality-invariance: electric vs mutation-engine Seiberg dual agree on
    a, c -- rational (dP_0: meson R=4/3, dual-quark R=1/3) and irrational
    (dP_1, same Q(sqrt 13) value despite different field content);
  - the opt-in obligation: NOT_APPLICABLE unless requested, CERTIFIED on a
    real dual, FAILED on a mismatched pair;
  - declared (Lean-style) flavor bases are validated against the kernel.

Skipped entirely if sympy (the optional ``[amax]`` extra) is absent.
"""

from __future__ import annotations

import pytest

sympy = pytest.importorskip("sympy")
import sympy as sp  # noqa: E402

from dualitycert.core.objects import DualityClaim  # noqa: E402
from dualitycert.core.status import Status  # noqa: E402
from dualitycert.experiments.seeds import dp0_electric, f0_phase_ii_electric  # noqa: E402
from dualitycert.experiments.seed_catalog import dp1_electric, spp_electric  # noqa: E402
from dualitycert.qft.a_maximization import (  # noqa: E402
    AMaxError,
    central_charges_match,
    superconformal_central_charges,
)
from dualitycert.qft.mutation_engine import (  # noqa: E402
    integrate_linear_fields,
    mutate_bare,
)
from dualitycert.qft.pure_quiver_json import pure_quiver_from_json  # noqa: E402
from dualitycert.qft.r_repair import repair_r_charges  # noqa: E402
from dualitycert.qft.rcharges import (  # noqa: E402
    a_maximization_matching,
    r_symmetry_observables,
)


SQRT13 = sp.sqrt(13)
DP1_A = sp.Rational(-739, 4) + 52 * SQRT13
DP1_C = sp.Rational(-369, 2) + 52 * SQRT13


def _dual(seed_json, node):
    """The node-`node` Seiberg dual quiver via the mutation engine."""

    bare = mutate_bare(seed_json, node=node)
    integrated = integrate_linear_fields(bare)
    return repair_r_charges(integrated)["representative"]


def _claim(electric_json, magnetic_json, *, run_amax):
    md = {"duality_profile": "phase2c_a_detection"}
    if run_amax:
        md["run_a_maximization"] = True
    return DualityClaim(
        name="amax test pair",
        electric_theory=pure_quiver_from_json(electric_json),
        magnetic_theory=pure_quiver_from_json(magnetic_json),
        metadata=md,
    )


# ----------------------------------------------------------------------
# Rational control.
# ----------------------------------------------------------------------


def test_dp0_central_charges_are_rational():
    res = superconformal_central_charges(dp0_electric(3))
    assert res.exact
    assert res.a == sp.Rational(99, 16)
    assert res.c == sp.Rational(51, 8)
    # all bifundamentals are R = 2/3 in the toric phase
    assert all(R == sp.Rational(2, 3) for R in res.r_charges.values())


def test_f0_central_charge_is_rational():
    res = superconformal_central_charges(f0_phase_ii_electric(3))
    assert res.exact
    assert res.a == sp.Rational(219, 32)


def test_amax_baseline_matches_encoded_observable_for_rational_seed():
    # For dP_0 the rational feasible R IS superconformal, so a-max must
    # reproduce r_symmetry_observables exactly.
    theory = pure_quiver_from_json(dp0_electric(3))
    assert superconformal_central_charges(dp0_electric(3)).a == r_symmetry_observables(theory)["a"]


# ----------------------------------------------------------------------
# Irrational headline (dP_1 -> sqrt(13)).
# ----------------------------------------------------------------------


def test_dp1_central_charges_are_quadratic_irrational():
    res = superconformal_central_charges(dp1_electric(2))
    assert res.exact
    assert sp.simplify(res.a - DP1_A) == 0
    assert sp.simplify(res.c - DP1_C) == 0
    # genuinely irrational, carrying the textbook dP_1 sqrt(13)
    assert res.a.has(SQRT13)


def test_spp_higher_radical_recovered_exactly():
    # SPP's superconformal a is a quadratic irrational in sqrt(97) -- a
    # radicand the old fixed sqrt-list missed. The power-basis minimal
    # polynomial path now recovers it exactly.
    res = superconformal_central_charges(spp_electric(2))
    assert res.exact
    assert sp.simplify(res.a - (sp.Rational(-189, 64) + sp.Rational(97, 192) * sp.sqrt(97))) == 0
    assert res.a.has(sp.sqrt(97))


# ----------------------------------------------------------------------
# Duality-invariance of a, c (the obligation's physics).
# ----------------------------------------------------------------------


def test_dp0_duality_invariance_of_a_c():
    electric = superconformal_central_charges(dp0_electric(3))
    magnetic = superconformal_central_charges(_dual(dp0_electric(3), 0))
    a_ok, c_ok = central_charges_match(electric, magnetic)
    assert a_ok and c_ok
    assert magnetic.a == sp.Rational(99, 16)
    # textbook Seiberg R-charges on the magnetic side
    rvals = set(magnetic.r_charges.values())
    assert sp.Rational(4, 3) in rvals  # mesons
    assert sp.Rational(1, 3) in rvals  # dual quarks


@pytest.mark.slow
def test_dp1_irrational_duality_invariance():
    electric = superconformal_central_charges(dp1_electric(2))
    magnetic = superconformal_central_charges(_dual(dp1_electric(2), 0))
    # different field content, identical Q(sqrt 13) central charges
    assert electric.flavor_dim and magnetic.flavor_dim
    a_ok, c_ok = central_charges_match(electric, magnetic)
    assert a_ok and c_ok
    assert sp.simplify(magnetic.a - DP1_A) == 0
    assert sp.simplify(magnetic.c - DP1_C) == 0


# ----------------------------------------------------------------------
# The opt-in obligation.
# ----------------------------------------------------------------------


def test_obligation_is_not_applicable_without_optin():
    claim = _claim(dp0_electric(3), _dual(dp0_electric(3), 0), run_amax=False)
    result = a_maximization_matching(claim)
    assert result.status == Status.NOT_APPLICABLE


def test_obligation_certifies_a_real_dual():
    claim = _claim(dp0_electric(3), _dual(dp0_electric(3), 0), run_amax=True)
    result = a_maximization_matching(claim)
    assert result.status == Status.CERTIFIED


def test_obligation_fails_a_mismatched_pair():
    # Cross-family wrong pair: dP_0 (a=99/16) vs F_0 (a=219/32).
    claim = _claim(dp0_electric(3), f0_phase_ii_electric(3), run_amax=True)
    result = a_maximization_matching(claim)
    assert result.status == Status.FAILED
    assert "a:" in result.message


# ----------------------------------------------------------------------
# Declared (Lean-style) flavor basis.
# ----------------------------------------------------------------------


def test_declared_flavor_basis_matching_kernel_reproduces_result():
    seed = dp1_electric(2)
    kernel = repair_r_charges(seed)["feasible_space"]["homogeneous_basis"]
    declared = superconformal_central_charges(seed, flavor_basis=kernel)
    auto = superconformal_central_charges(seed)
    assert sp.simplify(declared.a - auto.a) == 0


def test_declared_flavor_basis_rejects_non_symmetry():
    seed = dp0_electric(3)
    # Charge a single field -> breaks every W term it appears in.
    bogus = [{"X01[0]": "1"}]
    with pytest.raises(AMaxError, match="flavor"):
        superconformal_central_charges(seed, flavor_basis=bogus)
