"""a-maximization: independent superconformal R-symmetry and central charges.

JSON-in, verifier-independent (same architectural posture as
`mutation_engine.py` and `r_repair.py`). The 4d N=1 superconformal
R-symmetry is the one that maximizes the trial central charge

    a(R) = (3/32) (3 Tr R^3 - Tr R)

over the abelian flavor symmetries (Intriligator-Wecht). For a pure
quiver the trial space is the homogeneous solution space of
{R(W) = 2, gauge-anomaly-free at every node} -- which is exactly the
kernel `repair_r_charges` already returns in `feasible_space`. The trace
formulas mirror `qft/rcharges.r_symmetry_observables` (cross-checked).

This is STRONGER than `central_charge_matching`: that compares a, c from
the *encoded* R; this recomputes the superconformal R independently on
each theory, so two genuine Seiberg duals match even when their encoded
R-charges are merely rational-feasible (the irrational-R families).

Requires sympy (optional ``[amax]`` extra). Solver: exact ``sympy.solve``
for flavor-dim <= 2; numeric ``nsolve`` + PSLQ identification for larger
(the stationarity ``9 Tr(R^2 F_i) = Tr(F_i)`` is a multivariate quadratic
system that exact solve cannot handle past dim ~2). a-maximization here
assumes NO accidental decoupling; a chiral gauge-singlet operator below
the unitarity bound (R < 2/3) is detected and reported out-of-scope (v1
checks singlet operators only -- composite-operator decoupling is not
handled).
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Mapping, Sequence

from dualitycert.qft.r_repair import repair_r_charges


__all__ = [
    "AMaxError",
    "AMaxResult",
    "UNITARITY_R_BOUND",
    "superconformal_central_charges",
    "central_charges_match",
]


UNITARITY_R_BOUND = Fraction(2, 3)

# Exact symbolic solve is fast for <= 2 flavor parameters; above that the
# quadratic gradient system is solved numerically and identified by PSLQ.
_EXACT_SOLVE_MAX_DIM = 2
_NUM_PREC = 55

# Highest algebraic degree attempted when identifying an irrational a/c
# from its high-precision value (PSLQ on the power basis [1, v, .., v^deg]).
_MAX_ALGEBRAIC_DEGREE = 6


class AMaxError(ValueError):
    """Raised for inputs outside the a-maximization scope.

    Pattern-match on the message (mirrors ``RRepairError`` /
    ``MutationEngineError``). Infeasibility / non-convergence / unitarity
    decoupling are reported via this error so the obligation wrapper can
    translate them to NOT_APPLICABLE rather than crashing.
    """


@dataclass(frozen=True)
class AMaxResult:
    """Superconformal data for one theory from a-maximization."""

    a: Any  # exact sympy expr if recovered, else high-precision Float
    c: Any
    a_float: float
    c_float: float
    r_charges: dict[str, Any]  # field label -> exact/numeric R
    flavor_dim: int
    exact: bool  # True iff a, c were recovered as exact algebraic numbers
    unitarity_ok: bool
    unitarity_warnings: tuple[str, ...]


def _require_sympy():
    try:
        import sympy  # noqa: F401

        return sympy
    except ImportError as exc:  # pragma: no cover - exercised via the [amax] extra
        raise AMaxError(
            "a-maximization requires sympy; install the optional extra: "
            "pip install -e .[amax]"
        ) from exc


# ----------------------------------------------------------------------
# Field dimensions (mirror qft/rcharges.r_symmetry_observables).
# ----------------------------------------------------------------------


def _field_dim(arrow: Mapping[str, Any], ranks: Sequence[int]) -> int:
    s, t = int(arrow["source"]), int(arrow["target"])
    if s == t:
        return ranks[s] ** 2 - 1  # adjoint of SU(N)
    return ranks[s] * ranks[t]  # bifundamental


# ----------------------------------------------------------------------
# Declared-basis validation (Lean-style override; default is the kernel).
# ----------------------------------------------------------------------


def _homogeneous_rows(
    theory_json: Mapping[str, Any], field_labels: Sequence[str]
) -> list[list[Fraction]]:
    """Homogeneous {R(W)=0, gauge-anomaly=0} rows (mirrors r_repair)."""

    col = {label: i for i, label in enumerate(field_labels)}
    n = len(field_labels)
    ranks = [int(r) for r in theory_json["ranks"]]
    arrows = list(theory_json["arrows"])
    rows: list[list[Fraction]] = []
    for term in theory_json["superpotential"]:
        row = [Fraction(0)] * n
        for f in term["factors"]:
            row[col[f]] += Fraction(1)
        rows.append(row)
    for v in range(len(ranks)):
        row = [Fraction(0)] * n
        for arrow in arrows:
            s, t = int(arrow["source"]), int(arrow["target"])
            if s == v and t == v:
                a_vf = Fraction(ranks[v])
            elif s == v:
                a_vf = Fraction(1, 2) * Fraction(ranks[t])
            elif t == v:
                a_vf = Fraction(1, 2) * Fraction(ranks[s])
            else:
                continue
            row[col[arrow["label"]]] += a_vf
        rows.append(row)
    return rows


def _validate_flavor_basis(
    theory_json: Mapping[str, Any],
    field_labels: Sequence[str],
    flavor_basis: Sequence[Mapping[str, Any]],
    *,
    expected_dim: int,
) -> list[dict[str, Fraction]]:
    """Check each declared U(1) is W-invariant + gauge-anomaly-free."""

    rows = _homogeneous_rows(theory_json, field_labels)
    parsed: list[dict[str, Fraction]] = []
    for k, vec in enumerate(flavor_basis):
        charges = {label: Fraction(vec.get(label, 0)) for label in field_labels}
        for row in rows:
            if sum(
                (row[i] * charges[label] for i, label in enumerate(field_labels)),
                Fraction(0),
            ) != 0:
                raise AMaxError(
                    f"declared flavor U(1) #{k} is not W-invariant / "
                    "gauge-anomaly-free (it is not a flavor symmetry)"
                )
        parsed.append(charges)
    if len(parsed) != expected_dim:
        raise AMaxError(
            f"declared flavor basis has {len(parsed)} vectors but the flavor "
            f"space is {expected_dim}-dimensional (incomplete or redundant basis)"
        )
    return parsed


# ----------------------------------------------------------------------
# Core a-maximization.
# ----------------------------------------------------------------------


def superconformal_central_charges(
    theory_json: Mapping[str, Any],
    *,
    flavor_basis: Sequence[Mapping[str, Any]] | None = None,
) -> AMaxResult:
    """Independently a-maximize one theory; return its superconformal a, c, R.

    `flavor_basis` (optional, Lean-style) is a list of per-field U(1)
    charge dicts; when given it is validated (W-invariant + anomaly-free,
    spanning the flavor space) and used in place of the auto-derived
    `repair_r_charges` kernel.
    """

    sp = _require_sympy()

    rep = repair_r_charges(theory_json)
    if rep["status"] == "infeasible":
        raise AMaxError(f"R-charge feasibility system inconsistent: {rep['failure_reason']}")
    fs = rep["feasible_space"]
    particular = {k: Fraction(v) for k, v in fs["particular_solution"].items()}
    field_labels = list(particular)
    kernel = [
        {k: Fraction(v) for k, v in basis.items()}
        for basis in fs["homogeneous_basis"]
    ]

    if flavor_basis is not None:
        basis = _validate_flavor_basis(
            theory_json, field_labels, flavor_basis, expected_dim=len(kernel)
        )
    else:
        basis = kernel
    dim = len(basis)

    ranks = [int(r) for r in theory_json["ranks"]]
    arrows = list(theory_json["arrows"])
    singlets = list(theory_json.get("singlets", []))

    svars = list(sp.symbols(f"s0:{dim}", real=True)) if dim else []

    def _rat(fr: Fraction):
        return sp.Rational(fr.numerator, fr.denominator)

    def trial_R(label: str):
        expr = _rat(particular[label])
        for i, vec in enumerate(basis):
            expr += svars[i] * _rat(vec[label])
        return expr

    gaugino = sum(N ** 2 - 1 for N in ranks)
    tr_r = sp.Integer(gaugino)
    tr_r3 = sp.Integer(gaugino)
    for arrow in arrows:
        d = _field_dim(arrow, ranks)
        rf = trial_R(arrow["label"]) - 1
        tr_r += d * rf
        tr_r3 += d * rf ** 3
    for singlet in singlets:
        rf = trial_R(singlet["label"]) - 1
        tr_r += rf
        tr_r3 += rf ** 3

    a_expr = sp.Rational(3, 32) * (3 * tr_r3 - tr_r)
    c_expr = sp.Rational(1, 32) * (9 * tr_r3 - 5 * tr_r)

    subs, exact = _maximize(sp, a_expr, svars)

    a_val = a_expr.subs(subs)
    c_val = c_expr.subs(subs)
    a_float = float(sp.N(a_val, 40))
    c_float = float(sp.N(c_val, 40))

    if exact:
        a_out, c_out = sp.nsimplify(a_val), sp.nsimplify(c_val)
        recovered = True
    else:
        a_id, c_id = _identify(sp, a_val), _identify(sp, c_val)
        recovered = a_id is not None and c_id is not None
        a_out = a_id if a_id is not None else sp.Float(a_val, 40)
        c_out = c_id if c_id is not None else sp.Float(c_val, 40)

    r_charges: dict[str, Any] = {}
    for label in field_labels:
        rv = trial_R(label).subs(subs)
        ident = _identify(sp, rv) if not exact else sp.nsimplify(rv)
        r_charges[label] = ident if ident is not None else sp.Float(rv, 40)

    unit_ok, unit_warn = _unitarity_singlet_scope(singlets, r_charges, sp)

    return AMaxResult(
        a=a_out,
        c=c_out,
        a_float=a_float,
        c_float=c_float,
        r_charges=r_charges,
        flavor_dim=dim,
        exact=recovered,
        unitarity_ok=unit_ok,
        unitarity_warnings=unit_warn,
    )


def _maximize(sp, a_expr, svars):
    """Return (subs_dict, exact_flag) at the unique a-maximum.

    Exact ``solve`` for small flavor-dim; numeric ``nsolve`` otherwise.
    The maximum is the Hessian-negative-definite critical point.
    """

    if not svars:
        return {}, True

    grad = [sp.diff(a_expr, s) for s in svars]
    hess = sp.hessian(a_expr, svars)

    if len(svars) <= _EXACT_SOLVE_MAX_DIM:
        try:
            sols = sp.solve(grad, svars, dict=True)
        except Exception:  # pragma: no cover - solver fallthrough
            sols = []
        for sol in sols:
            if any(getattr(v, "is_real", None) is False for v in sol.values()):
                continue
            if _negative_definite(sp, hess.subs(sol), len(svars)):
                return sol, True

    # Numeric: Newton from the rational feasible baseline (s = 0).
    try:
        root = sp.nsolve(grad, svars, [0] * len(svars), prec=_NUM_PREC)
    except Exception as exc:
        raise AMaxError(f"a-maximization did not converge: {exc}") from exc
    subs = {svars[i]: root[i] for i in range(len(svars))}
    if not _negative_definite(sp, hess.subs(subs), len(svars)):
        raise AMaxError(
            "a-maximization critical point is not a maximum "
            "(Hessian not negative-definite); theory may be out of scope"
        )
    return subs, False


def _negative_definite(sp, hess, n) -> bool:
    """Sylvester's criterion via leading principal minors (no eigen-iteration)."""

    for k in range(1, n + 1):
        minor = sp.re(hess[:k, :k].det())
        if not (float((-1) ** k * minor) > 0):
            return False
    return True


