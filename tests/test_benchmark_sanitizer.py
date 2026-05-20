"""Tests for the Phase 2c-a sanitization layer and fixture JSONL I/O.

Pins Rule 3 (sanitize_for_prompt strips provenance, preserves
structure) and Rule 10 (deterministic JSONL serialization, round-trip
through write/read).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from dualitycert.benchmark import (
    Fixture,
    FixtureMetadata,
    GenerationLogEntry,
    fixture_from_dict,
    fixture_set_hash,
    fixture_to_dict,
    generation_entry_from_dict,
    generation_entry_to_dict,
    read_fixtures_jsonl,
    read_generation_log,
    sanitize_for_prompt,
    write_fixtures_jsonl,
    write_generation_log,
)


# ----------------------------------------------------------------------
# Sample theories (handwritten so the test is robust to engine changes).
# ----------------------------------------------------------------------


def _electric_theory() -> dict:
    return {
        "name": "dP_0 toric (electric)",
        "node_labels": ["SU(3)_0", "SU(3)_1", "SU(3)_2"],
        "ranks": [3, 3, 3],
        "u1_globals": ["U(1)_R"],
        "arrows": [
            {"label": "X01[0]", "source": 0, "target": 1, "r_charge": "2/3"},
            {"label": "X01[1]", "source": 0, "target": 1, "r_charge": "2/3"},
            {"label": "X01[2]", "source": 0, "target": 1, "r_charge": "2/3"},
            {"label": "X12[0]", "source": 1, "target": 2, "r_charge": "2/3"},
            {"label": "X20[0]", "source": 2, "target": 0, "r_charge": "2/3"},
        ],
        "superpotential": [
            {"factors": ["X01[0]", "X12[0]", "X20[0]"], "coefficient": "1"},
        ],
    }


def _candidate_theory() -> dict:
    return {
        "name": "dP_0 toric (electric) (Seiberg-mutated at node 0, bare) (integrated) (R-repaired)",
        "node_labels": ["SU(2N)_0", "SU(3)_1", "SU(3)_2"],
        "ranks": [6, 3, 3],
        "u1_globals": ["U(1)_R"],
        "arrows": [
            {"label": "X02[0]", "source": 0, "target": 2, "r_charge": "1/3"},
            {"label": "X10[0]", "source": 1, "target": 0, "r_charge": "1/3"},
            {"label": "X12[0]", "source": 1, "target": 2, "r_charge": "2/3"},
            {"label": "X21[0]", "source": 2, "target": 1, "r_charge": "4/3"},
        ],
        "superpotential": [
            {"factors": ["X10[0]", "X02[0]", "X21[0]"], "coefficient": "1"},
        ],
    }


# ----------------------------------------------------------------------
# sanitize_for_prompt: Rule 3 contract.
# ----------------------------------------------------------------------


def test_sanitize_replaces_name_with_theory_label():
    """`name` must become the supplied `theory_label`, not stay as the
    Seiberg-mutated provenance string."""

    sanitized = sanitize_for_prompt(_candidate_theory(), theory_label="Theory B")
    assert sanitized["name"] == "Theory B"
    assert "Seiberg" not in json.dumps(sanitized)
    assert "mutated" not in json.dumps(sanitized)
    assert "R-repaired" not in json.dumps(sanitized)


def test_sanitize_strips_node_labels():
    """`SU(2N)_0` would leak the rank parametrization; replace with neutral G{i}."""

    sanitized = sanitize_for_prompt(_candidate_theory(), theory_label="Theory B")
    assert sanitized["node_labels"] == ["G0", "G1", "G2"]
    # And nothing like SU(2N) lurks anywhere in the JSON.
    assert "SU(2N)" not in json.dumps(sanitized)
    assert "SU(3)" not in json.dumps(sanitized)


def test_sanitize_preserves_ranks_arrows_superpotential():
    """Physical content (ranks, arrows incl. labels, W) must pass through verbatim."""

    cand = _candidate_theory()
    sanitized = sanitize_for_prompt(cand, theory_label="Theory B")
    assert sanitized["ranks"] == [6, 3, 3]
    # Arrow labels X{i}{j}[k] are structural (encode source/target),
    # the plan keeps them; just compare full arrow dicts as a set.
    assert {a["label"] for a in sanitized["arrows"]} == {
        a["label"] for a in cand["arrows"]
    }
    for sa, ca in zip(sanitized["arrows"], cand["arrows"]):
        assert sa["source"] == ca["source"]
        assert sa["target"] == ca["target"]
        assert sa["r_charge"] == ca["r_charge"]
    assert sanitized["superpotential"] == cand["superpotential"]
    assert sanitized["u1_globals"] == cand["u1_globals"]


def test_sanitize_does_not_mutate_input():
    """Generator code may reuse the same theory dict across many fixtures —
    sanitize_for_prompt must produce a fresh dict (no aliasing)."""

    cand = _candidate_theory()
    before = json.dumps(cand, sort_keys=True)
    sanitized = sanitize_for_prompt(cand, theory_label="Theory B")
    after = json.dumps(cand, sort_keys=True)
    assert before == after
    # Mutating the output must not bleed into the input.
    sanitized["arrows"][0]["r_charge"] = "9/9"
    assert cand["arrows"][0]["r_charge"] == "1/3"


def test_sanitize_handles_missing_u1_globals():
    """Theories without u1_globals (rare but legal) get an empty list, not a KeyError."""

    theory = {k: v for k, v in _electric_theory().items() if k != "u1_globals"}
    sanitized = sanitize_for_prompt(theory, theory_label="Theory A")
    assert sanitized["u1_globals"] == []


def test_sanitize_uses_label_count_matching_ranks():
    """`node_labels` length must always equal `len(ranks)`, not the input's len."""

    theory = _electric_theory()
    # The input even had a 3-element node_labels list, but the rule is
    # "len(ranks)" not "len(input.node_labels)".
    theory["node_labels"] = ["should", "be", "ignored"]  # deliberate junk
    sanitized = sanitize_for_prompt(theory, theory_label="Theory A")
    assert sanitized["node_labels"] == ["G0", "G1", "G2"]


