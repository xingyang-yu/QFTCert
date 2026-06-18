"""The 4d N=1 superconformal index for pure-quiver gauge theories.

JSON-in, verifier-independent (same posture as ``a_maximization`` /
``mutation_engine`` / ``r_repair``). Computes the index as a power series
following Rastelli-Razamat (arXiv:1608.02965): list the single-letter
indices, take the plethystic exponential, and project onto gauge singlets
by the SU(N) matrix integral.

Conventions (Rastelli-Razamat eqs 2.9-2.15), here UNREFINED at ``p = q``:
write ``p = q`` and grade by ``tau = (pq)^(1/2)`` with ``tau = u^D`` so a
rational R-charge gives integer ``u``-powers (``D`` = lcm of the R-charge
denominators).

  - chiral multiplet, R-charge r, character chi (conjugate chibar):
        f_chi = (tau^r chi - tau^(2-r) chibar) / (1 - tau)^2          (eq 2.9)
  - vector multiplet (full adjoint character, incl. the Cartan):
        f_V   = -2 tau/(1 - tau) chi_adj                              (eq 2.11)
  - full index = gauge average of PE[sum of single-letters]           (eq 2.12)
        PE[f] = exp( sum_{n>=1} (1/n) f(tau^n, z^n) )                  (eq 2.13)
  - gauge average over SU(N): (1/N!) * constant-term over the maximal-torus
    fugacities (prod z_i = 1) of [ Vandermonde prod_{i!=j}(1 - z_i/z_j) * . ]

VALIDATED against (see tests):
  - the free-chiral index = the elliptic Gamma function (eq 2.14);
  - SU(2) with N_f = 3 (R = 1/3): the s-confinement index identity
    I_gauge == I_sigma = 15 mesons/baryons at R = 2/3 (eq 4.2/4.3);
  - the conifold SU(2) x SU(2): 1 + 10 u^2 + ... (4 mesons + 6 baryons).

SCOPE / LIMITATIONS (honest):
  - UNREFINED (p = q) and RATIONAL R only. An irrational superconformal R
    (the a-maximized dP_1 / dP_2 / SPP families) has irrational tau-powers,
    so there is no finite tau-series; that case needs the flavor-fugacity
    refinement (use a rational reference R + flavor fugacities) and is NOT
    implemented here -> raises ``SuperconformalIndexError``.
  - SU(N) is supported, but the gauge integral is a brute-force
    constant-term extraction whose cost grows fast with N, the node count,
    and the order: SU(2) nodes are cheap; SU(N >= 3) (dP_0, F_0) is slow.
  - Finite-order series only (no closed form), so index equality is a
    finite-order check, NOT a proof of an exact identity.
  - The index is a signed supertrace: equal indices are NECESSARY, not
    sufficient, for a duality (Romelsberger; Rastelli-Razamat).
"""

from __future__ import annotations

from collections import defaultdict
from fractions import Fraction
from math import factorial
from typing import Any, Mapping


__all__ = [
    "SuperconformalIndexError",
    "index_series",
    "index_matches",
    "format_index",
]


class SuperconformalIndexError(ValueError):
    """Input outside the (unrefined, rational-R, SU(N)) index scope."""


def _lcm(a: int, b: int) -> int:
    from math import gcd

    return a * b // gcd(a, b)


def _require_sympy():
    try:
        import sympy  # noqa: F401

        return sympy
    except ImportError as exc:  # pragma: no cover
        raise SuperconformalIndexError(
            "the superconformal index requires sympy; install the [amax] extra"
        ) from exc


def _parse_r(value: Any) -> Fraction:
    try:
        return Fraction(str(value))
    except ValueError as exc:
        raise SuperconformalIndexError(
            f"R-charge {value!r} is not rational; the unrefined index needs "
            "rational R (irrational superconformal R requires flavor "
            "fugacities, not implemented)"
        ) from exc


# ----------------------------------------------------------------------
# Power-series arithmetic: a series is {u-power(int) -> sympy coeff(z's)}.
# ----------------------------------------------------------------------


