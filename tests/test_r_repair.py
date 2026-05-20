"""Phase 2c1 R-repair tests.

Five fixtures pin the table in docs/phase2c1_r_repair.md §3:

  - dP_0 magnetic effective: trial R is already feasible (dim=2 affine
    space), so repair is a no-op.
  - F_0 II electric trial: trial R is already feasible (dim=3),
    repair is a no-op.
  - F_0 II engine output (mutate_bare + integrate_linear_fields at
    node 0): trial R is NOT feasible (the boundary regression);
    L2-projection changes 8 fields by ±1/3 in the patterns
    locked by docs §3.
  - Constructed infeasible toy: status="infeasible", representative=None.
  - Constructed 0-dim toy: rank == n_fields, unique feasible R.
"""

from __future__ import annotations

import itertools
from fractions import Fraction

import pytest

from dualitycert.core.objects import SuperpotentialTerm
from dualitycert.groups.u1 import u1_r
from dualitycert.qft.mutation_engine import (
    integrate_linear_fields,
    mutate_bare,
)
from dualitycert.qft.pure_quiver_builder import (
    build_dp0_magnetic_effective,
    build_pure_quiver,
)
from dualitycert.qft.pure_quiver_json import (
    pure_quiver_from_json,
    pure_quiver_to_json,
)
from dualitycert.qft.r_repair import RRepairError, repair_r_charges


# ----------------------------------------------------------------------
# Shared F_0 II electric fixture (mirrors the one in
# tests/test_mutation_engine.py — duplicated here intentionally so the
# r_repair test file has no import-order coupling to test files).
# ----------------------------------------------------------------------


def _electric_f0_phase_ii_trial(N: int = 3):
    def eps(a: int, b: int) -> int:
        if (a, b) == (0, 1):
            return 1
        if (a, b) == (1, 0):
            return -1
        return 0

    R_BD = Fraction(1, 2)
    R_DI = Fraction(1, 1)

    W_terms: list[SuperpotentialTerm] = []
    for a, i, alpha, beta in itertools.product(range(2), repeat=4):
        sign = eps(a, alpha) * eps(i, beta)
        if sign == 0:
            continue
        W_terms.append(
            SuperpotentialTerm(
                factors=(
                    (f"X01[{a}]", 1),
                    (f"X12[{i}]", 1),
                    (f"X20[{2 * alpha + beta}]", 1),
                ),
                coefficient=Fraction(sign),
            )
        )
    for a, i, alpha, beta in itertools.product(range(2), repeat=4):
        sign = eps(a, alpha) * eps(i, beta)
        if sign == 0:
            continue
        W_terms.append(
            SuperpotentialTerm(
                factors=(
                    (f"X03[{a}]", 1),
                    (f"X32[{i}]", 1),
                    (f"X20[{2 * alpha + beta}]", 1),
                ),
                coefficient=Fraction(-sign),
            )
        )

    return build_pure_quiver(
        ranks=(N, N, N, N),
        arrows={
            (0, 1): [R_BD] * 2,
            (0, 3): [R_BD] * 2,
            (2, 0): [R_DI] * 4,
            (1, 2): [R_BD] * 2,
            (3, 2): [R_BD] * 2,
        },
        superpotential=tuple(W_terms),
        u1_globals=(u1_r(),),
    )


# ----------------------------------------------------------------------
# 1. dP_0 magnetic effective: trial already feasible, dim=2, no-op repair.
# ----------------------------------------------------------------------


