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
  - dP_2 phase I    : hep-th/0205144 W_I (subsection "del Pezzo 2", Model I)
  - dP_3 phase IV   : hep-th/0209228 W_IV ("The Four Phases of dP3")
  - C^3/(Z_2 x Z_2) : arXiv:0704.0262 eq (3.1) + Fig 1
  - SPP             : arXiv:1702.03958 eq (2.3) + Fig 1  (has an adjoint)
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
    "dp2_phase1_electric",
    "dp3_phase4_electric",
    "spp_electric",
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


# ----------------------------------------------------------------------
# dP_2 phase I / Model I  (hep-th/0205144, subsection "del Pezzo 2")
# 5 nodes, 13 bifundamentals; W_I = 6 cubic + 2 quartic terms.
# Paper node k (1..5) -> index k-1; X_{ij} is an arrow node i -> node j.
# Field map (paper -> 0-indexed label):
#   X41 -> X30[0]   X42 -> X31[0]   X54 -> X43[0]   X34 -> X23[0]
#   X31 -> X20[0]   X32 -> X21[0]
#   (X15,Y15) -> X04[0,1]   (X25,Y25) -> X14[0,1]
#   (X53,Y53,Z53) -> X42[0,1,2]
# ----------------------------------------------------------------------


def dp2_phase1_electric(N: int = 2) -> dict[str, Any]:
    p = Fraction(1, 2)  # placeholder R; projected to feasible by r_repair
    arrows = {
        (3, 0): [p],          # X41
        (3, 1): [p],          # X42
        (0, 4): [p, p],       # X15, Y15
        (1, 4): [p, p],       # X25, Y25
        (4, 3): [p],          # X54
        (4, 2): [p, p, p],    # X53, Y53, Z53
        (2, 3): [p],          # X34
        (2, 0): [p],          # X31
        (2, 1): [p],          # X32
    }

    def t(factors, sign: int) -> SuperpotentialTerm:
        return SuperpotentialTerm(
            factors=tuple((f, 1) for f in factors), coefficient=Fraction(sign)
        )

    # W_I = [X41 X15 X54 - X42 X25 X54]
    #       - [X41 Y15 X53 X34 - X42 Y25 Y53 X34]
    #       - [X31 X15 Y53 - X32 X25 X53]
    #       + [X31 Y15 Z53 - X32 Y25 Z53]
    W = (
        t(["X30[0]", "X04[0]", "X43[0]"], +1),                 # +X41 X15 X54
        t(["X31[0]", "X14[0]", "X43[0]"], -1),                 # -X42 X25 X54
        t(["X30[0]", "X04[1]", "X42[0]", "X23[0]"], -1),       # -X41 Y15 X53 X34
        t(["X31[0]", "X14[1]", "X42[1]", "X23[0]"], +1),       # +X42 Y25 Y53 X34
        t(["X20[0]", "X04[0]", "X42[1]"], -1),                 # -X31 X15 Y53
        t(["X21[0]", "X14[0]", "X42[0]"], +1),                 # +X32 X25 X53
        t(["X20[0]", "X04[1]", "X42[2]"], +1),                 # +X31 Y15 Z53
        t(["X21[0]", "X14[1]", "X42[2]"], -1),                 # -X32 Y25 Z53
    )
    theory = pure_quiver_to_json(
        build_pure_quiver(
            ranks=tuple([N] * 5),
            arrows=arrows,
            superpotential=W,
            u1_globals=(u1_r(),),
        )
    )
    return _feasible_seed(theory, name=f"dP_2 phase I N={N}")


# ----------------------------------------------------------------------
# dP_3 phase IV  (hep-th/0209228 eq W_IV, "The Four Phases of dP3")
# Complex cone over del Pezzo 3. Of the four toric phases (W_I sextic,
# W_II quintic, W_III quartic, W_IV all-cubic) we take phase IV: 6 nodes,
# 18 bifundamentals, 12 purely-cubic W terms (the cleanest phase).
# Irrational superconformal R -> consistent-R path. The 2N_c nodes 0/1/2
# are genuine duals (TrR^3 matches) that certify ONLY under R-graded BCR.
# CATALOG-ONLY (deliberately NOT in default_seed_specs): R-graded grading
# cannot be the verifier default because it false-POSITIVES some negatives
# (drop_w_term / flip_w_sign certify under r_charge), which would corrupt the
# benchmark ground truth. Nodes 3/4 give rank-changing duals whose bounded
# chiral ring FAILS even R-graded (a genuine multi-trace gap), excluded too.
# Paper node k (1..6) -> index k-1; X_{ij} is an arrow node i -> node j.
# Field map (paper -> 0-indexed label):
#   X41->X30[0] X42->X31[0] X43->X32[0]  X51->X40[0] X52->X41[0] X53->X42[0]
#   (X16,Y16)->X05[0,1]  (X26,Y26)->X15[0,1]  (X36,Y36)->X25[0,1]
#   (X64,Y64,Z64)->X53[0,1,2]  (X65,Y65,Z65)->X54[0,1,2]
# ----------------------------------------------------------------------


