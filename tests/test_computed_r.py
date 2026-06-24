"""Judge ②b: the "computed" R-charge policy.

Under ``VerifierConfig(r_charge_policy="computed")`` the claimed R is IGNORED:
the verifier recomputes the superconformal (a-maximized) R from each side's
structure and runs the structural checks on it, so the model commits only to
quiver + matter + superpotential. There is no claimed-R audit and no
r_charge_perturb negative class (the perturbation is a no-op once the R is
recomputed).

The config round-trip needs no sympy; the verifier / generation tests need
the optional ``[amax]`` extra.
"""

from __future__ import annotations

import json
from fractions import Fraction
from random import Random

import pytest

from dualitycert.experiments.config import ExperimentConfig, VerifierConfig


def test_computed_policy_roundtrips_through_config_dict():
    vc = VerifierConfig(r_charge_policy="computed")
    assert vc.to_dict()["r_charge_policy"] == "computed"
    assert VerifierConfig.from_dict(vc.to_dict()).r_charge_policy == "computed"


def test_default_policy_is_not_serialized():
    """Byte-stability guardrail: the default ("given") policy never appears in
    the config dict, so judge-① config hashes are unchanged."""

    assert "r_charge_policy" not in VerifierConfig().to_dict()


# --- ②b LLM interface: R-charges hidden, ②b system prompt (no sympy) ------
_THEORY = {
    "name": "X",
    "ranks": [3],
    "node_labels": ["G0"],
    "u1_globals": ["U(1)_R"],
    "arrows": [{"label": "A", "tail": 0, "head": 0, "r_charge": "2/3"}],
    "singlets": [{"label": "M", "r_charge": "1/2"}],
    "superpotential": [{"factors": ["A"], "coefficient": "1"}],
}


def test_strip_r_charges_removes_only_r_charge():
    from dualitycert.experiments.single_shot import _strip_r_charges

    out = _strip_r_charges(_THEORY)
    assert "r_charge" not in out["arrows"][0]
    assert out["arrows"][0]["label"] == "A" and out["arrows"][0]["head"] == 0
    assert "r_charge" not in out["singlets"][0]
    assert out["ranks"] == [3] and out["superpotential"]
    # input untouched
    assert "r_charge" in _THEORY["arrows"][0]


def test_detection_computed_r_selects_2b_system_prompt():
    from dualitycert.agent import (
        DETECTION_SYSTEM_PROMPT,
        DETECTION_SYSTEM_PROMPT_COMPUTED_R,
        MockLLMClient,
        run_detection,
    )

    assert DETECTION_SYSTEM_PROMPT_COMPUTED_R != DETECTION_SYSTEM_PROMPT
    assert "NOT" in DETECTION_SYSTEM_PROMPT_COMPUTED_R  # "R-charges are NOT given"
    payload = {"verdict": "dual", "confidence": "low", "reasoning": "x"}
    mock = MockLLMClient(structured_responses=[payload, payload])

    run_detection(
        sanitized_electric=_THEORY, sanitized_candidate=_THEORY,
        client=mock, model="m", max_tokens=64, computed_r=True,
    )
    assert mock.structured_calls[0]["system"] == DETECTION_SYSTEM_PROMPT_COMPUTED_R

    run_detection(
        sanitized_electric=_THEORY, sanitized_candidate=_THEORY,
        client=mock, model="m", max_tokens=64, computed_r=False,
    )
    assert mock.structured_calls[1]["system"] == DETECTION_SYSTEM_PROMPT


def test_diagnosis_computed_r_selects_2b_system_prompt():
    from dualitycert.agent.client import MockLLMClient
    from dualitycert.agent.diagnosis import (
        DIAGNOSIS_SYSTEM_PROMPT,
        DIAGNOSIS_SYSTEM_PROMPT_COMPUTED_R,
        run_diagnosis,
    )

    assert DIAGNOSIS_SYSTEM_PROMPT_COMPUTED_R != DIAGNOSIS_SYSTEM_PROMPT
    payload = {"failure_modes": [], "confidence": "low", "reasoning": "x"}
    mock = MockLLMClient(structured_responses=[payload])

    run_diagnosis(
        sanitized_electric=_THEORY, sanitized_candidate=_THEORY,
        client=mock, model="m", max_tokens=64, computed_r=True,
    )
    assert mock.structured_calls[0]["system"] == DIAGNOSIS_SYSTEM_PROMPT_COMPUTED_R


# --- sympy-dependent below -----------------------------------------------
sympy = pytest.importorskip("sympy")

from dualitycert.experiments.generation import generate_fixtures  # noqa: E402
from dualitycert.experiments.perturbations import (  # noqa: E402
    apply_single_positive_edit,
)
from dualitycert.experiments.seed_catalog import spp_electric  # noqa: E402
from dualitycert.experiments.seeds import SeedSpec  # noqa: E402
from dualitycert.experiments.verifier import run_verifier  # noqa: E402


COMPUTED = VerifierConfig(r_charge_policy="computed")
# SPP is the load-bearing family: its electric R is symmetric (so the stored R
# is rational-feasible), yet its superconformal R is irrational (sqrt 97). It is
# exactly the case that distinguishes ②b (recompute, certify) from naive
# rational matching.
_SPP = [SeedSpec("spp", spp_electric, node=0, N=2)]


