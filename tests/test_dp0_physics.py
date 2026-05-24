"""Phase 2a+ physics-hardening tests for dP_0 (cone over C^3/Z_3).

These exercise the verifier end-to-end on a real superpotential (the
antisymmetric ε_{abc} X^a_{01} X^b_{12} X^c_{20} of the dP_0 toric phase),
running through evaluate_claim at the default cutoff L=6 and at the
P6 cap L=8. Unlike the algorithm-level tests in test_quiver_chiral_ring.py
which exercise the primitives in isolation on a 2-node toy, these tests
treat the verifier as a black box and pin its output on a fixture whose
physical content is independently known.

Theory under test: dP_0 = D3-branes at the tip of C^3/Z_3.
  - 3 SU(3) gauge nodes in a cyclic triangle 0 -> 1 -> 2 -> 0
  - 3 bifundamental copies per directed edge (9 arrows total),
    reflecting an SU(3)_a global flavor symmetry on each edge
  - All bifundamental R-charges = 2/3; W = ε_{abc} X^a_01 X^b_12 X^c_20
    has R = 2 and is invariant under the diagonal SU(3)_flavor
  - The fixture is ABJ-free at every gauge node (cubic SU(3)^3 anomaly
    and SU(3)^2 × U(1)_R mixed anomaly both vanish at R = 2/3)

Physical interpretation of the verifier's bounded chiral-ring output
on this fixture (single-trace cyclic words modulo cyclic-derivative
F-ideal, up to length L):

  - length 3: every closed walk has shape (X01[a], X12[b], X20[c])
    with (a, b, c) ∈ {0,1,2}^3, giving **27** raw cyclic words
    (Burnside does not collapse them — cyclic rotation of the closed
    walk permutes the *arrow types* X01 → X12 → X20, and canonical
    rotation picks the X01-leading rep, so each (a,b,c) is its own
    cyclic class). Under SU(3)_flavor the 27 decompose as
    3 ⊗ 3 ⊗ 3 = **10_S ⊕ 8 ⊕ 8 ⊕ 1_A**. The 9 F-relations
    ∂_{X01[a]} W = 0, ∂_{X12[b]} W = 0, ∂_{X20[c]} W = 0 (each is
    an ε contraction at length 2, lifted to length 3 by the 3
    independent contexts on each side) jointly enforce total
    symmetry in (a,b,c), killing **8 ⊕ 8 ⊕ 1 = 17** non-symmetric
    components and leaving the **Sym^3(C^3) = 10** totally symmetric
    mesonic invariants. Verifier should report dim 10 and rank 17.

  - length 6: 3^6 closed walks per starting node × 3 nodes = 2187
    ordered walks; Burnside on Z/6 (only rotation-by-3 has fixed
    points — the period-3 walks — counted as 3^3 × 3 = 81) yields
    **(2187 + 81)/6 = 378** cyclic classes. The two-sided F-ideal
    saturated to length 6 leaves **dim Sym^6(C^3) = C(8,2) = 28**
    — the degree-6 piece of the polynomial ring in three variables.
    Verifier should report dim 28 and rank 350.

  - lengths 4 / 5 / 7 / 8: no closed walks (the 3-cycle quiver
    closes only at multiples of 3), so no blocks are emitted at all.

The deeper physics statement: the mesonic moduli space of dP_0 is the
orbifold C^3/Z_3, whose coordinate ring is the Z_3-invariant
polynomials in three variables. At degree n divisible by 3 this is
the full dim Sym^n(C^3) = C(n+2, 2); at degree n not divisible by 3
it is empty. The verifier reproduces both halves: dim Sym^n(C^3) at
n ∈ {3, 6} and zero (no block emitted) at n ∈ {1, 2, 4, 5, 7, 8}.

(The verifier does NOT impose Casimir / tracelessness identities, per
design doc §12, so its output is a *bounded single-trace count*
rather than a Hilbert series. But dim Sym^n(C^3) is well-defined
independently of the verifier, so locking these numbers as regression
targets pins the algorithm against real physics.)
"""

from __future__ import annotations

import time
from fractions import Fraction

import pytest

from dualitycert.core.objects import DualityClaim
from dualitycert.core.status import Status
from dualitycert.groups.u1 import u1_r
from dualitycert.qft.dualities import evaluate_claim
from dualitycert.qft.pure_quiver_builder import (
    arrow_names,
    build_pure_quiver,
    dp0_superpotential,
)


# Wall-clock budget per evaluate_claim invocation on dP_0 at L=6 / L=8.
# Empirically ~4-5 s on a 2024-era laptop; a 30 s ceiling catches the
# kind of order-of-magnitude scaling regression (e.g. accidental O(L!))
# we want to know about, without flaking on slow CI.
_TIMING_BUDGET_SECONDS = 30.0


