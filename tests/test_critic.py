"""Tests for the critic report and inconsistency prompt.

Design-principle tests: the verifier reports inconsistencies, not answers.
These tests assert both what MUST appear (failed obligation name, universal
principle description, diagnostic message) and what MUST NOT appear (any
duality-specific suggested values like 'Nf - Nc = 2', explicit baryon
formulas, R-charge override values).
"""

import subprocess
import sys
from pathlib import Path

from dualitycert.qft.claims import load_claim_file
from dualitycert.qft.critic import build_critic_report, build_repair_prompt
from dualitycert.qft.dualities import evaluate_claim


REPO_ROOT = Path(__file__).resolve().parents[1]


# Strings that, if they appeared in any verifier output, would constitute
# leakage of the answer to the duality the proposer is supposed to repair.  These
# are profile-specific Seiberg-duality formulas — universal physics laws
# (e.g. "R-charge 2", "anomaly cancellation") are NOT in this list because
# they are conditions, not answers.
SQCD_ANSWER_LEAKS = (
    "Nf - Nc",
    "Nf-Nc",
    "magnetic.rank should be",
    "use B(q)",
    "use R(q)",
    "R(q)=",
    "R(M)=",
    "B(q)=",
    "B(qtilde)=",
    "include_meson to true",
    "set magnetic.include_meson",
    "Nc/Nf",
    "2(Nf-Nc)/Nf",
)


def _checked_claim(filename: str):
    claim = load_claim_file(REPO_ROOT / "claims" / filename)
    certificate = evaluate_claim(claim)
    return claim, certificate


def _assert_no_answer_leakage(text: str) -> None:
    for needle in SQCD_ANSWER_LEAKS:
        assert needle not in text, (
            f"answer leakage: produced text contained {needle!r}; "
            f"the verifier must report inconsistencies, not answers"
        )


# ---------------------------------------------------------------------------
# Critic report: structure and contents
# ---------------------------------------------------------------------------

def test_critic_report_includes_failure_status_and_obligation_name():
    claim, certificate = _checked_claim("wrong_magnetic_rank.json")

    report = build_critic_report(claim, certificate)

    assert "FAILED_IMPLEMENTED_OBLIGATIONS" in report
    assert "global anomaly matching" in report
    assert "Consistency condition" in report


def test_critic_report_includes_universal_principle_but_not_answer():
    """The 'description' field carries the universal physics condition; no answer."""
    claim, certificate = _checked_claim("wrong_magnetic_rank.json")

    report = build_critic_report(claim, certificate)

    assert "'t Hooft anomaly" in report or "anomaly tables must match" in report
    _assert_no_answer_leakage(report)


def test_critic_report_for_missing_meson_does_not_suggest_the_fix():
    claim, certificate = _checked_claim("missing_meson.json")

    report = build_critic_report(claim, certificate)

    assert "FAILED" in report
    _assert_no_answer_leakage(report)


def test_critic_report_for_wrong_R_charge_does_not_leak_formula():
    claim, certificate = _checked_claim("wrong_meson_R_charge.json")

    report = build_critic_report(claim, certificate)

    assert "R-charge" in report or "R-symmetry" in report
    _assert_no_answer_leakage(report)


# ---------------------------------------------------------------------------
# Repair prompt: must contain inconsistency, must not contain answer
# ---------------------------------------------------------------------------

def test_repair_prompt_contains_failed_condition_and_diagnostic():
    claim, certificate = _checked_claim("wrong_magnetic_rank.json")

    prompt = build_repair_prompt(claim, certificate)

    assert "Failed consistency conditions" in prompt
    assert "global anomaly matching" in prompt
    assert "Condition:" in prompt
    assert "Diagnostic:" in prompt


def test_repair_prompt_for_each_fixture_contains_no_answer_leakage():
    for filename in (
        "wrong_magnetic_rank.json",
        "missing_meson.json",
        "wrong_meson_R_charge.json",
        "wrong_superpotential_charge.json",
    ):
        claim, certificate = _checked_claim(filename)
        prompt = build_repair_prompt(claim, certificate)
        try:
            _assert_no_answer_leakage(prompt)
        except AssertionError as exc:
            raise AssertionError(f"{filename}: {exc}") from None


def test_repair_prompt_lists_not_implemented_scope_explicitly():
    claim, certificate = _checked_claim("missing_meson.json")

    prompt = build_repair_prompt(claim, certificate)

    if certificate.not_implemented_obligations:
        assert "Out-of-scope" in prompt or "not checked" in prompt


def test_repair_prompt_emits_evidence_from_structured_details():
    """Numerical evidence in obligation.details should reach the prompt."""
    claim, certificate = _checked_claim("wrong_magnetic_rank.json")

    prompt = build_repair_prompt(claim, certificate)

    assert "Evidence:" in prompt


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------

def test_cli_critique_and_repair_prompt_write_output_files(tmp_path):
    report_path = tmp_path / "critic_report.md"
    prompt_path = tmp_path / "repair_prompt.md"

    critique_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dualitycert.cli",
            "critique",
            "claims/wrong_magnetic_rank.json",
            "--out",
            str(report_path),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    repair_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dualitycert.cli",
            "repair-prompt",
            "claims/missing_meson.json",
            "--out",
            str(prompt_path),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert critique_result.returncode == 0, critique_result.stderr
    assert repair_result.returncode == 0, repair_result.stderr

    report_text = report_path.read_text()
    prompt_text = prompt_path.read_text()
    assert "FAILED" in report_text
    assert "Failed consistency conditions" in prompt_text
    _assert_no_answer_leakage(report_text)
    _assert_no_answer_leakage(prompt_text)