def _config(name, classes, verifier=COMPUTED):
    return ExperimentConfig(
        name=name,
        seed=20260624,
        depths=[1],
        fixture_classes=tuple(classes),
        n_per_cell=1,
        verifier=verifier,
    )


@pytest.mark.slow
def test_computed_generation_certifies_all_six_families():
    """Every default family yields a CERTIFIED depth-1 positive under ②b -- the
    same families that certify under ① and ②a."""

    result = generate_fixtures(
        _config("2b_coverage", ("positive",)),
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
def test_computed_generation_omits_r_charge_perturb():
    """r_charge_perturb is listed in the config but must be filtered out under
    computed-R: neither a manifest fixture nor an attrition record for it."""

    result = generate_fixtures(
        _config("2b_no_rperturb", ("positive", "r_charge_perturb", "rank_perturb")),
        seed_specs=_SPP,
        allow_incomplete_cells=True,
        write=False,
    )
    assert not any(
        r.perturbation_class == "r_charge_perturb" for r in result.manifest
    )
    assert not any(
        a.perturbation_class == "r_charge_perturb" for a in result.attrition
    )


@pytest.mark.slow
def test_computed_certifies_dual_whose_stored_r_is_rational(tmp_path):
    """The crux of ②b: SPP's stored R is rational-feasible (a valid Fraction),
    yet its superconformal R is irrational (sqrt 97). The computed policy
    CERTIFIES the pair by recomputing that algebraic R from the structure -- so
    a rational stored R is enough; the model need not emit the irrational R."""

    result = generate_fixtures(
        _config("2b_spp", ("positive",)),
        seed_specs=_SPP,
        out_dir=tmp_path,
        allow_incomplete_cells=True,
        write=True,
    )
    pos = [r for r in result.manifest if r.perturbation_class == "positive"]
    assert pos and pos[0].label == "CERTIFIED"

    electric = json.loads((tmp_path / pos[0].theory_a_path).read_text())
    candidate = json.loads((tmp_path / pos[0].theory_b_path).read_text())
    # No superconformal substitution leaked into the stored ②b fixture: the R is
    # rational (Fraction would raise on an algebraic value like "sqrt(97)/...").
    for arrow in candidate["arrows"]:
        Fraction(arrow["r_charge"])
    # Re-verifying under computed still certifies it (recomputes the sqrt(97) R).
    assert run_verifier(electric, candidate, COMPUTED).is_certified


@pytest.mark.slow
def test_computed_structural_negative_is_not_certified(tmp_path):
    """A rank perturbation changes each side's gauge content -> the recomputed
    R-system differs or becomes infeasible, so the computed verifier must not
    certify it (FAILED, or ERROR -> attrition; either way not CERTIFIED)."""

    result = generate_fixtures(
        _config("2b_spp_pos", ("positive",)),
        seed_specs=_SPP,
        out_dir=tmp_path,
        allow_incomplete_cells=True,
        write=True,
    )
    pos = [r for r in result.manifest if r.perturbation_class == "positive"][0]
    electric = json.loads((tmp_path / pos.theory_a_path).read_text())
    candidate = json.loads((tmp_path / pos.theory_b_path).read_text())

    edited, _ = apply_single_positive_edit("rank_perturb", candidate, Random(7))
    assert not run_verifier(electric, edited, COMPUTED).is_certified


@pytest.mark.slow
def test_given_policy_generation_unchanged_by_computed_code(tmp_path):
    """Gating proof: the default given policy still produces an SPP positive
    with a rational R and is untouched by the ②b code path."""

    result = generate_fixtures(
        _config("2b_given_guard", ("positive",), verifier=VerifierConfig()),
        seed_specs=_SPP,
        out_dir=tmp_path,
        allow_incomplete_cells=True,
        write=True,
    )
    pos = [r for r in result.manifest if r.perturbation_class == "positive"]
    assert pos and pos[0].label == "CERTIFIED"
    candidate = json.loads((tmp_path / pos[0].theory_b_path).read_text())
    for arrow in candidate["arrows"]:
        Fraction(arrow["r_charge"])


@pytest.mark.slow
def test_run_single_shot_computed_hides_r_and_uses_2b_prompt(tmp_path):
    """End-to-end ②b interface: run_single_shot(hide_r_charges=True) strips the
    R-charges from the prompt and uses the ②b detection system prompt, so the
    model sees only quiver + matter + W."""

    from dualitycert.agent import DETECTION_SYSTEM_PROMPT_COMPUTED_R, MockLLMClient
    from dualitycert.experiments.single_shot import run_single_shot

    result = generate_fixtures(
        _config("2b_ss", ("positive",)),
        seed_specs=_SPP,
        out_dir=tmp_path,
        allow_incomplete_cells=True,
        write=True,
    )
    recs = [r for r in result.manifest if r.perturbation_class == "positive"]
    assert recs
    payload = {"verdict": "dual", "confidence": "high", "reasoning": "x"}
    mock = MockLLMClient(structured_responses=[payload for _ in recs])

    run_single_shot(
        recs,
        theory_root=tmp_path,
        client=mock,
        out_dir=tmp_path / "run",
        model="mock",
        tasks=("detection",),
        hide_r_charges=True,
    )
    call = mock.structured_calls[0]
    assert call["system"] == DETECTION_SYSTEM_PROMPT_COMPUTED_R
    assert "r_charge" not in call["user"]