def _smul(a: dict, b: dict, K: int, sp) -> dict:
    out: dict = defaultdict(lambda: sp.Integer(0))
    for i, ci in a.items():
        if i > K:
            continue
        for j, cj in b.items():
            if i + j > K:
                continue
            out[i + j] += ci * cj
    return {k: sp.expand(v) for k, v in out.items() if sp.expand(v) != 0}


def _sadd(series_list, sp) -> dict:
    out: dict = defaultdict(lambda: sp.Integer(0))
    for s in series_list:
        for k, v in s.items():
            out[k] += v
    return {k: sp.expand(v) for k, v in out.items() if sp.expand(v) != 0}


def _chiral_letter(r: Fraction, D: int, char, charbar, K: int, sp) -> dict:
    """f_chi = (tau^r chi - tau^(2-r) chibar)/(1-tau)^2, tau = u^D."""

    geom = {D * m: sp.Integer(m + 1) for m in range(0, K // D + 2)}
    num: dict = {}
    rD, r2D = int(D * r), int(D * (2 - r))
    if rD <= K:
        num[rD] = num.get(rD, sp.Integer(0)) + char
    if r2D <= K:
        num[r2D] = num.get(r2D, sp.Integer(0)) - charbar
    num = {k: sp.expand(v) for k, v in num.items()}
    return _smul(num, geom, K, sp)


def _vector_letter(D: int, char_adj, K: int, sp) -> dict:
    """f_V = -2 tau/(1-tau) chi_adj, tau = u^D."""

    geom = {D * m: sp.Integer(1) for m in range(0, K // D + 2)}
    return _smul({D: sp.expand(-2 * char_adj)}, geom, K, sp)


def _plethystic_exp(f: dict, K: int, syms, sp) -> dict:
    """PE[f] = exp(sum_{n>=1} (1/n) f(u^n, z^n)) truncated to u^K."""

    S: dict = defaultdict(lambda: sp.Integer(0))
    for n in range(1, K + 1):
        sub = {s: s ** n for s in syms}
        for k, c in f.items():
            if k * n > K:
                continue
            S[k * n] += sp.Rational(1, n) * (c.subs(sub) if syms else c)
    S = {k: sp.expand(v) for k, v in S.items() if sp.expand(v) != 0}
    # exp via the recurrence n E_n = sum_{k=1}^n k S_k E_{n-k}, E_0 = 1.
    E = {0: sp.Integer(1)}
    for n in range(1, K + 1):
        acc = sp.Integer(0)
        for k in range(1, n + 1):
            if k in S and (n - k) in E:
                acc += k * S[k] * E[n - k]
        if acc != 0:
            E[n] = sp.expand(acc / n)
    return {k: v for k, v in E.items() if sp.expand(v) != 0}


def _constant_term(expr, zv, order: int, sp):
    """Constant term in the single Laurent variable zv."""

    e = sp.expand(expr)
    if e == 0:
        return sp.Integer(0)
    P = 6 * order + 12  # safe upper bound on the fugacity power at this order
    return sp.expand(e * zv ** P).coeff(zv, P)


# ----------------------------------------------------------------------
# The index.
# ----------------------------------------------------------------------


def index_series(theory_json: Mapping[str, Any], order: int = 6) -> dict[int, Any]:
    """Return the unrefined index of `theory_json` as {u-power -> coefficient}.

    `order` is the highest u-power kept (u = tau^(1/D), tau = (pq)^(1/2),
    D = lcm of the R-charge denominators). The u^0 coefficient is always 1.
    Raises ``SuperconformalIndexError`` for irrational R or empty input.
    """

    sp = _require_sympy()
    ranks = [int(x) for x in theory_json["ranks"]]
    arrows = list(theory_json["arrows"])
    singlets = list(theory_json.get("singlets", []))
    K = int(order)

    r_values = [_parse_r(a["r_charge"]) for a in arrows]
    r_values += [_parse_r(s["r_charge"]) for s in singlets]
    D = 1
    for r in r_values:
        D = _lcm(D, r.denominator)

    # Per-node maximal-torus fugacities z_{v,i} with prod_i z_{v,i} = 1.
    z_free: dict[int, list] = {}
    z_all: dict[int, list] = {}
    for v, N in enumerate(ranks):
        frees = [sp.Symbol(f"z_{v}_{i}") for i in range(N - 1)]
        z_free[v] = frees
        if N == 1:
            z_all[v] = [sp.Integer(1)]
        else:
            last = sp.Integer(1)
            for s in frees:
                last = last / s
            z_all[v] = frees + [last]

    def fund(v):
        return sum(z_all[v])

    def antifund(v):
        return sum(1 / x for x in z_all[v])

    def adjoint(v):
        return sp.expand(fund(v) * antifund(v) - 1)

    # Single-letter index of the full matter + vector content.
    letters: list[dict] = []
    for arrow in arrows:
        s, t = int(arrow["source"]), int(arrow["target"])
        r = _parse_r(arrow["r_charge"])
        if s == t:
            char = adjoint(s)
            charbar = adjoint(s)
        else:
            char = sp.expand(fund(s) * antifund(t))
            charbar = sp.expand(antifund(s) * fund(t))
        letters.append(_chiral_letter(r, D, char, charbar, K, sp))
    for singlet in singlets:
        r = _parse_r(singlet["r_charge"])
        letters.append(_chiral_letter(r, D, sp.Integer(1), sp.Integer(1), K, sp))
    for v, N in enumerate(ranks):
        if N >= 2:
            letters.append(_vector_letter(D, adjoint(v), K, sp))

    syms = [s for v in z_free for s in z_free[v]]
    pe = _plethystic_exp(_sadd(letters, sp), K, syms, sp)

    # Gauge average: project onto gauge singlets node by node.
    vandermonde: dict[int, Any] = {}
    norm = 1
    for v, N in enumerate(ranks):
        if N >= 2:
            vd = sp.Integer(1)
            for i in range(N):
                for j in range(N):
                    if i != j:
                        vd *= 1 - z_all[v][i] / z_all[v][j]
            vandermonde[v] = sp.expand(vd)
            norm *= factorial(N)

    out: dict[int, Any] = {}
    for k, coeff in pe.items():
        val = sp.expand(coeff)
        for v, N in enumerate(ranks):
            if N >= 2:
                val = sp.expand(val * vandermonde[v])
                for zv in z_free[v]:
                    val = _constant_term(val, zv, K, sp)
                    if val == 0:
                        break
        if val != 0:
            out[k] = sp.Rational(val, norm) if not getattr(val, "free_symbols", set()) else val
    out.setdefault(0, sp.Integer(1))
    return out


def index_matches(
    electric_json: Mapping[str, Any],
    magnetic_json: Mapping[str, Any],
    order: int = 6,
) -> tuple[bool, dict[str, Any]]:
    """Compute both indices to `order` and test coefficient-wise equality.

    The index is a duality invariant, so genuine duals must agree to every
    order; a finite-order match is necessary (not sufficient) evidence.
    Returns ``(matches, details)``.
    """

    sp = _require_sympy()
    ie = index_series(electric_json, order)
    im = index_series(magnetic_json, order)
    powers = sorted(set(ie) | set(im))
    diffs = []
    for k in powers:
        d = sp.simplify(ie.get(k, sp.Integer(0)) - im.get(k, sp.Integer(0)))
        if d != 0:
            diffs.append({"u_power": k, "electric": str(ie.get(k, 0)),
                          "magnetic": str(im.get(k, 0))})
    details = {
        "order": order,
        "electric": {k: str(v) for k, v in sorted(ie.items())},
        "magnetic": {k: str(v) for k, v in sorted(im.items())},
        "mismatches": diffs,
    }
    return (not diffs), details


def format_index(series: Mapping[int, Any], order: int | None = None) -> str:
    """Human-readable 'c0 + c1 u^1 + ...' rendering of an index series."""

    items = sorted(series.items())
    if order is not None:
        items = [(k, v) for k, v in items if k <= order]
    return " + ".join(f"{v}*u^{k}" if k else f"{v}" for k, v in items if v != 0)
