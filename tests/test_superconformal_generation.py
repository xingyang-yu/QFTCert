"""Stage ②a-4: the benchmark generation runs in the superconformal R-charge
policy (judge ②a).

Under `VerifierConfig(r_charge_policy="superconformal")` the positives are
regenerated with the superconformal (a-maximized) R substituted into both
sides (rational for dp0 / f0 / c3_z2z2, an exact algebraic number for the
irrational-R families dp1 / dp2 / spp); the negatives stay FAILED, since the
audit is a strictly stronger gate than judge ①. The whole substitution is
gated on the policy flag, so the default judge-① generation is byte-for-byte
unchanged.

Skipped if sympy (the optional ``[amax]`` extra) is absent.
"""

from __future__ import annotations

import json
from fractions import Fraction

import pytest

sympy = pytest.importorskip("sympy")

from dualitycert.experiments.config import ExperimentConfig, VerifierConfig  # noqa: E402
from dualitycert.experiments.generation import generate_fixtures  # noqa: E402
from dualitycert.experiments.seed_catalog import spp_electric  # noqa: E402
from dualitycert.experiments.seeds import SeedSpec  # noqa: E402


SUPERCONFORMAL = VerifierConfig(r_charge_policy="superconformal")
# SPP is the load-bearing case: its electric R is symmetric (rational-feasible,
# so the consistent-R path is a no-op and it routes through the mutation chain),
# yet its superconformal R is irrational (sqrt(97)). It exercises both the
# chain path under ②a and the algebraic-R substitution / perturbation.
_SPP = [SeedSpec("spp", spp_electric, node=0, N=2)]


def _config(name, classes):
    return ExperimentConfig(
        name=name,
        seed=20260617,
        depths=[1],
        fixture_classes=tuple(classes),
        n_per_cell=1,
        verifier=SUPERCONFORMAL,
    )


@pytest.mark.slow
def test_superconformal_generation_certifies_all_six_families():
    """Every default family yields a CERTIFIED depth-1 positive under ②a, now
    carrying its superconformal R (the same six families certify under ①)."""

    result = generate_fixtures(
        _config("2a_coverage", ("positive",)),
        allow_incomplete_cells=True,
        write=False,
    )
    certified = {
        r.source
        for r in result.manifest
        if r.perturbation_class == "positive" and r.label == "CERTIFIED"
    }
    assert {
        "dp0_toric",
        "f0_phase_ii",
        "c3_z2z2",
        "dp1",
        "dp2_phase1",
        "spp",
    } <= certified


@pytest.mark.slow
def test_spp_positive_carries_irrational_superconformal_r(tmp_path):
    """The written SPP positive carries the irrational superconformal R; the
    chain path no longer kills it (its internal verify is judge ①)."""

    result = generate_fixtures(
        _config("2a_spp", ("positive",)),
        seed_specs=_SPP,
        out_dir=tmp_path,
        allow_incomplete_cells=True,
        write=True,
    )
    pos = [r for r in result.manifest if r.perturbation_class == "positive"]
    assert pos and pos[0].label == "CERTIFIED"
    candidate = json.loads((tmp_path / pos[0].theory_b_path).read_text())
    assert any("sqrt" in str(a["r_charge"]) for a in candidate["arrows"])


@pytest.mark.slow
def test_r_charge_perturb_on_irrational_family_fails_not_crashes():
    """The algebraic-aware r_charge edit does not crash on an irrational R, and
    the perturbed claim is FAILED under ②a (a wrong R the audit kills)."""

    result = generate_fixtures(
        _config("2a_spp_rperturb", ("positive", "r_charge_perturb")),
        seed_specs=_SPP,
        allow_incomplete_cells=True,
        write=False,
    )
    r_perturb = [
        r for r in result.manifest if r.perturbation_class == "r_charge_perturb"
    ]
    assert r_perturb and all(r.label == "FAILED" for r in r_perturb)
    assert all(
        any(o["name"] == "superconformal R-charge audit" for o in r.failed_obligations)
        for r in r_perturb
    )


def test_given_policy_generation_keeps_rational_r(tmp_path):
    """Gating proof: under the DEFAULT given policy the SPP positive carries a
    rational (Fraction-parseable) R -- no superconformal substitution leaks
    into judge ①, so the locked generation path is unchanged."""

    config = ExperimentConfig(
        name="given_spp",
        seed=20260617,
        depths=[1],
        fixture_classes=("positive",),
        n_per_cell=1,
    )
    result = generate_fixtures(
        config,
        seed_specs=_SPP,
        out_dir=tmp_path,
        allow_incomplete_cells=True,
        write=True,
    )
    pos = [r for r in result.manifest if r.perturbation_class == "positive"]
    assert pos and pos[0].label == "CERTIFIED"
    candidate = json.loads((tmp_path / pos[0].theory_b_path).read_text())
    for arrow in candidate["arrows"]:
        Fraction(arrow["r_charge"])  # rational; raises on an algebraic R
