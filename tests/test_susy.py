"""Gauge-invariance checks for superpotential terms (susy.py).

Focus: the single-trace closed-loop acceptance added so that a W term
which visits a gauge node multiple times (3 fund + 3 antifund, etc.) is
recognized as Tr of one closed loop — gauge invariant — even though the
per-node rep multiset test `_contains_singlet` is too coarse to certify
it on its own.
"""

from __future__ import annotations

from fractions import Fraction

from dualitycert.core.objects import SuperpotentialTerm
from dualitycert.core.status import Status
from dualitycert.qft.pure_quiver_builder import build_pure_quiver
from dualitycert.qft.susy import superpotential_invariance


def _term(labels: list[str]) -> SuperpotentialTerm:
    return SuperpotentialTerm(
        factors=tuple((label, 1) for label in labels), coefficient=Fraction(1)
    )


def test_invariance_accepts_single_trace_multivisit_loop():
    """A single closed walk that re-enters node 0 (0->1->0->1->0) is the
    trace of one loop and must be accepted, even though node 0 carries
    2 fundamentals + 2 antifundamentals."""

    theory = build_pure_quiver(
        ranks=(2, 2),
        arrows={(0, 1): [Fraction(1, 2)], (1, 0): [Fraction(1, 2)]},
        superpotential=(_term(["X01[0]", "X10[0]", "X01[0]", "X10[0]"]),),
    )
    result = superpotential_invariance(theory)
    assert result.status == Status.CERTIFIED


def test_invariance_rejects_open_path():
    """An open walk 0->1->2 (not a closed loop) is not gauge invariant."""

    theory = build_pure_quiver(
        ranks=(2, 2, 2),
        arrows={(0, 1): [Fraction(1, 2)], (1, 2): [Fraction(1, 2)]},
        superpotential=(_term(["X01[0]", "X12[0]"]),),
    )
    result = superpotential_invariance(theory)
    assert result.status == Status.FAILED


def test_invariance_still_accepts_ordinary_single_visit_loop():
    """Regression: an ordinary single-visit closed triangle stays valid."""

    theory = build_pure_quiver(
        ranks=(2, 2, 2),
        arrows={
            (0, 1): [Fraction(2, 3)],
            (1, 2): [Fraction(2, 3)],
            (2, 0): [Fraction(2, 3)],
        },
        superpotential=(_term(["X01[0]", "X12[0]", "X20[0]"]),),
    )
    result = superpotential_invariance(theory)
    assert result.status == Status.CERTIFIED
