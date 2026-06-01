"""Seed (electric) theories for fixture generation.

These mirror the locked positive sources in
`scripts/generate_detection_fixtures.py` (dP_0 at N=3/4 and the F_0
phase-II quiver), kept here as an importable library so the experiment
generator does not depend on a script module. Two distinct families are
provided so `wrong_pair` (cross-family) is meaningful.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Callable

from dualitycert.core.objects import SuperpotentialTerm
from dualitycert.experiments.seed_catalog import (
    c3_z2z2_electric,
    dp1_electric,
    dp2_phase1_electric,
)
from dualitycert.groups.u1 import u1_r
from dualitycert.qft.pure_quiver_builder import (
    arrow_names,
    build_pure_quiver,
    dp0_superpotential,
)
from dualitycert.qft.pure_quiver_json import pure_quiver_to_json


__all__ = ["SeedSpec", "default_seed_specs", "dp0_electric", "f0_phase_ii_electric"]


def dp0_electric(N: int) -> dict[str, Any]:
    """dP_0 toric phase: SU(N)^3 cyclic, 9 bifundamentals, cubic W."""

    n01 = arrow_names(0, 1, 3)
    n12 = arrow_names(1, 2, 3)
    n20 = arrow_names(2, 0, 3)
    return pure_quiver_to_json(
        build_pure_quiver(
            ranks=(N, N, N),
            arrows={
                (0, 1): [Fraction(2, 3)] * 3,
                (1, 2): [Fraction(2, 3)] * 3,
                (2, 0): [Fraction(2, 3)] * 3,
            },
            superpotential=dp0_superpotential(n01, n12, n20),
            u1_globals=(u1_r(),),
        )
    )


def f0_phase_ii_electric(N: int) -> dict[str, Any]:
    """F_0 phase-II quiver (4 nodes), distinct family from dP_0."""

    def eps(a: int, b: int) -> int:
        if (a, b) == (0, 1):
            return 1
        if (a, b) == (1, 0):
            return -1
        return 0

    R_BD = Fraction(1, 2)
    R_DI = Fraction(1, 1)
    W: list[SuperpotentialTerm] = []
    for a, i, alpha, beta in itertools.product(range(2), repeat=4):
        sign = eps(a, alpha) * eps(i, beta)
        if sign == 0:
            continue
        W.append(
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
        W.append(
            SuperpotentialTerm(
                factors=(
                    (f"X03[{a}]", 1),
                    (f"X32[{i}]", 1),
                    (f"X20[{2 * alpha + beta}]", 1),
                ),
                coefficient=Fraction(-sign),
            )
        )
    return pure_quiver_to_json(
        build_pure_quiver(
            ranks=(N, N, N, N),
            arrows={
                (0, 1): [R_BD] * 2,
                (0, 3): [R_BD] * 2,
                (2, 0): [R_DI] * 4,
                (1, 2): [R_BD] * 2,
                (3, 2): [R_BD] * 2,
            },
            superpotential=tuple(W),
            u1_globals=(u1_r(),),
        )
    )


@dataclass(frozen=True)
class SeedSpec:
    """One positive source: a seed electric theory + the node to dualize."""

    source_name: str
    builder: Callable[[int], dict[str, Any]]
    node: int
    N: int

    def electric(self) -> dict[str, Any]:
        return self.builder(self.N)


def default_seed_specs() -> list[SeedSpec]:
    """Positive sources for the paper dataset (five independent families).

    The two locked MVP families (dP_0, F_0 phase II) plus three curated
    catalog families that now certify through the real generation path:
    C^3/(Z_2 x Z_2) (non-chiral; magnetic side carries gauge singlets, so
    `run_verifier` auto-grades its chiral ring by R-charge), dP_1 and dP_2
    phase I (irrational superconformal R; the depth-1 path picks the
    consistent R representative so the magnetic R is the exact duality
    image). The pinned dP_2 nodes (3, 4) certify under the default chiral-
    ring grading; its other nodes are equally valid duals (TrR^3 matches)
    but only certify under R-graded BCR, so they are left out here.
    """

    return [
        SeedSpec("dp0_toric", dp0_electric, node=0, N=3),
        SeedSpec("dp0_toric", dp0_electric, node=1, N=3),
        SeedSpec("dp0_toric", dp0_electric, node=2, N=3),
        SeedSpec("dp0_toric", dp0_electric, node=0, N=4),
        SeedSpec("f0_phase_ii", f0_phase_ii_electric, node=0, N=3),
        SeedSpec("f0_phase_ii", f0_phase_ii_electric, node=2, N=3),
        SeedSpec("c3_z2z2", c3_z2z2_electric, node=0, N=2),
        SeedSpec("c3_z2z2", c3_z2z2_electric, node=1, N=2),
        SeedSpec("dp1", dp1_electric, node=0, N=2),
        SeedSpec("dp1", dp1_electric, node=1, N=2),
        SeedSpec("dp2_phase1", dp2_phase1_electric, node=3, N=2),
        SeedSpec("dp2_phase1", dp2_phase1_electric, node=4, N=2),
    ]
