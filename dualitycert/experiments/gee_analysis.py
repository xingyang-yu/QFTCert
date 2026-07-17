"""Frozen primary analysis for the confirmatory phase (protocol section 7).

For each model and endpoint: marginal binomial GEE with logit link, arm and
replication fixed effects, fixture ID as the clustering unit, exchangeable
working correlation, and robust sandwich covariance. The reported effect is
the standardized marginal risk difference: predict each arm at every
observed replication level, average predictions equally over replication
levels and the fixed fixtures, and subtract; its 95% CI comes from the
delta method on the robust covariance. A logged numerical failure of the
exchangeable fit triggers ONLY a refit with independence working
correlation (same mean model, same robust covariance). Identity-link GEE
and fixture bootstrap are excluded by the protocol.

Primary family: {E1 vf-gr, E2 gr-ss, E4 portfolio-control} x {qwen,
deepseek}, one paper-wide Holm adjustment across the six hypotheses.
E3 (vf@1-gr@1) and E5 (vf - vf_masked, own two-hypothesis Holm family)
are secondary.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import numpy as np

__all__ = [
    "EndpointResult",
    "fit_endpoint",
    "holm",
    "load_arm_outcomes",
    "load_portfolio_outcomes",
    "load_at1_outcomes",
    "analyze_confirmatory",
]


# ----------------------------------------------------------------------
# Data loading. Outcomes are dicts (fixture_id, rep) -> bool per arm.
# ----------------------------------------------------------------------


def load_arm_outcomes(
    run_dirs: Mapping[int, Path | str],
) -> dict[tuple[str, int], bool]:
    """{rep -> run dir} -> {(fixture_id, rep) -> success}."""
    out: dict[tuple[str, int], bool] = {}
    for rep, run_dir in run_dirs.items():
        path = Path(run_dir) / "repair_results.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            key = (rec["fixture_id"], rep)
            if key in out:
                raise ValueError(f"duplicate {key} in {path}")
            out[key] = bool(rec["success"])
    return out


def load_at1_outcomes(
    run_dirs: Mapping[int, Path | str],
) -> dict[tuple[str, int], bool]:
    """success@1 (E3): success with success_round == 1."""
    out: dict[tuple[str, int], bool] = {}
    for rep, run_dir in run_dirs.items():
        path = Path(run_dir) / "repair_results.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            out[(rec["fixture_id"], rep)] = bool(
                rec["success"] and rec.get("success_round") == 1
            )
    return out


def load_portfolio_outcomes(
    e4_dirs: Mapping[int, Path | str],
) -> dict[tuple[str, int], bool]:
    """{rep -> e4 replay dir} -> {(fixture_id, rep) -> portfolio_success}."""
    out: dict[tuple[str, int], bool] = {}
    for rep, e4_dir in e4_dirs.items():
        path = Path(e4_dir) / "e4_replay.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            out[(rec["fixture_id"], rep)] = bool(rec["portfolio_success"])
    return out


# ----------------------------------------------------------------------
# GEE fit.
# ----------------------------------------------------------------------


@dataclass
class EndpointResult:
    endpoint: str
    model: str
    rd: float
    se: float | None
    ci_lo: float | None
    ci_hi: float | None
    p: float
    working_correlation: str  # exchangeable | independence | degenerate
    n_fixtures: int
    n_reps: int
    arm1_successes: int
    arm0_successes: int
    n_obs_per_arm: int
    per_rep_rd: list[float] = field(default_factory=list)
    holm_adjusted_p: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def _design(arm: np.ndarray, rep: np.ndarray) -> np.ndarray:
    """Columns: intercept, arm, rep dummies (first rep level = reference)."""
    levels = sorted(set(rep.tolist()))
    cols = [np.ones_like(arm, dtype=float), arm.astype(float)]
    for lv in levels[1:]:
        cols.append((rep == lv).astype(float))
    return np.column_stack(cols)


def fit_endpoint(
    *,
    endpoint: str,
    model: str,
    arm1: Mapping[tuple[str, int], bool],
    arm0: Mapping[tuple[str, int], bool],
) -> EndpointResult:
    """Fit the frozen GEE for one endpoint and standardize to a marginal RD.

    `arm1`/`arm0` map (fixture_id, rep) to the binary outcome for the two
    arms of the contrast (RD = P(arm1) - P(arm0) averaged over reps and
    fixtures).
    """
    if set(arm1) != set(arm0):
        raise ValueError(
            f"{endpoint}/{model}: arm outcome keys differ "
            f"(symmetric difference size {len(set(arm1) ^ set(arm0))})"
        )
    keys = sorted(arm1)
    fixtures = sorted({k[0] for k in keys})
    reps = sorted({k[1] for k in keys})
    fix_index = {f: i for i, f in enumerate(fixtures)}

    y = np.array([float(arm1[k]) for k in keys] + [float(arm0[k]) for k in keys])
    arm = np.array([1] * len(keys) + [0] * len(keys))
    rep = np.array([k[1] for k in keys] * 2)
    groups = np.array([fix_index[k[0]] for k in keys] * 2)

    s1 = int(sum(arm1[k] for k in keys))
    s0 = int(sum(arm0[k] for k in keys))
    per_rep_rd = [
        (
            sum(arm1[k] for k in keys if k[1] == r)
            - sum(arm0[k] for k in keys if k[1] == r)
        )
        / sum(1 for k in keys if k[1] == r)
        for r in reps
    ]

    base = dict(
        endpoint=endpoint,
        model=model,
        n_fixtures=len(fixtures),
        n_reps=len(reps),
        arm1_successes=s1,
        arm0_successes=s0,
        n_obs_per_arm=len(keys),
        per_rep_rd=per_rep_rd,
    )

    # Degenerate cells (no successes, or all successes, in the pooled data)
    # make the logit fit separate; report the raw RD with no test.
    if (s1 + s0) == 0 or (s1 + s0) == 2 * len(keys):
        rd = (s1 - s0) / len(keys)
        return EndpointResult(
            rd=rd, se=None, ci_lo=None, ci_hi=None, p=1.0,
            working_correlation="degenerate", **base,
        )

    X = _design(arm, rep)

    import statsmodels.api as sm

    def _fit(cov_struct):
        gee = sm.GEE(
            y, X, groups=groups,
            family=sm.families.Binomial(),
            cov_struct=cov_struct,
        )
        return gee.fit(maxiter=200)

    working = "exchangeable"
    try:
        res = _fit(sm.cov_struct.Exchangeable())
        if not np.all(np.isfinite(res.params)) or not np.all(
            np.isfinite(np.diag(res.cov_params()))
        ):
            raise RuntimeError("non-finite exchangeable fit")
    except Exception:
        # Frozen numerical fallback: same mean model, independence working
        # correlation, same robust covariance.
        working = "independence"
        res = _fit(sm.cov_struct.Independence())

    beta = np.asarray(res.params)
    V = np.asarray(res.cov_params())

    # Standardized marginal RD over the observed (fixture, rep) cells:
    # both arms predicted at every cell, equal weights.
    X1 = _design(np.ones(len(keys)), np.array([k[1] for k in keys]))
    X0 = _design(np.zeros(len(keys)), np.array([k[1] for k in keys]))

    def _expit(z: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-z))

    p1 = _expit(X1 @ beta)
    p0 = _expit(X0 @ beta)
    rd = float(np.mean(p1 - p0))
    grad = np.mean(
        (p1 * (1 - p1))[:, None] * X1 - (p0 * (1 - p0))[:, None] * X0, axis=0
    )
    var = float(grad @ V @ grad)
    se = math.sqrt(var) if var > 0 else None
    if se:
        z = rd / se
        p = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0))))
        ci_lo, ci_hi = rd - 1.96 * se, rd + 1.96 * se
    else:
        p, ci_lo, ci_hi = 1.0, None, None

    return EndpointResult(
        rd=rd, se=se, ci_lo=ci_lo, ci_hi=ci_hi, p=p,
        working_correlation=working, **base,
    )


def holm(results: list[EndpointResult]) -> None:
    """Holm step-down adjustment in place over one hypothesis family."""
    order = sorted(range(len(results)), key=lambda i: results[i].p)
    m = len(results)
    running = 0.0
    for rank, i in enumerate(order):
        adj = min(1.0, (m - rank) * results[i].p)
        running = max(running, adj)  # enforce monotonicity
        results[i].holm_adjusted_p = running


# ----------------------------------------------------------------------
# Full confirmatory assembly.
# ----------------------------------------------------------------------


def analyze_confirmatory(
    *,
    runs_root: Path | str,
    models: Mapping[str, str],
    reps: tuple[int, ...] = (1, 2, 3),
    out_dir: Path | str,
) -> dict[str, Any]:
    """Assemble and fit the frozen endpoint families.

    `models` maps a model label to the run-id prefix, e.g.
    {"deepseek": "conf_deepseek", "qwen": "conf_qwen"}. Expects run ids
    <prefix>_<arm>_r<rep> and e4 dirs <prefix>_e4_r<rep> under runs_root.
    """
    root = Path(runs_root)

    def arm_dirs(prefix: str, arm: str) -> dict[int, Path]:
        return {r: root / f"{prefix}_{arm}_r{r}" for r in reps}

    primary: list[EndpointResult] = []
    secondary_e5: list[EndpointResult] = []
    secondary_e3: list[EndpointResult] = []

    for label, prefix in models.items():
        ss = load_arm_outcomes(arm_dirs(prefix, "single_shot_repair"))
        gr = load_arm_outcomes(arm_dirs(prefix, "generic_retry"))
        vf = load_arm_outcomes(arm_dirs(prefix, "verifier_feedback"))
        masked = load_arm_outcomes(arm_dirs(prefix, "vf_masked"))
        control = load_arm_outcomes(arm_dirs(prefix, "best_of_n"))
        portfolio = load_portfolio_outcomes(
            {r: root / f"{prefix}_e4_r{r}" for r in reps}
        )
        primary.append(
            fit_endpoint(endpoint="E1_vf_vs_gr", model=label, arm1=vf, arm0=gr)
        )
        primary.append(
            fit_endpoint(endpoint="E2_gr_vs_ss", model=label, arm1=gr, arm0=ss)
        )
        primary.append(
            fit_endpoint(
                endpoint="E4_portfolio_vs_control",
                model=label,
                arm1=portfolio,
                arm0=control,
            )
        )
        secondary_e5.append(
            fit_endpoint(
                endpoint="E5_vf_vs_masked", model=label, arm1=vf, arm0=masked
            )
        )
        secondary_e3.append(
            fit_endpoint(
                endpoint="E3_vf_at1_vs_gr_at1",
                model=label,
                arm1=load_at1_outcomes(arm_dirs(prefix, "verifier_feedback")),
                arm0=load_at1_outcomes(arm_dirs(prefix, "generic_retry")),
            )
        )

    holm(primary)
    holm(secondary_e5)
    # E3 is reported with effect + interval only (no family claim).

    report = {
        "protocol": "paper/analysis_protocol.md (frozen 813fdb0)",
        "primary_family_holm": [r.to_dict() for r in primary],
        "secondary_e5_family_holm": [r.to_dict() for r in secondary_e5],
        "secondary_e3_descriptive": [r.to_dict() for r in secondary_e3],
    }
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "confirmatory_analysis.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report
