"""End-to-end verifier-in-the-loop tests.

These tests model the intended LLM <-> verifier interaction:

    broken claim -> certificate (FAILED) -> structured repair hints
    -> deterministic repair step that consumes the structured signal
    -> rebuilt claim -> certificate (PASSED)

The repair functions here are deliberately deterministic and do not call any
language model. They read structured fields from the certificate or from
typed RepairHint objects and apply minimal edits to the claim JSON. This
proves that the verifier's outputs are mechanically actionable, which is the
contract we want to expose to a real LLM repair agent.

Assertions match on the public outward status string and on RepairHint
`type` keys rather than on hint prose, so wording changes in critic messages
will not break these tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from dualitycert.core.certificates import (
    OUTWARD_FAILED,
    OUTWARD_PARTIAL,
    OUTWARD_PASSED,
    Certificate,
)
from dualitycert.core.objects import DualityClaim
from dualitycert.qft.claims import build_claim_from_data
from dualitycert.qft.critic import RepairHint, build_repair_hints
from dualitycert.qft.dualities import evaluate_claim


REPO_ROOT = Path(__file__).resolve().parents[1]


RepairFn = Callable[
    [dict[str, Any], list[RepairHint], Certificate, DualityClaim],
    dict[str, Any],
]


PASSING_STATUSES = {OUTWARD_PASSED, OUTWARD_PARTIAL}


def _load_claim_data(filename: str) -> dict[str, Any]:
    return json.loads((REPO_ROOT / "claims" / filename).read_text())


def _hint_types(hints: list[RepairHint]) -> set[str]:
    return {hint.type for hint in hints}


def _run_round_trip(
    broken_filename: str, repair: RepairFn
) -> tuple[Certificate, Certificate]:
    """Load a broken claim, fail it, deterministically repair it, and re-verify."""

    data = _load_claim_data(broken_filename)
    claim = build_claim_from_data(data)
    certificate = evaluate_claim(claim)
    assert certificate.outward_status == OUTWARD_FAILED, (
        f"{broken_filename}: starting claim should fail; "
        f"got {certificate.outward_status}"
    )

    hints = build_repair_hints(claim, certificate)
    assert hints, f"{broken_filename}: a failed claim should emit at least one repair hint"

    repaired_data = repair(data, hints, certificate, claim)
    repaired_claim = build_claim_from_data(repaired_data)
    repaired_certificate = evaluate_claim(repaired_claim)
    remaining = [r.name for r in repaired_certificate.failed_obligations]
    assert repaired_certificate.outward_status in PASSING_STATUSES, (
        f"{broken_filename}: repaired claim should pass implemented checks; "
        f"got {repaired_certificate.outward_status}; remaining failures: {remaining}"
    )
    assert not remaining, f"unexpected failures after repair: {remaining}"
    return certificate, repaired_certificate


def test_round_trip_wrong_magnetic_rank_repair_passes():
    """Reading the structured magnetic_rank_mismatch hint is enough to fix the claim."""

    def repair(data, hints, cert, claim):
        rank_hint = next(
            (h for h in hints if h.type == "magnetic_rank_mismatch"), None
        )
        assert rank_hint is not None, "expected a magnetic_rank_mismatch hint"
        assert rank_hint.path == "magnetic.rank"
        assert isinstance(rank_hint.suggested_value, int)
        repaired = json.loads(json.dumps(data))
        repaired.setdefault("magnetic", {})["rank"] = rank_hint.suggested_value
        repaired["name"] = f"{data.get('name', 'claim')}_repaired"
        return repaired

    _, repaired_cert = _run_round_trip("wrong_magnetic_rank.json", repair)
    assert not repaired_cert.failed_obligations


def test_round_trip_missing_meson_repair_passes():
    """The structured missing_meson hint carries the exact edit to apply."""

    def repair(data, hints, cert, claim):
        meson_hint = next((h for h in hints if h.type == "missing_meson"), None)
        assert meson_hint is not None, "expected a missing_meson hint"
        assert meson_hint.path == "magnetic.include_meson"
        assert meson_hint.suggested_value is True
        repaired = json.loads(json.dumps(data))
        repaired.setdefault("magnetic", {})["include_meson"] = meson_hint.suggested_value
        repaired["name"] = f"{data.get('name', 'claim')}_repaired"
        return repaired

    _, repaired_cert = _run_round_trip("missing_meson.json", repair)
    assert not repaired_cert.failed_obligations


def test_round_trip_wrong_meson_r_charge_repair_passes():
    """The structured r_charge_formula hint exposes the override value directly."""

    def repair(data, hints, cert, claim):
        r_hint = next((h for h in hints if h.type == "r_charge_formula"), None)
        assert r_hint is not None, "expected an r_charge_formula hint"
        assert isinstance(r_hint.suggested_value, dict)
        meson_override = r_hint.suggested_value["magnetic.meson_R_override"]
        repaired = json.loads(json.dumps(data))
        repaired.setdefault("magnetic", {})["meson_R_override"] = meson_override
        repaired["name"] = f"{data.get('name', 'claim')}_repaired"
        return repaired

    _, repaired_cert = _run_round_trip("wrong_meson_R_charge.json", repair)
    assert not repaired_cert.failed_obligations


def test_round_trip_repair_loop_iterates_until_pass():
    """Iterative loop: re-check after each repair until no implemented obligation fails."""

    data = _load_claim_data("wrong_magnetic_rank.json")
    max_iterations = 5
    history: list[str] = []
    for _ in range(max_iterations):
        claim = build_claim_from_data(data)
        certificate = evaluate_claim(claim)
        history.append(certificate.outward_status)
        if certificate.outward_status != OUTWARD_FAILED:
            break
        hints = build_repair_hints(claim, certificate)
        rank_hint = next(
            (h for h in hints if h.type == "magnetic_rank_mismatch"), None
        )
        assert rank_hint is not None
        data = json.loads(json.dumps(data))
        data.setdefault("magnetic", {})["rank"] = rank_hint.suggested_value
    else:  # pragma: no cover - guard against an infinite loop
        raise AssertionError(f"loop did not converge in {max_iterations} steps: {history}")

    assert certificate.outward_status in PASSING_STATUSES, history
    assert history[0] == OUTWARD_FAILED, "first iteration should have started failed"
    assert history[-1] in PASSING_STATUSES


def test_round_trip_rejects_unrepairable_claim_without_silent_pass():
    """If we apply only a partial fix, the verifier must still report FAILED."""

    data = _load_claim_data("wrong_magnetic_rank.json")
    bad_data = json.loads(json.dumps(data))
    bad_data.setdefault("magnetic", {})["rank"] = 4
    bad_claim = build_claim_from_data(bad_data)
    bad_cert = evaluate_claim(bad_claim)
    assert bad_cert.outward_status == OUTWARD_FAILED, (
        "an incorrect repair should not slip through as PASSED"
    )


def test_round_trip_hint_types_are_stable_keys():
    """Hint `type` keys are part of the public contract for downstream agents."""

    data = _load_claim_data("wrong_magnetic_rank.json")
    claim = build_claim_from_data(data)
    certificate = evaluate_claim(claim)
    hints = build_repair_hints(claim, certificate)
    types = _hint_types(hints)
    assert "magnetic_rank_mismatch" in types, types


def test_operator_map_is_deduped_against_inferred_sqcd_defaults():
    """A claim that self-describes the SQCD standard maps should not be checked twice."""

    from dualitycert.qft.dualities import build_seiberg_sqcd_claim

    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5)
    cert = evaluate_claim(claim)
    op_result = next(
        r
        for r in cert.obligation_results
        if r.name == "operator map Abelian charge matching"
    )
    # The builder populates 3 standard maps; defaults should not duplicate them.
    assert op_result.details["claim_operator_map_count"] == 3
    assert op_result.details["inferred_sqcd_default_count"] == 0


def test_inferred_defaults_count_uses_set_semantics_for_duplicate_spellings():
    """Two syntactic spellings of the same map count once in claim_keys."""

    from dataclasses import replace as dc_replace
    from dualitycert.qft.dualities import build_seiberg_sqcd_claim

    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5)
    # Both keys parse to the same canonical (("Q",1),("Qtilde",1)) -> (("M",1),).
    # The user only asserts the meson; baryon and antibaryon should still be
    # inferred from SQCD defaults regardless of the duplicate spelling.
    duplicate_meson = dc_replace(
        claim,
        operator_map={"Q Qtilde": "M", "Q^1 Qtilde": "M"},
    )
    cert = evaluate_claim(duplicate_meson)
    op_result = next(
        r
        for r in cert.obligation_results
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
        r
        for r in cert.obligation_results
        if r.name == "operator map Abelian charge matching"
    )
    assert op_result.details["claim_operator_map_count"] == 0
    assert op_result.details["inferred_sqcd_default_count"] == 3
    assert cert.outward_status in PASSING_STATUSES


def test_json_loader_distinguishes_explicit_empty_operator_map_from_missing():
    """Explicit `operator_map: {}` in JSON overrides the builder-provided default."""

    base = _load_claim_data("sqcd_Nc3_Nf5.json")

    # Missing operator_map key: builder-populated default sticks (3 entries).
    missing_claim = build_claim_from_data(base)
    assert len(missing_claim.operator_map) == 3

    # Explicit empty {} : honored as "no claim-asserted maps".
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
        r
        for r in good_cert.obligation_results
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