def dp3_phase4_electric(N: int = 2) -> dict[str, Any]:
    p = Fraction(1, 2)  # placeholder R; projected to feasible by r_repair
    arrows = {
        (3, 0): [p], (3, 1): [p], (3, 2): [p],     # X41, X42, X43
        (0, 5): [p, p], (1, 5): [p, p], (2, 5): [p, p],   # X16/Y16, X26/Y26, X36/Y36
        (5, 3): [p, p, p], (5, 4): [p, p, p],       # X64/Y64/Z64, X65/Y65/Z65
        (4, 0): [p], (4, 1): [p], (4, 2): [p],      # X51, X52, X53
    }

    def t(factors, sign: int) -> SuperpotentialTerm:
        return SuperpotentialTerm(
            factors=tuple((f, 1) for f in factors), coefficient=Fraction(sign)
        )

    # W_IV = [X41 X16 X64 + X43 X36 Y64 + X42 X26 Z64]
    #      - [X41 Y16 Y64 + X43 Y36 Z64 + X42 Y26 X64]
    #      + [X51 Y16 X65 + X53 Y36 Y65 + X52 Y26 Z65]
    #      - [X51 X16 Y65 + X53 X36 Z65 + X52 X26 X65]
    W = (
        t(["X30[0]", "X05[0]", "X53[0]"], +1),
        t(["X32[0]", "X25[0]", "X53[1]"], +1),
        t(["X31[0]", "X15[0]", "X53[2]"], +1),
        t(["X30[0]", "X05[1]", "X53[1]"], -1),
        t(["X32[0]", "X25[1]", "X53[2]"], -1),
        t(["X31[0]", "X15[1]", "X53[0]"], -1),
        t(["X40[0]", "X05[1]", "X54[0]"], +1),
        t(["X42[0]", "X25[1]", "X54[1]"], +1),
        t(["X41[0]", "X15[1]", "X54[2]"], +1),
        t(["X40[0]", "X05[0]", "X54[1]"], -1),
        t(["X42[0]", "X25[0]", "X54[2]"], -1),
        t(["X41[0]", "X15[0]", "X54[0]"], -1),
    )
    theory = pure_quiver_to_json(
        build_pure_quiver(
            ranks=tuple([N] * 6),
            arrows=arrows,
            superpotential=W,
            u1_globals=(u1_r(),),
        )
    )
    return _feasible_seed(theory, name=f"dP_3 phase IV N={N}")


# ----------------------------------------------------------------------
# SPP — suspended pinch point  (arXiv:1702.03958 eq W_SPP)
# 3 nodes, 7 fields incl. an ADJOINT X22 at node 2 (0-indexed node 1).
# W = X12 X21 X22 - X22 X23 X32 + X13 X23 X31 X32 - X12 X13 X21 X31.
# Field map (paper -> 0-indexed; X_{ij}=arrow i->j, paper node k->k-1):
#   X12 -> X01[0]  X21 -> X10[0]  X22 -> Phi1[0] (adjoint @ node 1)
#   X23 -> X12[0]  X32 -> X21[0]  X13 -> X02[0]  X31 -> X20[0]
#
# Only the adjoint-free nodes 0 and 2 are dualized (default_seed_specs):
# dualizing node 1 would be a Kutasov-type move on its adjoint, not the
# ordinary SQCD Seiberg duality this engine implements. SPP's quartic W
# terms form "bouquets" that traverse the dualized node twice
# (X12 X13 X21 X31 at node 0; X13 X23 X31 X32 at node 2), so the move needs
# multi-meson premutation (`mutate_bare` collapses each pass independently).
# The resulting dual is genuinely NON-TORIC: the diagonal mesons leave
# gauge singlets (which no brane tiling carries) and relocate the adjoint
# off node 1; it CERTIFIES with TrR^3 matching.
# ----------------------------------------------------------------------


def spp_electric(N: int = 2) -> dict[str, Any]:
    p = Fraction(1, 2)  # placeholder R; projected to feasible by r_repair
    arrows = {
        (0, 1): [p],   # X12
        (1, 0): [p],   # X21
        (1, 1): [p],   # X22  (adjoint at node 1)
        (1, 2): [p],   # X23
        (2, 1): [p],   # X32
        (0, 2): [p],   # X13
        (2, 0): [p],   # X31
    }

    def t(factors, sign: int) -> SuperpotentialTerm:
        return SuperpotentialTerm(
            factors=tuple((f, 1) for f in factors), coefficient=Fraction(sign)
        )

    # Each term reordered into a single closed walk (the trace is cyclic):
    W = (
        t(["X01[0]", "Phi1[0]", "X10[0]"], +1),            # +X12 X22 X21
        t(["Phi1[0]", "X12[0]", "X21[0]"], -1),            # -X22 X23 X32
        t(["X02[0]", "X21[0]", "X12[0]", "X20[0]"], +1),   # +X13 X32 X23 X31
        t(["X01[0]", "X10[0]", "X02[0]", "X20[0]"], -1),   # -X12 X21 X13 X31
    )
    theory = pure_quiver_to_json(
        build_pure_quiver(
            ranks=tuple([N] * 3),
            arrows=arrows,
            superpotential=W,
            u1_globals=(u1_r(),),
        )
    )
    return _feasible_seed(theory, name=f"SPP N={N}")