def _identify(sp, value, *, max_coeff: int = 10 ** 12, max_denom: int = 10 ** 6):
    """Recover an exact algebraic number from its value, else None.

    Strategy: rational (small denominator) first, then the minimal
    polynomial via PSLQ on the power basis [1, v, v^2, ..., v^deg] for
    ascending degree; the value is the polynomial root nearest `value`
    (radicals for degree <= 4, an exact ``CRootOf`` otherwise).

    Verification is at HIGH precision (mpmath, 60 digits) -- a float
    comparison is far too weak (it would accept the decimal expansion of
    an irrational as a giant "rational", or a spurious low-degree fit).
    """

    import mpmath

    saved = mpmath.mp.dps
    mpmath.mp.dps = 80
    try:
        v = mpmath.mpf(str(sp.N(value, 70)))
        eps = mpmath.mpf(10) ** (-40)

        def _close(expr) -> bool:
            return mpmath.fabs(mpmath.mpf(str(sp.N(expr, 60))) - v) < eps

        # Rational: small denominator AND high-precision agreement.
        rat = sp.Rational(sp.nsimplify(sp.N(value, 60), rational=True))
        if rat.q <= max_denom and _close(rat):
            return rat

        x = sp.Symbol("x")
        vf = float(v)
        for deg in range(2, _MAX_ALGEBRAIC_DEGREE + 1):
            rel = mpmath.pslq(
                [v ** i for i in range(deg + 1)],
                maxcoeff=max_coeff,
                maxsteps=4 * 10 ** 5,
            )
            if not rel or rel[deg] == 0:
                continue
            poly = sp.Poly(list(reversed([int(c) for c in rel])), x)
            try:
                roots = poly.all_roots()
            except Exception:  # pragma: no cover - solver fallthrough
                continue
            real_roots = [
                r for r in roots if abs(complex(sp.N(r, 30)).imag) < 1e-25
            ]
            if not real_roots:
                continue
            best = min(real_roots, key=lambda r: abs(float(sp.re(sp.N(r, 40))) - vf))
            best = sp.re(best)
            if not _close(best):
                continue
            simplified = sp.radsimp(best)
            return simplified if _close(simplified) else best
        return None
    finally:
        mpmath.mp.dps = saved


