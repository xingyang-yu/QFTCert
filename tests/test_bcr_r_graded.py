"""R-charge-graded bounded chiral-ring comparison (opt-in mode).

Word-length is not a duality-invariant grading (a magnetic meson M of
length 1 is the electric composite Q̃Q of length 2), so non-chiral duals
like C^3/(Z_2 x Z_2) — whose dualized node produces diagonal mesons /
adjoints — only match under R-charge grading. These tests pin:
  - C^3 certifies up to R=2 (was NOT_APPLICABLE in length mode);
  - it FAILS honestly at R=8/3 (single-trace / finite-N gap, deferred);
  - the locked length-graded default is unchanged;
  - dp0 (a true dual) still certifies; a broken dual still FAILS.
"""

from __future__ import annotations

import copy
from fractions import Fraction

import pytest

from dualitycert.core.objects import DualityClaim
from dualitycert.core.obligations import ObligationResult
from dualitycert.core.status import Status
from dualitycert.experiments.seed_catalog import c3_z2z2_electric
from dualitycert.qft.mutation_engine import integrate_fields, mutate_bare
from dualitycert.qft.pure_quiver_json import (
    pure_quiver_from_json,
    pure_quiver_to_json,
)
from dualitycert.qft.quiver_chiral_ring import (
    bounded_chiral_ring_consistency_check,
)
from dualitycert.qft.r_repair import repair_r_charges

from tests.test_mutation_engine import _electric_dp0


_ANOMALY_KEYS = (
    "electric_gauge_anomaly",
    "magnetic_gauge_anomaly",
    "electric_gauge_global_mixed_anomaly",
    "magnetic_gauge_global_mixed_anomaly",
)


def _prior_pass():
    return {
        key: ObligationResult(
            name=key, description="", status=Status.CERTIFIED, message=""
        )
        for key in _ANOMALY_KEYS
    }


def _check(electric, magnetic, **bcr):
    claim = DualityClaim(
        name="bcr-test",
        electric_theory=electric,
        magnetic_theory=magnetic,
        metadata={"bounded_chiral_ring": bcr},
    )
    return bounded_chiral_ring_consistency_check(claim, _prior_pass())


def _c3_pair(node: int = 0):
    elec_json = c3_z2z2_electric()
    mag_json = repair_r_charges(
        integrate_fields(mutate_bare(dict(elec_json), node=node))
    )["representative"]
    return pure_quiver_from_json(elec_json), mag_json


def _dp0_pair():
    electric = _electric_dp0()
    mag_json = repair_r_charges(
        integrate_fields(mutate_bare(pure_quiver_to_json(electric), node=0))
    )["representative"]
    return electric, pure_quiver_from_json(mag_json)


def test_c3_r_graded_certifies_up_to_r2():
    electric, mag_json = _c3_pair()
    result = _check(
        electric, pure_quiver_from_json(mag_json),
        grading="r_charge", max_r_charge="2",
    )
    assert result.status == Status.CERTIFIED
    assert result.details["per_side_cutoff"] == {"electric_L": 3, "magnetic_L": 6}


@pytest.mark.slow
def test_c3_r_graded_fails_at_r_8_3_singletrace_gap():
    """At R=8/3 the single-trace / finite-N gap surfaces (electric 9 vs
    magnetic 6); the mode reports FAILED rather than a false CERTIFIED.

    Marked slow: needs magnetic word-length 8 (P6 cap) enumeration."""

    electric, mag_json = _c3_pair()
    result = _check(
        electric, pure_quiver_from_json(mag_json),
        grading="r_charge", max_r_charge="8/3",
    )
    assert result.status == Status.FAILED
    assert any(
        b["r_charge"] == "8/3" for b in result.details["failed_r_buckets"]
    )


def test_c3_length_mode_default_still_not_applicable():
    """The locked length-graded default rejects singlet theories at P5."""

    electric, mag_json = _c3_pair()
    result = _check(electric, pure_quiver_from_json(mag_json), max_length=3)
    assert result.status == Status.NOT_APPLICABLE


def test_dp0_r_graded_certifies():
    electric, magnetic = _dp0_pair()
    result = _check(electric, magnetic, grading="r_charge", max_r_charge="2")
    assert result.status == Status.CERTIFIED


@pytest.mark.slow
def test_c3_r_graded_fails_on_broken_dual():
    """Dropping a magnetic W term must break the R-graded comparison too.

    Marked slow: magnetic word-length 6 enumeration on the C^3 dual."""

    electric, mag_json = _c3_pair()
    broken = copy.deepcopy(mag_json)
    broken["superpotential"] = broken["superpotential"][1:]
    result = _check(
        electric, pure_quiver_from_json(broken),
        grading="r_charge", max_r_charge="2",
    )
    assert result.status == Status.FAILED


def test_r_graded_too_high_r_hits_p6_cap():
    """max_r_charge requiring word-length > 8 returns UNKNOWN, not a partial
    (incomplete) comparison."""

    electric, mag_json = _c3_pair()
    result = _check(
        electric, pure_quiver_from_json(mag_json),
        grading="r_charge", max_r_charge="3",  # magnetic L = ceil(3/(1/3)) = 9 > 8
    )
    assert result.status == Status.UNKNOWN
