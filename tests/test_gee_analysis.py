"""Offline tests for the frozen GEE analysis (protocol section 7)."""

from __future__ import annotations

import math
import random

import pytest

pytest.importorskip("statsmodels")

from dualitycert.experiments.gee_analysis import (
    EndpointResult,
    fit_endpoint,
    holm,
)


def _synthetic(p1: float, p0: float, *, n_fix=145, reps=(1, 2, 3), seed=7):
    rng = random.Random(seed)
    arm1, arm0 = {}, {}
    for f in range(n_fix):
        fid = f"fx{f:03d}"
        base = rng.gauss(0, 0.5)  # shared fixture effect -> clustering
        for r in reps:
            arm1[(fid, r)] = rng.random() < min(max(p1 + 0.1 * base, 0.01), 0.99)
            arm0[(fid, r)] = rng.random() < min(max(p0 + 0.1 * base, 0.01), 0.99)
    return arm1, arm0


def test_gee_recovers_known_risk_difference():
    arm1, arm0 = _synthetic(0.30, 0.15)
    res = fit_endpoint(endpoint="E", model="m", arm1=arm1, arm0=arm0)
    assert res.working_correlation in ("exchangeable", "independence")
    assert abs(res.rd - 0.15) < 0.05
    assert res.se and 0 < res.se < 0.05
    assert res.ci_lo < res.rd < res.ci_hi
    assert res.p < 0.01
    assert res.n_fixtures == 145 and res.n_reps == 3
    assert len(res.per_rep_rd) == 3


def test_gee_null_effect_not_significant():
    arm1, arm0 = _synthetic(0.20, 0.20, seed=11)
    res = fit_endpoint(endpoint="E", model="m", arm1=arm1, arm0=arm0)
    assert abs(res.rd) < 0.05
    assert res.p > 0.05


def test_degenerate_all_zero_cell():
    arm1 = {(f"fx{f}", r): False for f in range(20) for r in (1, 2)}
    arm0 = dict(arm1)
    res = fit_endpoint(endpoint="E", model="m", arm1=arm1, arm0=arm0)
    assert res.working_correlation == "degenerate"
    assert res.rd == 0.0 and res.p == 1.0 and res.se is None


def test_key_mismatch_rejected():
    arm1 = {("a", 1): True}
    arm0 = {("b", 1): False}
    with pytest.raises(ValueError, match="keys differ"):
        fit_endpoint(endpoint="E", model="m", arm1=arm1, arm0=arm0)


def _res(p: float) -> EndpointResult:
    return EndpointResult(
        endpoint="E", model="m", rd=0.0, se=1.0, ci_lo=0, ci_hi=0, p=p,
        working_correlation="exchangeable", n_fixtures=1, n_reps=1,
        arm1_successes=0, arm0_successes=0, n_obs_per_arm=1,
    )


def test_holm_adjustment():
    rs = [_res(0.01), _res(0.04), _res(0.03), _res(0.005), _res(0.20), _res(0.9)]
    holm(rs)
    # sorted p: .005 .01 .03 .04 .20 .9 -> multipliers 6 5 4 3 2 1
    by_p = sorted(rs, key=lambda r: r.p)
    expect = [0.03, 0.05, 0.12, 0.12, 0.40, 0.90]
    for r, e in zip(by_p, expect):
        assert math.isclose(r.holm_adjusted_p, e, rel_tol=1e-9)
