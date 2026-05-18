"""End-to-end verifier-in-the-loop tests using deterministic repair functions.

These tests demonstrate that the verifier's output (failed obligations with
diagnostic messages and structured details) is mechanically actionable: a
deterministic agent that knows the relevant physics can read the failure
report and converge to a passing claim.

Design principle (important): the verifier reports inconsistencies, not
answers. So the repair functions in this file embed SQCD knowledge (e.g.
"for Seiberg duality the magnetic rank is Nf - Nc"). The framework does
NOT provide that knowledge. Tests verify that:

  1. The verifier accurately identifies what fails.
  2. A repair using local physics knowledge restores PASS.
  3. The verifier does not silently accept partial fixes.

The JSON-loader and operator-map plumbing tests below are independent of
the repair principle and stay as plain unit tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dualitycert.core.certificates import (
    OUTWARD_FAILED,
    OUTWARD_PARTIAL,
    OUTWARD_PASSED,
)
from dualitycert.qft.claims import build_claim_from_data
from dualitycert.qft.dualities import evaluate_claim


REPO_ROOT = Path(__file__).resolve().parents[1]
PASSING_STATUSES = {OUTWARD_PASSED, OUTWARD_PARTIAL}


def _load_claim_data(filename: str) -> dict[str, Any]:
    return json.loads((REPO_ROOT / "claims" / filename).read_text())


# ---------------------------------------------------------------------------
# End-to-end round-trips: deterministic agent reads certificate, applies fix
# ---------------------------------------------------------------------------

def test_round_trip_wrong_magnetic_rank_with_seiberg_knowledge():
    """Agent that knows Seiberg duality can repair a wrong-rank claim."""
    data = _load_claim_data("wrong_magnetic_rank.json")
    claim = build_claim_from_data(data)
    certificate = evaluate_claim(claim)

    assert certificate.outward_status == OUTWARD_FAILED
    failed_names = {r.name for r in certificate.failed_obligations}
    assert "global anomaly matching" in failed_names

    # SQCD knowledge lives HERE, not in the framework: magnetic rank is Nf - Nc.
    repaired = json.loads(json.dumps(data))
    Nc = data["parameters"]["Nc"]
    Nf = data["parameters"]["Nf"]
    repaired.setdefault("magnetic", {})["rank"] = Nf - Nc

    repaired_cert = evaluate_claim(build_claim_from_data(repaired))
    assert repaired_cert.outward_status in PASSING_STATUSES
    assert not repaired_cert.failed_obligations


def test_round_trip_missing_meson_with_sqcd_knowledge():
    """Agent that knows W = M q qtilde requires field M can repair the claim."""
    data = _load_claim_data("missing_meson.json")
    claim = build_claim_from_data(data)
    certificate = evaluate_claim(claim)

    assert certificate.outward_status == OUTWARD_FAILED
    # SQCD knowledge: enabling include_meson restores the M field referenced by W.
    repaired = json.loads(json.dumps(data))
    repaired.setdefault("magnetic", {})["include_meson"] = True

    repaired_cert = evaluate_claim(build_claim_from_data(repaired))
    assert repaired_cert.outward_status in PASSING_STATUSES


def test_round_trip_iterative_loop_converges():
    """Verify-repair-reverify loop: each iteration reads the current failure set."""
    data = _load_claim_data("wrong_magnetic_rank.json")
    max_iterations = 5
    history: list[str] = []
    Nc = data["parameters"]["Nc"]
    Nf = data["parameters"]["Nf"]

    for _ in range(max_iterations):
        claim = build_claim_from_data(data)
        certificate = evaluate_claim(claim)
        history.append(certificate.outward_status)
        if certificate.outward_status != OUTWARD_FAILED:
            break
        # Deterministic agent: if any obligation fails, set magnetic rank to Nf-Nc.
        data = json.loads(json.dumps(data))
        data.setdefault("magnetic", {})["rank"] = Nf - Nc
    else:
        raise AssertionError(f"loop did not converge: {history}")

    assert history[0] == OUTWARD_FAILED
    assert history[-1] in PASSING_STATUSES


def test_round_trip_rejects_partial_fix_without_silent_pass():
    """An incorrect repair must still surface as FAILED."""
    data = _load_claim_data("wrong_magnetic_rank.json")
    bad = json.loads(json.dumps(data))
    bad.setdefault("magnetic", {})["rank"] = 4  # still wrong
    bad_cert = evaluate_claim(build_claim_from_data(bad))
    assert bad_cert.outward_status == OUTWARD_FAILED, (
        "an incorrect repair should not slip through as PASSED"
    )


# ---------------------------------------------------------------------------
# JSON-loader and operator-map plumbing (independent of repair principle)
# ---------------------------------------------------------------------------

def test_operator_map_is_deduped_against_inferred_sqcd_defaults():
    """A claim that self-describes the SQCD standard maps should not be checked twice."""
    from dualitycert.qft.dualities import build_seiberg_sqcd_claim

    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5)
    cert = evaluate_claim(claim)
    op_result = next(
        r for r in cert.obligation_results
        if r.name == "operator map Abelian charge matching"
    )
    assert op_result.details["claim_operator_map_count"] == 3
    assert op_result.details["inferred_sqcd_default_count"] == 0


def test_inferred_defaults_count_uses_set_semantics_for_duplicate_spellings():
    """Two syntactic spellings of the same map count once in claim_keys."""
    from dataclasses import replace as dc_replace
    from dualitycert.qft.dualities import build_seiberg_sqcd_claim

    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5)
    duplicate_meson = dc_replace(
        claim, operator_map={"Q Qtilde": "M", "Q^1 Qtilde": "M"},
    )
    cert = evaluate_claim(duplicate_meson)
    op_result = next(
        r for r in cert.obligation_results
        if r.name == "operator map Abelian charge matching"
    )
    assert op_result.details["inferred_sqcd_default_count"] == 2
    assert op_result.details["unique_maps_checked"] == 3


def test_operator_map_inferred_defaults_fill_in_when_claim_map_empty():
    """If the claim does not assert any operator maps, the SQCD-default fills in."""
    from dataclasses import replace as dc_replace
    from dualitycert.qft.dualities import build_seiberg_sqcd_claim

    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5)
    empty_claim = dc_replace(claim, operator_map={})
    cert = evaluate_claim(empty_claim)
    op_result = next(
        r for r in cert.obligation_results
        if r.name == "operator map Abelian charge matching"
    )
    assert op_result.details["claim_operator_map_count"] == 0
    assert op_result.details["inferred_sqcd_default_count"] == 3
    assert cert.outward_status in PASSING_STATUSES


def test_json_loader_distinguishes_explicit_empty_operator_map_from_missing():
    """Explicit `operator_map: {}` in JSON overrides the builder-provided default."""
    base = _load_claim_data("sqcd_Nc3_Nf5.json")

    missing_claim = build_claim_from_data(base)
    assert len(missing_claim.operator_map) == 3

    empty_data = json.loads(json.dumps(base))
    empty_data["operator_map"] = {}
    empty_claim = build_claim_from_data(empty_data)
    assert empty_claim.operator_map == {}


def test_json_loader_accepts_operator_map_and_checker_runs_it():
    """A custom operator_map in JSON is parsed, forwarded, and checked end-to-end."""
    data = _load_claim_data("sqcd_Nc3_Nf5.json")

    good_data = json.loads(json.dumps(data))
    good_data["operator_map"] = {"Q Qtilde": "M"}
    good_claim = build_claim_from_data(good_data)
    assert good_claim.operator_map == {"Q Qtilde": "M"}
    good_cert = evaluate_claim(good_claim)
    op_result = next(
        r for r in good_cert.obligation_results
        if r.name == "operator map Abelian charge matching"
    )
    assert op_result.details.get("claim_operator_map_count") == 1
    assert good_cert.outward_status in PASSING_STATUSES

    bad_data = json.loads(json.dumps(data))
    bad_data["operator_map"] = {"Q": "qtilde"}
    bad_claim = build_claim_from_data(bad_data)
    bad_cert = evaluate_claim(bad_claim)
    assert bad_cert.outward_status == OUTWARD_FAILED
    assert any(
        r.name == "operator map Abelian charge matching"
        for r in bad_cert.failed_obligations
    )