# ----------------------------------------------------------------------
# Fixture / GenerationLogEntry dataclass invariants.
# ----------------------------------------------------------------------


def _example_fixture() -> Fixture:
    return Fixture(
        fixture_id="dp0_node0_positive_001",
        ground_truth_label="dual",
        verifier_ground_truth={
            "overall_status": "CERTIFIED",
            "failed_obligations": [],
        },
        electric=_electric_theory(),
        candidate=_candidate_theory(),
        metadata=FixtureMetadata(
            source="dp0_toric",
            seed=42,
            perturbation_type="none",
            extra={"mutation_node": 0, "mutation_depth": 1, "N": 3},
        ),
    )


def test_fixture_label_must_agree_with_overall_status():
    """`ground_truth_label` must derive consistently from overall_status."""

    with pytest.raises(ValueError, match="does not match"):
        Fixture(
            fixture_id="bad",
            ground_truth_label="not_dual",
            verifier_ground_truth={
                "overall_status": "CERTIFIED",
                "failed_obligations": [],
            },
            electric=_electric_theory(),
            candidate=_candidate_theory(),
            metadata=FixtureMetadata(source="x", seed=0, perturbation_type="none"),
        )


def test_fixture_rejects_ambiguous_ground_truth_overall_status():
    """Rule 6: only CERTIFIED or FAILED are accepted; NOT_APPLICABLE / etc
    must be filtered out at generation time."""

    with pytest.raises(ValueError, match="CERTIFIED"):
        Fixture(
            fixture_id="bad",
            ground_truth_label="dual",
            verifier_ground_truth={
                "overall_status": "NOT_APPLICABLE",
                "failed_obligations": [],
            },
            electric=_electric_theory(),
            candidate=_candidate_theory(),
            metadata=FixtureMetadata(source="x", seed=0, perturbation_type="none"),
        )


def test_generation_log_entry_invariants():
    """Accepted entries have no discard_reason; discarded entries must have one."""

    md = FixtureMetadata(source="x", seed=1, perturbation_type="none")

    with pytest.raises(ValueError, match="accepted"):
        GenerationLogEntry(
            fixture_id="f",
            generation_status="accepted",
            discard_reason="oops",
            prompt_visible_fields=("electric", "candidate"),
            verifier_ground_truth={"overall_status": "CERTIFIED", "failed_obligations": []},
            metadata=md,
        )

    with pytest.raises(ValueError, match="discarded"):
        GenerationLogEntry(
            fixture_id="f",
            generation_status="discarded",
            discard_reason=None,
            prompt_visible_fields=(),
            verifier_ground_truth=None,
            metadata=md,
        )


# ----------------------------------------------------------------------
# JSONL I/O round-trip + determinism.
# ----------------------------------------------------------------------


def test_fixture_round_trip_via_dict_is_identity():
    """`fixture_from_dict(fixture_to_dict(f))` reproduces the original."""

    original = _example_fixture()
    redux = fixture_from_dict(fixture_to_dict(original))
    assert redux == original


