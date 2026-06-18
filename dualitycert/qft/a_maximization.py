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
    "audit_superconformal_r",
    "with_superconformal_r",
    "HM_AC_LOWER",
    "HM_AC_UPPER",
    "central_charge_scft_bounds",
    "one_loop_beta_coefficients",
    "asymptotic_freedom_report",
    "mesonic_unitarity_scan",
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


def _constraint_system(
    theory_json: Mapping[str, Any], field_labels: Sequence[str]
) -> tuple[list[list[Fraction]], list[Fraction]]:
    """Build (A, b) for the R-feasibility system A R = b (mirrors r_repair).

    Rows: one per W term (R-sum = 2), then one per gauge node
    (SU(N)^2 U(1)_R anomaly-free). Columns follow `field_labels`.
    """

    col = {label: i for i, label in enumerate(field_labels)}
    n = len(field_labels)
    ranks = [int(r) for r in theory_json["ranks"]]
    arrows = list(theory_json["arrows"])
    A: list[list[Fraction]] = []
    b: list[Fraction] = []
    for term in theory_json["superpotential"]:
        row = [Fraction(0)] * n
        for f in term["factors"]:
            row[col[f]] += Fraction(1)
        A.append(row)
        b.append(Fraction(2))
    for v in range(len(ranks)):
        row = [Fraction(0)] * n
        sum_a = Fraction(0)
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
            sum_a += a_vf
        A.append(row)
        b.append(sum_a - Fraction(ranks[v]))
    return A, b


def _homogeneous_rows(
    theory_json: Mapping[str, Any], field_labels: Sequence[str]
) -> list[list[Fraction]]:
    """Homogeneous {R(W)=0, gauge-anomaly=0} rows (the A of the system)."""

    return _constraint_system(theory_json, field_labels)[0]


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
    flavor_ranks: "Sequence[int] | None" = None,
) -> AMaxResult:
    """Independently a-maximize one theory; return its superconformal a, c, R.

    `flavor_basis` (optional, Lean-style) is a list of per-field U(1)
    charge dicts; when given it is validated (W-invariant + anomaly-free,
    spanning the flavor space) and used in place of the auto-derived
    `repair_r_charges` kernel.

    `flavor_ranks` (optional) are SU(N) GLOBAL flavor nodes (indexed after
    the gauge nodes): the ABJ R-anomaly is then imposed only at the gauge
    nodes and the gaugino traces count gauge nodes only, while flavored
    fields contribute their full multiplicity. This is the standard a-max
    for flavored theories -- e.g. it gives SQCD's R_Q = 1 - N_c/N_f.
    """

    sp = _require_sympy()

    rep = repair_r_charges(theory_json, flavor_ranks=list(flavor_ranks) if flavor_ranks else None)
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
    all_ranks = ranks + [int(r) for r in (flavor_ranks or [])]
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

    gaugino = sum(N ** 2 - 1 for N in ranks)  # GAUGE nodes only; flavor has none
    tr_r = sp.Integer(gaugino)
    tr_r3 = sp.Integer(gaugino)
    for arrow in arrows:
        d = _field_dim(arrow, all_ranks)
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

    # Upgrade a NUMERIC maximizer to an EXACT one by identifying each flavor
    # coordinate s_i (only `dim` numbers, far more robust than identifying
    # every field's R). Because every kernel vector has W-charge 0 and is
    # gauge-anomaly-free, R = R0 + sum s_i F_i satisfies W=2 + anomaly-free
    # for ANY s — so an exact `subs` yields per-field R that is exact AND
    # constraint-satisfying. Identify `a` first; if it lives in Q(sqrt d),
    # reuse d as a hint so every s_i is found in the same quadratic field.
    if not exact and svars:
        a_guess = _identify(sp, a_expr.subs(subs))
        hint = _radicand(sp, a_guess)
        exact_subs: dict[Any, Any] = {}
        ok = True
        for s in svars:
            si = _identify(sp, subs[s], hint_radicand=hint)
            if si is None:
                ok = False
                break
            exact_subs[s] = si
        if ok:
            subs, exact = exact_subs, True

    a_raw = a_expr.subs(subs)
    c_raw = c_expr.subs(subs)
    a_float = float(sp.N(a_raw, 40))
    c_float = float(sp.N(c_raw, 40))

    if exact:
        recovered = True
        a_out = sp.radsimp(sp.simplify(a_raw))
        c_out = sp.radsimp(sp.simplify(c_raw))
        r_charges = {
            label: sp.radsimp(sp.simplify(trial_R(label).subs(subs)))
            for label in field_labels
        }
    else:
        a_id, c_id = _identify(sp, a_raw), _identify(sp, c_raw)
        recovered = a_id is not None and c_id is not None
        a_out = a_id if a_id is not None else sp.Float(a_float, 40)
        c_out = c_id if c_id is not None else sp.Float(c_float, 40)
        r_charges = {}
        for label in field_labels:
            rv = trial_R(label).subs(subs)
            ident = _identify(sp, rv)
            r_charges[label] = (
                ident if ident is not None else sp.Float(float(sp.N(rv, 40)), 40)
            )

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