def test_dp0_magnetic_effective_repair_is_noop():
    """Trial R on `build_dp0_magnetic_effective` already satisfies
    every W and anomaly constraint. R-repair returns
    `trial_feasible=True`, `changed_fields=[]`, and a 2-dimensional
    affine kernel (the flavor/baryonic U(1) directions that the linear
    system cannot pin down without a-maximization).
    """

    theory_json = pure_quiver_to_json(build_dp0_magnetic_effective(N=3))
    result = repair_r_charges(theory_json)

    assert result["trial_feasible"] is True
    assert result["status"] == "underdetermined"
    assert result["dimension"] == 2
    assert result["changed_fields"] == []
    assert result["failure_reason"] is None
    assert result["representative"] is not None

    # Repaired arrows reproduce the trial R-charges exactly.
    trial_by_label = {a["label"]: a["r_charge"] for a in theory_json["arrows"]}
    repaired_by_label = {
        a["label"]: a["r_charge"] for a in result["representative"]["arrows"]
    }
    for label in trial_by_label:
        assert Fraction(repaired_by_label[label]) == Fraction(trial_by_label[label])

    # feasible_space.particular_solution agrees with representative.
    for label, value in result["feasible_space"]["particular_solution"].items():
        assert Fraction(value) == Fraction(repaired_by_label[label])
    assert len(result["feasible_space"]["homogeneous_basis"]) == 2


# ----------------------------------------------------------------------
# 2. F_0 II electric trial: trial already feasible, dim=3, no-op repair.
# ----------------------------------------------------------------------


def test_f0_phase_ii_electric_trial_repair_is_noop():
    """The F_0 II electric fixture self-certifies, so its trial R
    already lies in the feasible affine space. Repair is a no-op and
    reports `dimension=3` (the flavor mixing dimension).
    """

    theory_json = pure_quiver_to_json(_electric_f0_phase_ii_trial(N=3))
    result = repair_r_charges(theory_json)

    assert result["trial_feasible"] is True
    assert result["status"] == "underdetermined"
    assert result["dimension"] == 3
    assert result["changed_fields"] == []
    assert result["representative"] is not None
    assert len(result["feasible_space"]["homogeneous_basis"]) == 3


# ----------------------------------------------------------------------
# 3. F_0 II engine output: trial R fails, repair fixes 8 fields.
# ----------------------------------------------------------------------


def test_f0_phase_ii_engine_output_repair_changes_eight_fields():
    """The Phase 2c0 → 2c1 boundary regression.

    The engine output's trial R has R(reversed-diagonal)=0 and
    R(reversed-boundary)=1/2, which fails SU(N)² × U(1)_R at non-
    dualized nodes. The L2 projection moves all 4 reversed-diagonal
    fields by +1/3 and all 4 reversed-boundary fields by -1/3 (the
    meson R-charges stay fixed at 3/2 because they're the L2-minimum
    point in the kernel direction).
    """

    electric = _electric_f0_phase_ii_trial(N=3)
    engine_out = integrate_linear_fields(
        mutate_bare(pure_quiver_to_json(electric), node=0)
    )
    result = repair_r_charges(engine_out)

    assert result["trial_feasible"] is False
    assert result["status"] == "underdetermined"
    assert result["dimension"] == 3
    assert result["failure_reason"] is None

    # Exactly 8 fields changed.
    assert len(result["changed_fields"]) == 8

    changed_by_label = {c["label"]: (c["from"], c["to"]) for c in result["changed_fields"]}

    # Reversed diagonal X02[0..3]: 0 → 1/3.
    for k in range(4):
        label = f"X02[{k}]"
        assert label in changed_by_label, f"expected {label!r} in changed_fields"
        f, t = changed_by_label[label]
        assert Fraction(f) == Fraction(0)
        assert Fraction(t) == Fraction(1, 3)

    # Reversed top X10[0..1]: 1/2 → 1/6.
    for k in range(2):
        label = f"X10[{k}]"
        assert label in changed_by_label
        f, t = changed_by_label[label]
        assert Fraction(f) == Fraction(1, 2)
        assert Fraction(t) == Fraction(1, 6)

    # Reversed left X30[0..1]: 1/2 → 1/6.
    for k in range(2):
        label = f"X30[{k}]"
        assert label in changed_by_label
        f, t = changed_by_label[label]
        assert Fraction(f) == Fraction(1, 2)
        assert Fraction(t) == Fraction(1, 6)

    # Mesons X21[0..5] and X23[0..5] are not in changed_fields.
    for k in range(6):
        assert f"X21[{k}]" not in changed_by_label
        assert f"X23[{k}]" not in changed_by_label

    # Sanity-check the representative round-trips through pure_quiver_from_json.
    pure_quiver_from_json(result["representative"])


