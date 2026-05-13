import json
import subprocess
import sys
from pathlib import Path

from dualitycert.qft.claims import load_claim_file
from dualitycert.qft.dualities import evaluate_claim


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_load_correct_claim_file_and_emit_partial_json_certificate():
    claim = load_claim_file(REPO_ROOT / "claims" / "sqcd_Nc3_Nf5.json")

    certificate = evaluate_claim(claim)
    data = certificate.to_dict()

    assert data["claim_name"] == "sqcd_Nc3_Nf5"
    assert data["parameters"]["Nc"] == 3
    assert data["parameters"]["Nf"] == 5
    assert data["parameters"]["magnetic_rank"] == 2
    assert data["outward_status"] == "PARTIAL_WITH_NOT_IMPLEMENTED_OBLIGATIONS"
    assert not data["failed_obligations"]


def test_load_wrong_magnetic_rank_claim_file_fails_implemented_check():
    claim = load_claim_file(REPO_ROOT / "claims" / "wrong_magnetic_rank.json")

    certificate = evaluate_claim(claim)
    data = certificate.to_dict()

    assert data["outward_status"] == "FAILED_IMPLEMENTED_OBLIGATIONS"
    assert any(
        item["name"] == "global anomaly matching"
        for item in data["failed_obligations"]
    )


def test_load_wrong_superpotential_charge_claim_file_fails_invariance():
    claim = load_claim_file(REPO_ROOT / "claims" / "wrong_superpotential_charge.json")

    certificate = evaluate_claim(claim)
    data = certificate.to_dict()

    assert data["outward_status"] == "FAILED_IMPLEMENTED_OBLIGATIONS"
    assert any(
        item["name"] == "magnetic superpotential consistency"
        for item in data["failed_obligations"]
    )


def test_failure_example_claim_files_cover_missing_meson_and_wrong_r_charge():
    for filename in ("missing_meson.json", "wrong_meson_R_charge.json"):
        claim = load_claim_file(REPO_ROOT / "claims" / filename)

        certificate = evaluate_claim(claim)
        data = certificate.to_dict()

        assert data["outward_status"] == "FAILED_IMPLEMENTED_OBLIGATIONS"
        assert data["failed_obligations"]


def test_cli_json_mode_runs_for_correct_claim():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dualitycert.cli",
            "check",
            "claims/sqcd_Nc3_Nf5.json",
            "--json",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["outward_status"] == "PARTIAL_WITH_NOT_IMPLEMENTED_OBLIGATIONS"


def test_cli_json_mode_runs_for_failing_claim_without_program_error():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "dualitycert.cli",
            "check",
            "claims/wrong_magnetic_rank.json",
            "--json",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["outward_status"] == "FAILED_IMPLEMENTED_OBLIGATIONS"