def _radicand(sp, expr):
    """If `expr` is p + q*sqrt(d) (d a squarefree int), return d, else None."""

    if expr is None:
        return None
    for atom in expr.atoms(sp.Pow):
        base, exp = atom.as_base_exp()
        if exp == sp.Rational(1, 2) and getattr(base, "is_Integer", False):
            return int(base)
    return None


def _identify(
    sp, value, *, max_coeff: int = 10 ** 12, max_denom: int = 10 ** 6, hint_radicand=None
):
    """Recover an exact algebraic number from its value, else None.

    Strategy: rational (small denominator) first; then, if `hint_radicand`
    d is given, the targeted quadratic p/q + r/s*sqrt(d) (robust when many
    quantities share one field Q(sqrt d), e.g. all the flavor coordinates
    of a single a-maximization); then the minimal polynomial via PSLQ on
    the power basis [1, v, ..., v^deg] for ascending degree (radicals for
    degree <= 4, an exact ``CRootOf`` otherwise).

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

        # Exact zero (e.g. a baryonic flavor coordinate that decouples at the
        # maximum) -- short-circuit before PSLQ, which rejects a zero entry.
        if mpmath.fabs(v) < eps:
            return sp.Integer(0)

        def _close(expr) -> bool:
            return mpmath.fabs(mpmath.mpf(str(sp.N(expr, 60))) - v) < eps

        # Rational: small denominator AND high-precision agreement.
        rat = sp.Rational(sp.nsimplify(sp.N(value, 60), rational=True))
        if rat.q <= max_denom and _close(rat):
            return rat

        # Targeted quadratic in a known field Q(sqrt d): PSLQ on [1, sqrt d, v].
        if hint_radicand:
            rel = mpmath.pslq(
                [mpmath.mpf(1), mpmath.sqrt(hint_radicand), v],
                maxcoeff=max_coeff,
                maxsteps=4 * 10 ** 5,
            )
            if rel and rel[2] != 0:
                A, B, C = rel
                cand = sp.Rational(-A, C) + sp.Rational(-B, C) * sp.sqrt(hint_radicand)
                if _close(cand):
                    return cand

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


# ----------------------------------------------------------------------
# Superconformal-R audit (judge ②a) + rational-feasible proxy.
# ----------------------------------------------------------------------


_R_PLACEHOLDER = "1/2"


def _placeholder_json(theory_json: Mapping[str, Any]) -> dict[str, Any]:
    """Copy of `theory_json` with every R-charge set to a rational placeholder.

    The feasible R-space depends only on the structure (W terms, ranks,
    arrows), so this lets r_repair / a-maximization run even when the
    encoded R is irrational (which would otherwise crash Fraction parsing).
    """

    out = dict(theory_json)
    out["arrows"] = [dict(a, r_charge=_R_PLACEHOLDER) for a in theory_json["arrows"]]
    if theory_json.get("singlets"):
        out["singlets"] = [
            dict(s, r_charge=_R_PLACEHOLDER) for s in theory_json["singlets"]
        ]
    return out


def audit_superconformal_r(theory_json: Mapping[str, Any]) -> dict[str, Any]:
    """Audit whether `theory_json`'s encoded R IS the superconformal R.

    Status:
      - "superconformal"    : encoded R is consistent AND equals the a-max R;
      - "inconsistent"      : encoded R violates R(W)=2 or gauge-anomaly;
      - "non_superconformal": consistent but != the a-max superconformal R;
      - "out_of_scope"      : a-maximization cannot resolve this theory.
    """

    sp = _require_sympy()

    claimed: dict[str, Any] = {}
    for arrow in theory_json["arrows"]:
        claimed[arrow["label"]] = sp.sympify(arrow["r_charge"])
    for singlet in theory_json.get("singlets", []):
        claimed[singlet["label"]] = sp.sympify(singlet["r_charge"])
    field_labels = list(claimed)

    # Stage 0: encoded R is feasible (R(W)=2 + gauge-anomaly-free).
    A, b = _constraint_system(theory_json, field_labels)
    for row, rhs in zip(A, b):
        lhs = sum(
            (
                sp.Rational(row[i].numerator, row[i].denominator) * claimed[label]
                for i, label in enumerate(field_labels)
                if row[i] != 0
            ),
            sp.Integer(0),
        )
        if sp.simplify(lhs - sp.Rational(rhs.numerator, rhs.denominator)) != 0:
            return {
                "status": "inconsistent",
                "detail": "encoded R violates R(W)=2 / gauge-anomaly cancellation",
                "claimed": {k: str(v) for k, v in claimed.items()},
                "computed": {},
            }

    # Compute the superconformal R from the structure (placeholder R so the
    # rational r_repair / a-max pipeline is unaffected by the encoded R).
    try:
        computed = superconformal_central_charges(_placeholder_json(theory_json)).r_charges
    except AMaxError as exc:
        return {
            "status": "out_of_scope",
            "detail": str(exc),
            "claimed": {k: str(v) for k, v in claimed.items()},
            "computed": {},
        }

    # Stage 1: encoded R must equal the superconformal R, field by field.
    mismatches = [
        label
        for label in field_labels
        if sp.simplify(claimed[label] - computed[label]) != 0
    ]
    computed_str = {k: str(v) for k, v in computed.items()}
    if mismatches:
        return {
            "status": "non_superconformal",
            "detail": (
                "encoded R is feasible but not the superconformal R; "
                f"fields off: {mismatches}"
            ),
            "claimed": {k: str(v) for k, v in claimed.items()},
            "computed": computed_str,
        }
    return {
        "status": "superconformal",
        "detail": "encoded R is the superconformal R",
        "claimed": {k: str(v) for k, v in claimed.items()},
        "computed": computed_str,
    }


def with_superconformal_r(theory_json: Mapping[str, Any]) -> dict[str, Any]:
    """Return a copy of `theory_json` carrying THE superconformal (a-max) R.

    This is the judge-②a substitution: the structure (ranks, arrows, W) is
    untouched, but every field's R-charge is replaced by its a-maximized
    superconformal value (rational for the symmetric families, an exact
    algebraic number for the irrational-R families). The result is what a
    claim must carry under the "superconformal" R-charge policy so the
    audit (`audit_superconformal_r`) certifies it.

    The superconformal R is computed from the structure alone (the encoded
    R is ignored), so this works on a theory whose stored R is only
    rational-feasible. Raises `AMaxError` if a-maximization cannot resolve
    the theory (the caller routes that to attrition).
    """

    r = superconformal_central_charges(theory_json).r_charges
    out = dict(theory_json)
    out["arrows"] = [
        dict(a, r_charge=str(r[a["label"]])) for a in theory_json["arrows"]
    ]
    if theory_json.get("singlets"):
        out["singlets"] = [
            dict(s, r_charge=str(r[s["label"]])) for s in theory_json["singlets"]
        ]
    return out


# ----------------------------------------------------------------------
# SCFT-soundness diagnostics (necessary conditions for a unitary 4d N=1
# SCFT). These FLAG inputs that CANNOT be the SCFT they claim to be; they
# do NOT prove an interacting fixed point exists (that needs physics input
# / is not decidable from the Lagrangian). "certificates, not proofs."
# ----------------------------------------------------------------------


# Hofman-Maldacena conformal-collider bounds for a unitary 4d N=1 SCFT:
# 1/2 <= a/c <= 3/2. The endpoints are free fields (a/c=1/2 a free chiral
# multiplet, a/c=3/2 a free vector multiplet), so saturation is allowed.
HM_AC_LOWER = Fraction(1, 2)
HM_AC_UPPER = Fraction(3, 2)


def central_charge_scft_bounds(
    a_float: float, c_float: float, *, tol: float = 1e-9
) -> dict[str, Any]:
    """Necessary central-charge conditions for a unitary 4d N=1 SCFT.

    Requires a > 0, c > 0 and the Hofman-Maldacena bound
    ``1/2 <= a/c <= 3/2`` (Hofman-Maldacena 2008; the endpoints are free
    fields). Violating any of these means the theory is NOT a unitary SCFT;
    satisfying them is necessary, NOT sufficient. Takes the numeric a, c
    (e.g. ``AMaxResult.a_float`` / ``.c_float``), so it is sympy-free.
    """

    a_pos = a_float > 0.0
    c_pos = c_float > 0.0
    ratio = (a_float / c_float) if c_float != 0.0 else None
    lo, hi = float(HM_AC_LOWER), float(HM_AC_UPPER)
    hm_ok = ratio is not None and (lo - tol) <= ratio <= (hi + tol)

    violations: list[str] = []
    if not a_pos:
        violations.append(f"a = {a_float:.6g} is not positive")
    if not c_pos:
        violations.append(f"c = {c_float:.6g} is not positive")
    if ratio is None:
        violations.append("c = 0, so a/c is undefined")
    elif not hm_ok:
        violations.append(
            f"a/c = {ratio:.6g} is outside the Hofman-Maldacena window [1/2, 3/2]"
        )

    return {
        "ok": bool(a_pos and c_pos and hm_ok),
        "a_positive": bool(a_pos),
        "c_positive": bool(c_pos),
        "hofman_maldacena_ok": bool(hm_ok),
        "a_over_c": ratio,
        "violations": tuple(violations),
    }


def one_loop_beta_coefficients(
    theory_json: Mapping[str, Any]
) -> dict[int, Fraction]:
    """Per-node one-loop NSVZ numerator ``b0 = 3 T(adj) - sum_matter T(r)``.

    Sign convention: ``b0 > 0`` is asymptotically free. For SU(N):
    ``T(adj) = N``, ``T(fund) = 1/2``; a bifundamental contributes
    ``T(fund) x (spectator rank)`` and an adjoint ``N`` (singlets 0). This
    reuses exactly the matter index sums of the gauge-R anomaly rows, and
    is R-independent (purely structural).
    """

    ranks = [int(r) for r in theory_json["ranks"]]
    arrows = list(theory_json["arrows"])
    b0: dict[int, Fraction] = {}
    for v in range(len(ranks)):
        matter = Fraction(0)
        for arrow in arrows:
            s, t = int(arrow["source"]), int(arrow["target"])
            if s == v and t == v:
                matter += Fraction(ranks[v])  # adjoint, T(adj) = N
            elif s == v:
                matter += Fraction(1, 2) * ranks[t]  # fund of v, mult = rank(t)
            elif t == v:
                matter += Fraction(1, 2) * ranks[s]
        # gauge-singlet fields carry no node charge -> contribute 0.
        b0[v] = 3 * Fraction(ranks[v]) - matter
    return b0


def asymptotic_freedom_report(theory_json: Mapping[str, Any]) -> dict[str, Any]:
    """Per-node one-loop beta classification -- a DIAGNOSTIC, NOT an SCFT gate.

    IMPORTANT (physics): the one-loop ``b0`` is the conformal condition ONLY
    at a free/orbifold point where every R = 2/3 (then ``b0 = 0``, e.g.
    dP_0, C^3/(Z2xZ2)). The EXACT conformal condition is the NSVZ beta with
    anomalous dimensions ``gamma_i = 3 R_i - 2``,

        beta ~ T(adj) + sum_i T(r_i) (R_i - 1) = 0,

    which is exactly the ABJ R-anomaly / gauge-R-anomaly condition already
    enforced (r_repair feasibility + the mixed gauge-global anomaly check).
    So for an SCFT with R != 2/3 the one-loop ``b0`` is generically nonzero,
    and ``b0 < 0`` at a node is PHYSICALLY ALLOWED (a free-magnetic-phase
    node, or one that is interacting only via the superpotential / other
    nodes; e.g. F_0 phase II and dP_2 phase I are genuine SCFTs with
    ``b0 < 0`` nodes). Therefore ``b0`` is reported for information only and
    MUST NOT be used as a hard "not an SCFT" gate.
    """

    b0 = one_loop_beta_coefficients(theory_json)
    return {
        "b0": dict(b0),
        "all_one_loop_asymptotically_free": all(b > 0 for b in b0.values()),
        "one_loop_ir_free_nodes": {v: b for v, b in b0.items() if b < 0},
        "one_loop_marginal_nodes": [v for v, b in b0.items() if b == 0],
    }


def mesonic_unitarity_scan(
    theory_json: Mapping[str, Any],
    r_charges: Mapping[str, Any],
    *,
    max_length: int | None = None,
    max_operators: int = 5000,
) -> dict[str, Any]:
    """Scan single-trace mesonic gauge invariants for the unitarity bound.

    Broadens the v1 singlet-only check to COMPOSITE operators: every simple
    directed cycle in the quiver (a closed gauge-invariant word, up to
    ``max_length`` arrows; default = #nodes) is an operator with
    ``R = sum of its arrows' R``. Any with ``R < 2/3`` is a CANDIDATE
    decoupling free field (so naive a-maximization would be invalid there).

    Honestly bounded (same posture as the bounded chiral ring): F-term
    relations are NOT imposed, so a flagged cycle may be F-term trivial
    rather than a genuine chiral-ring generator -- it is a candidate to
    confirm, not a proof. Single-trace mesonic only: baryonic (epsilon-
    contracted) operators are not enumerated. The enumeration is capped at
    ``max_operators`` (a warning records truncation).
    """

    ranks = [int(r) for r in theory_json["ranks"]]
    num_nodes = len(ranks)
    arrows = list(theory_json["arrows"])
    if max_length is None:
        max_length = num_nodes  # a simple cycle visits each node at most once

    def _as_float(x: Any) -> float:
        try:
            return float(x)
        except (TypeError, ValueError):
            import sympy as sp

            return float(sp.N(x, 40))

    r_float = {a["label"]: _as_float(r_charges[a["label"]]) for a in arrows}
    cycles, capped = _simple_cycles_over_arrows(
        arrows, num_nodes, max_length, max_operators
    )

    bound = float(UNITARITY_R_BOUND)
    below: list[dict[str, Any]] = []
    for cyc in cycles:
        labels = [arrows[i]["label"] for i in cyc]
        r_sum = sum(r_float[lab] for lab in labels)
        if r_sum < bound - 1e-9:
            below.append({"operator": labels, "R": r_sum})

    warnings: list[str] = []
    if capped:
        warnings.append(
            f"mesonic operator enumeration hit the cap ({max_operators}); "
            "longer cycles were not all scanned."
        )
    for op in below:
        warnings.append(
            f"single-trace operator {'*'.join(op['operator'])} has R="
            f"{op['R']:.6g} < 2/3 -> candidate decoupling (confirm vs the "
            "chiral ring; F-relations not imposed here)."
        )

    return {
        "ok": not below,
        "operators_scanned": len(cycles),
        "below_bound": tuple(below),
        "truncated": bool(capped),
        "warnings": tuple(warnings),
    }


def _simple_cycles_over_arrows(
    arrows: Sequence[Mapping[str, Any]],
    num_nodes: int,
    max_length: int,
    max_operators: int,
) -> tuple[list[list[int]], bool]:
    """Enumerate simple directed cycles as lists of arrow indices.

    Canonical de-duplication: a cycle is recorded only from its minimum
    node, and the DFS only extends to strictly larger nodes, so each simple
    cycle is emitted exactly once (no rotations). Self-loops (adjoints) and
    2-cycles are included. Parallel arrows are distinct edges. Returns
    ``(cycles, truncated)``.
    """

    adj: dict[int, list[tuple[int, int]]] = {v: [] for v in range(num_nodes)}
    for i, ar in enumerate(arrows):
        adj[int(ar["source"])].append((i, int(ar["target"])))

    cycles: list[list[int]] = []
    state = {"capped": False}

    def dfs(start: int, node: int, visited: frozenset, stack: list[int]) -> None:
        if state["capped"]:
            return
        for ai, tgt in adj[node]:
            if len(stack) + 1 > max_length:
                continue
            if tgt == start:
                cycles.append(stack + [ai])
                if len(cycles) >= max_operators:
                    state["capped"] = True
                    return
            elif tgt > start and tgt not in visited:
                dfs(start, tgt, visited | {tgt}, stack + [ai])
                if state["capped"]:
                    return

    for start in range(num_nodes):
        dfs(start, start, frozenset({start}), [])
        if state["capped"]:
            break
    return cycles, state["capped"]
