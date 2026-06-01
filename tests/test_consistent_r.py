"""Consistent R-propagation for single-node Seiberg duals.

Picks the electric R representative whose dual propagation is anomaly-free
on the magnetic side too, so the magnetic R is the exact duality image and
TrR^3 / central charge match with rational arithmetic — no a-maximization.
This unblocks irrational-superconformal-R seeds (dP_1 = Y^{2,1}, and the
Y^{p,q} / L^{abc} family) without algebraic-number support.
"""

from __future__ import annotations

from fractions import Fraction

from dualitycert.experiments.chains import seiberg_dual_consistent
from dualitycert.experiments.config import VerifierConfig
from dualitycert.experiments.seed_catalog import c3_z2z2_electric, dp1_electric
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