def test_jsonl_write_then_read_round_trip(tmp_path: Path):
    """The fixture file is the authoritative serialization."""

    a = _example_fixture()
    b = Fixture(
        fixture_id="dp0_node0_w_drop_001",
        ground_truth_label="not_dual",
        verifier_ground_truth={
            "overall_status": "FAILED",
            "failed_obligations": ["bounded chiral-ring consistency"],
        },
        electric=_electric_theory(),
        candidate=_candidate_theory(),
        metadata=FixtureMetadata(
            source="dp0_toric",
            seed=43,
            perturbation_type="w_drop",
            extra={"dropped_term": ["X10[0]", "X02[0]", "X21[0]"]},
        ),
    )
    path = tmp_path / "out.jsonl"
    write_fixtures_jsonl(path, [a, b])
    redux = read_fixtures_jsonl(path)
    assert redux == [a, b]


def test_jsonl_serialization_is_deterministic(tmp_path: Path):
    """Same input fixtures → byte-identical JSONL (Rule 10)."""

    fix = _example_fixture()
    p1 = tmp_path / "a.jsonl"
    p2 = tmp_path / "b.jsonl"
    write_fixtures_jsonl(p1, [fix])
    write_fixtures_jsonl(p2, [fix])
    assert p1.read_bytes() == p2.read_bytes()
    # And every line is single-line (no embedded newlines).
    lines = p1.read_text().splitlines()
    assert len(lines) == 1


def test_jsonl_skips_blank_lines(tmp_path: Path):
    fix = _example_fixture()
    path = tmp_path / "blanks.jsonl"
    write_fixtures_jsonl(path, [fix])
    # Append a blank line; reader should ignore it.
    with path.open("a") as fh:
        fh.write("\n\n")
    redux = read_fixtures_jsonl(path)
    assert redux == [fix]


def test_fixture_set_hash_is_stable_and_order_sensitive():
    a = _example_fixture()
    b = Fixture(
        fixture_id="other",
        ground_truth_label="not_dual",
        verifier_ground_truth={"overall_status": "FAILED", "failed_obligations": ["x"]},
        electric=_electric_theory(),
        candidate=_candidate_theory(),
        metadata=FixtureMetadata(source="dp0_toric", seed=2, perturbation_type="w_drop"),
    )
    h_ab = fixture_set_hash([a, b])
    h_ab2 = fixture_set_hash([a, b])
    h_ba = fixture_set_hash([b, a])
    assert h_ab == h_ab2
    assert h_ab != h_ba  # order-sensitive by design


# ----------------------------------------------------------------------
# Generation log round-trip.
# ----------------------------------------------------------------------


def test_generation_log_round_trip(tmp_path: Path):
    md = FixtureMetadata(source="dp0_toric", seed=11, perturbation_type="r_naive")
    accepted = GenerationLogEntry(
        fixture_id="dp0_node0_r_naive_001",
        generation_status="accepted",
        discard_reason=None,
        prompt_visible_fields=("electric", "candidate"),
        verifier_ground_truth={"overall_status": "FAILED", "failed_obligations": ["W"]},
        metadata=md,
    )
    discarded = GenerationLogEntry(
        fixture_id="dp0_node0_r_naive_002",
        generation_status="discarded",
        discard_reason="ambiguous_ground_truth",
        prompt_visible_fields=(),
        verifier_ground_truth=None,
        metadata=FixtureMetadata(
            source="dp0_toric", seed=12, perturbation_type="r_naive"
        ),
    )
    path = tmp_path / "gen.jsonl"
    write_generation_log(path, [accepted, discarded])
    redux = read_generation_log(path)
    assert redux == [accepted, discarded]


def test_generation_log_records_prompt_visible_fields():
    """Audit-trail field: accepted entries explicitly list what the LLM saw."""

    md = FixtureMetadata(source="x", seed=0, perturbation_type="none")
    entry = GenerationLogEntry(
        fixture_id="f",
        generation_status="accepted",
        discard_reason=None,
        prompt_visible_fields=("electric", "candidate"),
        verifier_ground_truth={"overall_status": "CERTIFIED", "failed_obligations": []},
        metadata=md,
    )
    encoded = generation_entry_to_dict(entry)
    assert encoded["prompt_visible_fields"] == ["electric", "candidate"]
    # Round-trip preserves the order/contents.
    decoded = generation_entry_from_dict(encoded)
    assert decoded.prompt_visible_fields == ("electric", "candidate")
