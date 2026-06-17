"""Judge ②a: the superconformal-R audit (a-max as gatekeeper).

Pins that, under the "superconformal" R-charge policy, a claim must carry
THE superconformal (a-maximized) R: a consistent-but-non-superconformal R
(the rational-feasible stand-in the seeds ship) or an inconsistent R is
killed BEFORE the duality comparison; only the true superconformal R is
admitted. Also pins the opt-in obligation and the config byte-stability
of the new policy flag.

Skipped if sympy (the optional ``[amax]`` extra) is absent.
"""

from __future__ import annotations

import copy

import pytest

sympy = pytest.importorskip("sympy")
import sympy as sp  # noqa: E402

from dualitycert.core.objects import DualityClaim  # noqa: E402
from dualitycert.core.status import Status  # noqa: E402
from dualitycert.experiments.chains import seiberg_dual_consistent  # noqa: E402
from dualitycert.experiments.config import VerifierConfig  # noqa: E402
from dualitycert.experiments.seed_catalog import dp1_electric  # noqa: E402
from dualitycert.experiments.seeds import dp0_electric  # noqa: E402
from dualitycert.experiments.verifier import run_verifier  # noqa: E402
from dualitycert.qft.a_maximization import (  # noqa: E402
    audit_superconformal_r,
    with_superconformal_r,
)
from dualitycert.qft.pure_quiver_json import pure_quiver_from_json  # noqa: E402
from dualitycert.qft.rcharges import superconformal_r_audit_check  # noqa: E402


def _superconformal(theory_json):
    """A copy of `theory_json` with the a-max superconformal R substituted in."""

    return with_superconformal_r(copy.deepcopy(theory_json))


def _claim(electric_json, magnetic_json, **metadata):
    return DualityClaim(
        name="audit test",
        electric_theory=pure_quiver_from_json(electric_json),
        magnetic_theory=pure_quiver_from_json(magnetic_json),
        metadata=metadata,
    )


# ----------------------------------------------------------------------
# audit_superconformal_r verdicts.
# ----------------------------------------------------------------------


def test_audit_accepts_superconformal_R():
    assert audit_superconformal_r(_superconformal(dp1_electric(2)))["status"] == "superconformal"


def test_audit_rejects_rational_feasible_as_non_superconformal():
    # The dp1 seed ships a rational-feasible R; the superconformal R is the
    # irrational a-max point, so the rational stand-in is NOT superconformal.
    assert audit_superconformal_r(dp1_electric(2))["status"] == "non_superconformal"


def test_audit_rejects_inconsistent_R():
    bad = _superconformal(dp1_electric(2))
    bad["arrows"][0]["r_charge"] = str(
        sp.sympify(bad["arrows"][0]["r_charge"]) + sp.Rational(1, 3)
    )
    assert audit_superconformal_r(bad)["status"] == "inconsistent"


def test_audit_dp0_rational_superconformal():
    # dP_0's superconformal R is rational (2/3) and the seed already carries it.
    assert audit_superconformal_r(dp0_electric(3))["status"] == "superconformal"


# ----------------------------------------------------------------------
# The opt-in obligation.
# ----------------------------------------------------------------------


def test_obligation_is_not_applicable_without_optin():
    e = _superconformal(dp1_electric(2))
    result = superconformal_r_audit_check(_claim(e, e))
    assert result.status == Status.NOT_APPLICABLE


def test_obligation_certifies_superconformal_claim():
    e = _superconformal(dp1_electric(2))
    result = superconformal_r_audit_check(_claim(e, e, run_superconformal_audit=True))
    assert result.status == Status.CERTIFIED


def test_obligation_fails_non_superconformal_claim():
    e = dp1_electric(2)  # rational-feasible (non-superconformal) R
    result = superconformal_r_audit_check(_claim(e, e, run_superconformal_audit=True))
    assert result.status == Status.FAILED


# ----------------------------------------------------------------------
# End-to-end ②a mode (run_verifier with r_charge_policy="superconformal").
# ----------------------------------------------------------------------


@pytest.mark.slow
def test_superconformal_mode_certifies_correct_dual():
    cons = seiberg_dual_consistent(dp1_electric(2), 0)
    out = run_verifier(
        _superconformal(cons.electric),
        _superconformal(cons.magnetic),
        VerifierConfig(r_charge_policy="superconformal"),
        claim_name="dp1",
    )
    assert out.status == "CERTIFIED"


@pytest.mark.slow
def test_superconformal_mode_kills_rational_feasible_R():
    # Feeding the consistent rational-feasible R (NOT the superconformal R)
    # under ②a is killed by the audit before the duality comparison.
    cons = seiberg_dual_consistent(dp1_electric(2), 0)
    out = run_verifier(
        cons.electric,
        cons.magnetic,
        VerifierConfig(r_charge_policy="superconformal"),
        claim_name="dp1",
    )
    assert out.status == "FAILED"
    assert "superconformal R-charge audit" in out.failed_obligation_names


# ----------------------------------------------------------------------
# Config byte-stability of the new policy flag.
# ----------------------------------------------------------------------


def test_given_policy_is_not_serialized():
    # Default "given" must NOT appear in to_dict (keeps existing config_hash).
    assert "r_charge_policy" not in VerifierConfig().to_dict()
    assert VerifierConfig().config_hash() == VerifierConfig.from_dict({}).config_hash()
    # The non-default policy IS serialized and round-trips.
    sc = VerifierConfig(r_charge_policy="superconformal")
    assert sc.to_dict()["r_charge_policy"] == "superconformal"
    assert VerifierConfig.from_dict(sc.to_dict()).r_charge_policy == "superconformal"