def _build_dp0_self_claim(*, max_length: int | None = None, profile: str = "dp0_self") -> DualityClaim:
    """Build a self-equivalence claim on the dP_0 SU(3)^3 cyclic quiver.

    Multiplicity = 3 copies per directed edge, R = 2/3 everywhere, W is
    the totally antisymmetric ε_{abc} sum over the 3-copy index from
    dp0_superpotential. U(1)_R global is attached so the mixed anomaly
    check has data to fire on.

    If `max_length` is None the bounded_chiral_ring metadata block is
    omitted so the check picks up its defaults (L=6, require_r_graded=True).
    """

    r = Fraction(2, 3)
    n01 = arrow_names(0, 1, 3)
    n12 = arrow_names(1, 2, 3)
    n20 = arrow_names(2, 0, 3)
    dp0 = build_pure_quiver(
        ranks=(3, 3, 3),
        arrows={(0, 1): [r] * 3, (1, 2): [r] * 3, (2, 0): [r] * 3},
        superpotential=dp0_superpotential(n01, n12, n20),
        u1_globals=(u1_r(),),
    )
    metadata = {"duality_profile": profile, "theory_kind": "pure_quiver"}
    if max_length is not None:
        metadata["bounded_chiral_ring"] = {
            "max_length": max_length,
            "require_r_graded": True,
        }
    return DualityClaim(
        name=f"dP_0 self ({profile})",
        electric_theory=dp0,
        magnetic_theory=dp0,
        metadata=metadata,
    )


def _results_by_name(certificate) -> dict:
    return {r.name: r for r in certificate.obligation_results}


# ---------------------------------------------------------------------------
# Test A: full pipeline at default L=6 — physics regression gate
# ---------------------------------------------------------------------------

def test_dp0_self_equivalence_full_pipeline_at_default_L6():
    """End-to-end on dP_0 with default metadata. This is the headline
    physics regression for Phase 2a:
      - upstream cubic ABJ + mixed U(1)_R^2 SU(3) anomaly checks must
        CERTIFY (dP_0 at R=2/3 is solved-anomaly);
      - bounded_chiral_ring check must CERTIFY at cutoff_L = 6 (the
        documented default) in R-graded mode (require_r_graded=True
        default, P3/P4 unblocked);
      - the quotient-dimension blocks must match dim Sym^n(C^3) — the
        single-trace mesonic count of dP_0 at the corresponding scaling
        dimension (n = ℓ since each bifundamental has unit conformal
        dim);
      - all 9 arrow machine labels (X01/X12/X20, three copies each) are
        carried in the certificate (multi-arrow expansion §3.2 surviving
        end-to-end);
      - the run finishes well inside the wall-clock budget.
    """
    claim = _build_dp0_self_claim()  # default metadata → L=6, r_graded=True

    t0 = time.perf_counter()
    cert = evaluate_claim(claim)
    elapsed = time.perf_counter() - t0
    assert elapsed < _TIMING_BUDGET_SECONDS, (
        f"dP_0 L=6 evaluate_claim took {elapsed:.1f}s, exceeding budget "
        f"{_TIMING_BUDGET_SECONDS}s — likely combinatorial regression"
    )

    by_name = _results_by_name(cert)

    # --- P4 upstream: all four anomaly obligations must CERTIFY -----------
    for key in (
        "electric gauge anomaly cancellation",
        "magnetic gauge anomaly cancellation",
        "electric gauge-global mixed anomaly cancellation",
        "magnetic gauge-global mixed anomaly cancellation",
    ):
        assert key in by_name, f"upstream anomaly obligation {key!r} missing"
        assert by_name[key].status == Status.CERTIFIED, (
            f"{key} was {by_name[key].status.value}, expected CERTIFIED"
        )

    # --- Bounded chiral-ring verdict --------------------------------------
    bounded = by_name["bounded chiral-ring consistency"]
    assert bounded.status == Status.CERTIFIED
    details = bounded.details

    # Default metadata picked up.
    assert details["cutoff_L"] == 6
    assert details["require_r_graded"] is True
    assert details["r_graded"] is True
    assert details["r_graded_blocked_by"] == []

    # --- Per-block dimensions match Sym^n(C^3) ----------------------------
    # dP_0 is a 3-cycle quiver, so closed walks only exist at lengths
    # that are multiples of 3 — at L=6 that's lengths 3 and 6, with no
    # other blocks emitted by enumerate_cyclic_words.
    tested = details["tested_blocks"]
    assert len(tested) == 2, f"expected 2 blocks at L=6, got {len(tested)}"

    blocks = {(b["length"], b["r_charge"]): b for b in tested}

    # length 3, R = 2: 27 raw cyclic words M^{abc} = (X01[a], X12[b],
    # X20[c]) decompose under SU(3)_flavor as 10_S ⊕ 8 ⊕ 8 ⊕ 1_A.
    # The 9 ε-form F-relations enforce total symmetry in (a, b, c),
    # killing 8 ⊕ 8 ⊕ 1_A = 17 components → dim Sym^3(C^3) = C(5,2) = 10
    # surviving. This is the SU(3)_flavor symmetric mesonic invariants.
    assert (3, "2") in blocks, f"missing length-3 block; got {list(blocks)}"
    b3 = blocks[(3, "2")]
    assert b3["electric_dim"] == 10
    assert b3["magnetic_dim"] == 10

    # length 6, R = 4: 378 raw cyclic words (Burnside on Z/6, 2187
    # ordered walks reduced to 378 classes). F-ideal saturated to
    # length 6 leaves dim Sym^6(C^3) = C(8,2) = 28 — the degree-6
    # piece of the polynomial ring in three variables (= mesonic
    # chiral ring of dP_0 = C^3/Z_3 at degrees divisible by 3).
    assert (6, "4") in blocks, f"missing length-6 block; got {list(blocks)}"
    b6 = blocks[(6, "4")]
    assert b6["electric_dim"] == 28
    assert b6["magnetic_dim"] == 28

    # No mismatch on self-equivalence.
    assert details["failed_blocks"] == []

    # --- Multi-arrow expansion preserved through evaluate_claim -----------
    expected_labels = sorted(
        [f"X01[{i}]" for i in range(3)]
        + [f"X12[{i}]" for i in range(3)]
        + [f"X20[{i}]" for i in range(3)]
    )
    assert details["arrow_machine_labels_electric"] == expected_labels
    assert details["arrow_machine_labels_magnetic"] == expected_labels


