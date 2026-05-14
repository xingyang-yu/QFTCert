import subprocess
import sys
from pathlib import Path

from dualitycert.qft.claims import load_claim_file
from dualitycert.qft.critic import build_critic_report, build_repair_prompt
from dualitycert.qft.dualities import evaluate_claim


REPO_ROOT = Path(__file__).resolve().parents[1]


def _checked_claim(filename: str):
    claim = load_claim_file(REPO_ROOT / "claims" / filename)
    certificate = evaluate_claim(claim)
    return claim, certificate


def test_critic_report_suggests_expected_magnetic_rank():
    claim, certificate = _checked_claim("wrong_magnetic_rank.json")

    report = build_critic_report(claim, certificate)

    assert "FAILED_IMPLEMENTED_OBLIGATIONS" in report
    assert "magnetic.rank should be Nf - Nc = 2" in report
    assert "global anomaly matching" in report


def test_repair_prompt_suggests_including_missing_meson():
    claim, certificate = _checked_claim("missing_meson.json")

    prompt = build_repair_prompt(claim, certificate)

    assert "Return only corrected JSON" in prompt
    assert "magnetic.include_meson to true" in prompt
    assert "Do not change unrelated fields" in prompt


def test_repair_prompt_suggests_r_charge_formula():
    claim, certificate = _checked_claim("wrong_meson_R_charge.json")

    prompt = build_repair_prompt(claim, certificate)

    assert "R(M)=4/5" in prompt
    assert "R(q)=R(qtilde)=3/5" in prompt


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

    assert critique_result.returncode == 0
    assert repair_result.returncode == 0
    assert "magnetic.rank should be Nf - Nc = 2" in report_path.read_text()
    assert "magnetic.include_meson to true" in prompt_path.read_text()