def _unitarity_singlet_scope(singlets, r_charges, sp):
    """v1 unitarity check: gauge-singlet chiral operators need R >= 2/3.

    Composite gauge-invariant operators are NOT enumerated here, so this
    is a partial (but sound, as far as it goes) check.
    """

    warnings: list[str] = [
        "a-maximization assumes no accidental decoupling; only gauge-singlet "
        "operators are checked against the unitarity bound (composite "
        "operators are not enumerated in v1)."
    ]
    ok = True
    bound = float(UNITARITY_R_BOUND)
    for singlet in singlets:
        label = singlet["label"]
        if float(sp.N(r_charges[label], 30)) < bound - 1e-12:
            ok = False
            warnings.append(
                f"gauge-singlet operator {label!r} has R < 2/3 -> it decouples "
                "as a free field; naive a-maximization is invalid here."
            )
    return ok, tuple(warnings)


# ----------------------------------------------------------------------
# Pair comparison.
# ----------------------------------------------------------------------


def central_charges_match(
    electric: AMaxResult, magnetic: AMaxResult, *, tol: float = 1e-25
) -> tuple[bool, bool]:
    """Return (a_matches, c_matches).

    Compares the (exact or numeric) central charges at 40-digit precision:
    two independently-computed algebraic numbers that agree to 40 digits
    are equal (distinct algebraic numbers of this bounded height/degree
    cannot coincide that closely). Robust across radical / CRootOf /
    rational / Float representations.
    """

    import sympy as sp

    a_ok = abs(float(sp.N(electric.a - magnetic.a, 40))) < tol
    c_ok = abs(float(sp.N(electric.c - magnetic.c, 40))) < tol
    return bool(a_ok), bool(c_ok)