# ---------------------------------------------------------------------------
# Test B: P6 cap reachable
# ---------------------------------------------------------------------------

def test_dp0_self_equivalence_reaches_p6_cap_at_L8():
    """L = 8 is the upper bound of the documented P6 contract (design
    doc §3.1 / §4). The verifier must produce a CERTIFIED self-
    equivalence at this cap without crashing or exceeding budget.

    On dP_0 specifically, length 4/5/7/8 yield no closed walks (the
    cyclic 3-quiver structure means only lengths divisible by 3 close),
    so the tested-blocks count at L=8 stays at 2. This isn't a deep
    combinatorial probe — that lives in test_quiver_chiral_ring.py with
    fixtures that have self-loops — but it does verify that lifting the
    cutoff doesn't trip a guard that was implicitly assuming the
    default L=6.
    """
    claim = _build_dp0_self_claim(max_length=8, profile="dp0_self_L8")

    t0 = time.perf_counter()
    cert = evaluate_claim(claim)
    elapsed = time.perf_counter() - t0
    assert elapsed < _TIMING_BUDGET_SECONDS, (
        f"dP_0 L=8 evaluate_claim took {elapsed:.1f}s, exceeding budget"
    )

    bounded = _results_by_name(cert)["bounded chiral-ring consistency"]
    assert bounded.status == Status.CERTIFIED
    assert bounded.details["cutoff_L"] == 8

    # Same physics as L=6 — length 4,5,7,8 give zero walks on a 3-cycle
    # quiver, so the block set is unchanged.
    tested = bounded.details["tested_blocks"]
    assert len(tested) == 2
    lengths = {b["length"] for b in tested}
    assert lengths == {3, 6}


# ---------------------------------------------------------------------------
# Test C: explicit metadata override smoke test
# ---------------------------------------------------------------------------

def test_dp0_explicit_max_length_4_matches_step_4_smoke():
    """An explicit `max_length=4` (the value used by the algorithm-level
    Phase 2a step 4 self-equivalence smoke test in
    test_quiver_chiral_ring.py) must still CERTIFY here, exercising
    only the length-3 block. Acts as a consistency cross-check between
    the two test files and confirms that the per-block computation at
    L=4 truly only emits one block on dP_0."""
    claim = _build_dp0_self_claim(max_length=4, profile="dp0_self_L4")
    cert = evaluate_claim(claim)
    bounded = _results_by_name(cert)["bounded chiral-ring consistency"]
    assert bounded.status == Status.CERTIFIED
    assert bounded.details["cutoff_L"] == 4

    tested = bounded.details["tested_blocks"]
    assert len(tested) == 1
    assert tested[0]["length"] == 3
    assert tested[0]["r_charge"] == "2"
    assert tested[0]["electric_dim"] == 10
    assert tested[0]["magnetic_dim"] == 10
