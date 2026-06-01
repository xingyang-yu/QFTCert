"""Literature-curated seed theories for the paper-main seed set (Phase 2d-ext).

Each builder encodes a toric quiver gauge theory transcribed from a cited
source into the repo's 0-indexed pure-quiver convention (arrow i->j is
label ``X{i}{j}[k]``; adjoint at i is ``Phi{i}[k]``; W factors are listed
in closed-walk order). R-charges are assigned by rational feasibility:
each builder seeds a placeholder R and projects onto the feasible affine
space {R(W)=2, SU(N)^2 U(1)_R anomaly-free} via `repair_r_charges`
(the superconformal R is generically irrational; a rational feasible R
gives the same duality verdicts — see docs/experiments.md).

Sources (verify against the paper before trusting):
  - dP_1            : hep-th/0205144 ("Symmetries of Toric Duality") eq (4.7)
  - dP_2 phase I    : hep-th/0205144 W_I (sec 4.5)
  - C^3/(Z_2 x Z_2) : arXiv:0704.0262 eq (3.1) + Fig 1
  - SPP             : arXiv:1702.03958 eq (2.3) + Fig 1  (has an adjoint)

STATUS: under physics verification. Not yet wired into
`default_seed_specs`; exercised by the seed health-check first.
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

from dualitycert.core.objects import SuperpotentialTerm
from dualitycert.groups.u1 import u1_r
from dualitycert.qft.pure_quiver_builder import build_pure_quiver
from dualitycert.qft.pure_quiver_json import pure_quiver_to_json
from dualitycert.qft.r_repair import repair_r_charges


__all__ = [
    "c3_z2z2_electric",
    "dp1_electric",
]


def _feasible_seed(theory_json: dict[str, Any], *, name: str) -> dict[str, Any]:
    """Project the placeholder R onto a rational feasible assignment.

    Raises ValueError if the linear feasibility system is inconsistent —
    that signals a transcription error in the quiver/superpotential.
    """

    repaired = repair_r_charges(theory_json)
    if repaired["status"] == "infeasible":
        raise ValueError(
            f"seed {name!r} has no feasible R-charge assignment "
            f"(R(W)=2 + anomaly inconsistent): {repaired['failure_reason']}. "
            "This usually means the quiver or superpotential was transcribed "
            "incorrectly."
        )
    out = repaired["representative"]
    out["name"] = name
    return out


# ----------------------------------------------------------------------
# C^3/(Z_2 x Z_2) orbifold  (arXiv:0704.0262 eq 3.1 + Fig 1)
# 4 nodes SU(N)^4, complete K4 bidirectional (12 bifundamentals,
# non-chiral), purely cubic 8-term W. Paper node a (1..4) -> index a-1.
# ----------------------------------------------------------------------


def c3_z2z2_electric(N: int = 2) -> dict[str, Any]:
    r = Fraction(2, 3)  # cubic theory: R = 2/3 is already feasible
    arrows = {
        (i, j): [r] for i in range(4) for j in range(4) if i != j
    }

    def term(a: int, b: int, c: int, sign: int) -> SuperpotentialTerm:
        # closed 3-walk a->b->c->a using the single arrow on each edge.
        return SuperpotentialTerm(
            factors=(
                (f"X{a}{b}[0]", 1),
                (f"X{b}{c}[0]", 1),
                (f"X{c}{a}[0]", 1),
            ),
            coefficient=Fraction(sign),
        )

    # eq (3.1), Phi_ab -> arrow (a-1)->(b-1):
    W = (
        term(0, 1, 2, +1),  # +Phi12 Phi23 Phi31
        term(0, 2, 1, -1),  # -Phi13 Phi32 Phi21
        term(0, 2, 3, +1),  # +Phi13 Phi34 Phi41
        term(0, 3, 2, -1),  # -Phi14 Phi43 Phi31
        term(0, 3, 1, +1),  # +Phi14 Phi42 Phi21
        term(0, 1, 3, -1),  # -Phi12 Phi24 Phi41
        term(1, 3, 2, +1),  # +Phi24 Phi43 Phi32
        term(1, 2, 3, -1),  # -Phi23 Phi34 Phi42
    )
    theory = pure_quiver_to_json(
        build_pure_quiver(
            ranks=tuple([N] * 4),
            arrows=arrows,
            superpotential=W,
            u1_globals=(u1_r(),),
        )
    )
    return _feasible_seed(theory, name=f"C3/(Z2xZ2) orbifold N={N}")


# ----------------------------------------------------------------------
# dP_1  (hep-th/0205144 eq 4.7, Fig 11)
# 4 nodes, 10 bifundamentals; W = 2 cubic + 1 quartic (eps_ab expanded).
# Paper node k (1..4) -> index k-1. Field map (0-indexed labels):
#   X12 -> X01[0]   X13 -> X02[0]   X42 -> X31[0]
#   X34^{1,2,3} -> X23[0..2]   X41^{1,2} -> X30[0,1]   X23^{1,2} -> X12[0,1]
# ----------------------------------------------------------------------


def dp1_electric(N: int = 2) -> dict[str, Any]:
    p = Fraction(1, 2)  # placeholder R; projected to feasible by r_repair
    arrows = {
        (0, 1): [p],          # X12
        (0, 2): [p],          # X13
        (3, 1): [p],          # X42
        (2, 3): [p, p, p],    # X34^{1,2,3}
        (3, 0): [p, p],       # X41^{1,2}
        (1, 2): [p, p],       # X23^{1,2}
    }

    def t(factors, sign: int) -> SuperpotentialTerm:
        return SuperpotentialTerm(
            factors=tuple((f, 1) for f in factors), coefficient=Fraction(sign)
        )

    # eq 4.7 with eps_ab expanded (eps_12 = +1):
    #  T1 = eps_ab X34^a X41^b X13   (cubic, walk 2->3->0->2)
    #  T2 = -eps_ab X34^a X23^b X42  (cubic, walk 2->3->1->2)
    #  T3 = eps_ab X12 X34^3 X41^a X23^b (quartic, walk 0->1->2->3->0)
    W = (
        t(["X23[0]", "X30[1]", "X02[0]"], +1),                 # +X34^1 X41^2 X13
        t(["X23[1]", "X30[0]", "X02[0]"], -1),                 # -X34^2 X41^1 X13
        t(["X23[0]", "X31[0]", "X12[1]"], -1),                 # -X34^1 X42 X23^2
        t(["X23[1]", "X31[0]", "X12[0]"], +1),                 # +X34^2 X42 X23^1
        t(["X01[0]", "X12[1]", "X23[2]", "X30[0]"], +1),       # +X12 X23^2 X34^3 X41^1
        t(["X01[0]", "X12[0]", "X23[2]", "X30[1]"], -1),       # -X12 X23^1 X34^3 X41^2
    )
    theory = pure_quiver_to_json(
        build_pure_quiver(
            ranks=tuple([N] * 4),
            arrows=arrows,
            superpotential=W,
            u1_globals=(u1_r(),),
        )
    )
    return _feasible_seed(theory, name=f"dP_1 N={N}")