# ----------------------------------------------------------------------
# 4. Infeasible toy: SU(2) × SU(2) with W = X01·X10 length-2 mass loop.
# ----------------------------------------------------------------------


def test_infeasible_toy_reports_infeasible():
    """Constructed infeasible 2-node mass loop.

    Geometry: SU(2) × SU(2) with one bifundamental each way (X01[0]
    and X10[0]) and a W = X01[0] · X10[0] mass term. The W constraint
    forces R(X01) + R(X10) = 2, but the node-0 anomaly forces
    R(X01) + R(X10) = 0 (the gaugino's +N_0 cancels against the
    same-rank D_v factor without enough field content to compensate).
    System is inconsistent; R-repair returns `status: "infeasible"`.
    """

    theory_json = {
        "name": "Infeasible 2-node mass loop",
        "node_labels": ["SU(2)_0", "SU(2)_1"],
        "ranks": [2, 2],
        "u1_globals": ["U(1)_R"],
        "arrows": [
            {"label": "X01[0]", "source": 0, "target": 1, "r_charge": "1"},
            {"label": "X10[0]", "source": 1, "target": 0, "r_charge": "1"},
        ],
        "superpotential": [
            {"factors": ["X01[0]", "X10[0]"], "coefficient": "1"},
        ],
    }

    result = repair_r_charges(theory_json)

    assert result["status"] == "infeasible"
    assert result["dimension"] is None
    assert result["trial_feasible"] is False
    assert result["representative"] is None
    assert result["feasible_space"] is None
    assert result["changed_fields"] == []
    assert result["failure_reason"] is not None
    assert "inconsistent" in result["failure_reason"]


# ----------------------------------------------------------------------
# 5. 0-dim toy: single adjoint at SU(3), R uniquely pinned to 0.
# ----------------------------------------------------------------------


def test_zero_dim_toy_single_adjoint_uniquely_determined():
    """Constructed 0-dim toy: single SU(3) gauge node with one adjoint
    chiral, no W. The anomaly constraint
    `T(adj) · (R − 1) + T(adj) = 0` reduces to `3 (R − 1) + 3 = 0`,
    i.e. `R = 0`. System has rank 1 = n_fields → dimension 0.
    """

    theory_json = {
        "name": "Single-adjoint 0-dim toy",
        "node_labels": ["SU(3)_0"],
        "ranks": [3],
        "u1_globals": ["U(1)_R"],
        "arrows": [
            {"label": "Phi0[0]", "source": 0, "target": 0, "r_charge": "1"},
        ],
        "superpotential": [],
    }

    result = repair_r_charges(theory_json)

    assert result["status"] == "unique"
    assert result["dimension"] == 0
    assert result["trial_feasible"] is False  # trial was R=1, repaired is R=0
    assert result["representative"] is not None
    assert result["feasible_space"]["homogeneous_basis"] == []

    repaired_r = result["representative"]["arrows"][0]["r_charge"]
    assert Fraction(repaired_r) == Fraction(0)

    assert len(result["changed_fields"]) == 1
    assert result["changed_fields"][0] == {
        "label": "Phi0[0]",
        "from": "1",
        "to": "0",
    }


# ----------------------------------------------------------------------
# Guardrail tests for unsupported options.
# ----------------------------------------------------------------------


def test_unsupported_tie_mode_raises():
    theory_json = pure_quiver_to_json(build_dp0_magnetic_effective(N=3))
    with pytest.raises(RRepairError, match="tie_mode"):
        repair_r_charges(theory_json, tie_mode="edge_family")


def test_unsupported_representative_raises():
    theory_json = pure_quiver_to_json(build_dp0_magnetic_effective(N=3))
    with pytest.raises(RRepairError, match="representative"):
        repair_r_charges(theory_json, representative="a_max")
