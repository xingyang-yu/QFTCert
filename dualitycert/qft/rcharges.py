"""R-symmetry observables and unitarity-bound checks."""

from __future__ import annotations

from fractions import Fraction
from typing import Iterable

from dualitycert.core.objects import CheckResult, DualityClaim, Field, SINGLET, Theory, r_charge_equal
from dualitycert.core.status import Status
from dualitycert.groups.su import dimension
from dualitycert.qft.a_maximization import (
    AMaxError,
    asymptotic_freedom_report,
    audit_superconformal_r,
    central_charge_scft_bounds,
    central_charges_match,
    mesonic_unitarity_scan,
    superconformal_central_charges,
)
from dualitycert.qft.pure_quiver_json import (
    PureQuiverJSONError,
    pure_quiver_to_json,
)


UNITARITY_R_BOUND = Fraction(2, 3)

A_MAXIMIZATION_OBLIGATION = "a-maximization central charge matching"
SUPERCONFORMAL_AUDIT_OBLIGATION = "superconformal R-charge audit"
SCFT_SOUNDNESS_OBLIGATION = "SCFT soundness (necessary conditions)"


def scft_soundness_check(claim: DualityClaim) -> CheckResult:
    """Necessary conditions for each theory to be a unitary 4d N=1 SCFT.

    A battery of independent NECESSARY conditions (a failure proves the
    input is not the SCFT it claims to be; passing them is NOT sufficient --
    "certificates, not proofs"):

    - **Hofman-Maldacena (the hard gate):** a > 0, c > 0 and
      ``1/2 <= a/c <= 3/2`` on the a-maximized central charges. Violating
      this means the theory is not a unitary SCFT, so the obligation FAILS.
    - **Composite unitarity (warning):** single-trace mesonic gauge
      invariants with R < 2/3 are flagged as candidate decoupling free
      fields (broadens the v1 singlet-only scan; F-relations are not
      imposed, so these are candidates to confirm, not a hard failure).
    - **One-loop beta coefficients (diagnostic only):** per-node ``b0`` is
      reported in ``details`` but NEVER gates -- the exact conformal
      condition is the ABJ R-anomaly already enforced elsewhere, and a
      node with ``b0 < 0`` is physically allowed (free-magnetic phase).

    OPT-IN via ``claim.metadata['run_scft_soundness']`` -> NOT_APPLICABLE
    otherwise, so committed certificates / benchmark ground truth are
    untouched. Requires the optional ``[amax]`` extra (sympy) for the
    central-charge gate; the b0 diagnostic is sympy-free.
    """

    if not claim.metadata.get("run_scft_soundness"):
        return CheckResult(
            status=Status.NOT_APPLICABLE,
            message=(
                "SCFT-soundness battery is opt-in; set "
                "metadata['run_scft_soundness']=True to enable it."
            ),
        )

    try:
        sides = {
            "electric": pure_quiver_to_json(claim.electric_theory),
            "magnetic": pure_quiver_to_json(claim.magnetic_theory),
        }
    except PureQuiverJSONError as exc:
        return CheckResult(
            status=Status.NOT_APPLICABLE,
            message=f"SCFT soundness requires pure-quiver theories: {exc}",
        )

    details: dict[str, dict] = {}
    hard_failures: list[str] = []
    warnings: list[str] = []
    amax_unavailable: list[str] = []
    amax_sympy_missing = False

    for side, theory_json in sides.items():
        af = asymptotic_freedom_report(theory_json)
        side_detail: dict = {
            # diagnostic only -- see scft docstring / asymptotic_freedom_report.
            "one_loop_b0": {str(v): str(b) for v, b in af["b0"].items()},
            "one_loop_ir_free_nodes": {
                str(v): str(b) for v, b in af["one_loop_ir_free_nodes"].items()
            },
        }
        try:
            res = superconformal_central_charges(theory_json)
        except AMaxError as exc:
            side_detail["a_maximization"] = f"unavailable: {exc}"
            details[side] = side_detail
            amax_unavailable.append(f"{side}: {exc}")
            if "sympy" in str(exc):
                amax_sympy_missing = True
            continue

        hm = central_charge_scft_bounds(res.a_float, res.c_float)
        mes = mesonic_unitarity_scan(theory_json, res.r_charges)
        side_detail.update(
            {
                "a": str(res.a),
                "c": str(res.c),
                "a_over_c": hm["a_over_c"],
                "hofman_maldacena_ok": hm["ok"],
                "singlet_unitarity_ok": res.unitarity_ok,
                "mesonic_unitarity_ok": mes["ok"],
                "mesonic_operators_below_bound": mes["below_bound"],
            }
        )
        details[side] = side_detail

        if not hm["ok"]:
            hard_failures.append(f"{side}: " + "; ".join(hm["violations"]))
        if not res.unitarity_ok:
            warnings.extend(f"{side}: {w}" for w in res.unitarity_warnings[1:])
        warnings.extend(f"{side}: {w}" for w in mes["warnings"])

    if hard_failures:
        return CheckResult(
            status=Status.FAILED,
            message=(
                "central-charge SCFT bounds violated (not a unitary SCFT): "
                + "; ".join(hard_failures)
            ),
            details=details,
            warnings=tuple(warnings),
        )

    if amax_unavailable:
        status = Status.UNKNOWN if amax_sympy_missing else Status.NOT_APPLICABLE
        return CheckResult(
            status=status,
            message=(
                "SCFT soundness could not run the central-charge gate "
                "(a-maximization unavailable): " + "; ".join(amax_unavailable)
            ),
            details=details,
            warnings=tuple(warnings),
        )

    return CheckResult(
        status=Status.CERTIFIED,
        message=(
            "Necessary SCFT conditions hold: a, c > 0 and the Hofman-Maldacena "
            "bound 1/2 <= a/c <= 3/2 on both theories."
        ),
        details=details,
        warnings=tuple(warnings)
        + (
            "Necessary conditions only; passing does NOT prove an interacting "
            "fixed point exists. One-loop b0 is reported as a diagnostic, not a "
            "gate (the exact conformal condition is the ABJ R-anomaly).",
        ),
    )


def superconformal_r_audit_check(claim: DualityClaim) -> CheckResult:
    """Audit that each theory's CLAIMED R is the superconformal R (judge ②a).

    This is the a-max gatekeeper for the superconformal-R policy: a claim
    whose R is inconsistent (violates R(W)=2 / gauge-anomaly) or merely
    feasible-but-not-superconformal is killed BEFORE the duality
    comparison (an ill-specified theory does not merit a duality verdict).

    OPT-IN via ``claim.metadata['run_superconformal_audit']`` -> otherwise
    NOT_APPLICABLE, so existing flows / committed ground truth are
    untouched. Requires the optional ``[amax]`` extra (sympy).
    """

    if not claim.metadata.get("run_superconformal_audit"):
        return CheckResult(
            status=Status.NOT_APPLICABLE,
            message=(
                "superconformal R-charge audit is opt-in; set "
                "metadata['run_superconformal_audit']=True to enable it."
            ),
        )

    try:
        sides = {
            "electric": pure_quiver_to_json(claim.electric_theory),
            "magnetic": pure_quiver_to_json(claim.magnetic_theory),
        }
    except PureQuiverJSONError as exc:
        return CheckResult(
            status=Status.NOT_APPLICABLE,
            message=f"superconformal audit requires pure-quiver theories: {exc}",
        )

    results: dict[str, dict] = {}
    for side, theory_json in sides.items():
        try:
            results[side] = audit_superconformal_r(theory_json)
        except AMaxError as exc:
            status = Status.UNKNOWN if "sympy" in str(exc) else Status.NOT_APPLICABLE
            return CheckResult(
                status=status, message=f"superconformal audit could not run ({side}): {exc}"
            )

    details = {
        side: {"status": r["status"], "detail": r["detail"]}
        for side, r in results.items()
    }

    for side, r in results.items():
        if r["status"] == "out_of_scope":
            return CheckResult(
                status=Status.NOT_APPLICABLE,
                message=f"{side} theory is out of a-maximization scope: {r['detail']}",
                details=details,
            )

    bad = [(side, r) for side, r in results.items() if r["status"] != "superconformal"]
    if bad:
        return CheckResult(
            status=Status.FAILED,
            message=(
                "claimed R is not the superconformal R -- "
                + "; ".join(f"{side}: {r['detail']}" for side, r in bad)
            ),
            details=details,
        )

    return CheckResult(
        status=Status.CERTIFIED,
        message="Both theories' claimed R is the superconformal (a-maximized) R.",
        details=details,
    )


def central_charge_matching(claim: DualityClaim) -> CheckResult:
    """Compare Tr R, Tr R^3, and a,c from the encoded R-symmetry.

    The formulas are the standard 4d N=1 SCFT anomaly formulas

        a = 3/32 (3 Tr R^3 - Tr R),
        c = 1/32 (9 Tr R^3 - 5 Tr R).

    This validates a stated R-symmetry; it does not perform full
    a-maximization or detect accidental symmetries.
    """

    if not _has_r_symmetry(claim.electric_theory) or not _has_r_symmetry(
        claim.magnetic_theory
    ):
        return CheckResult(
            status=Status.UNKNOWN,
            message="No encoded U(1)_R symmetry is available for central-charge checks.",
            details={"implemented": ["Tr R", "Tr R^3", "a", "c"]},
        )

    electric = r_symmetry_observables(claim.electric_theory)
    magnetic = r_symmetry_observables(claim.magnetic_theory)
    mismatches = [
        key
        for key in ("TrR", "TrR3", "a", "c")
        if not r_charge_equal(electric[key], magnetic[key])
    ]
    details = {
        "electric": electric,
        "magnetic": magnetic,
        "not_implemented": [
            "full a-maximization over trial mixings",
            "automatic accidental-symmetry detection",
            "automatic decoupled-free-field repair",
        ],
    }
    if mismatches:
        return CheckResult(
            status=Status.FAILED,
            message="Encoded R-symmetry observables do not match: "
            + ", ".join(mismatches),
            details=details,
        )
    return CheckResult(
        status=Status.CERTIFIED,
        message="Encoded R-symmetry Tr R, Tr R^3, a, and c match.",
        details=details,
        warnings=(
            "This validates the encoded R-symmetry data; it does not run full a-maximization.",
        ),
    )


def a_maximization_matching(claim: DualityClaim) -> CheckResult:
    """Independently a-maximize both theories and compare the central charges.

    Stronger than `central_charge_matching`: it recomputes the
    superconformal R on each side (no reference to the encoded R or to the
    other theory), so genuine Seiberg duals match even when their encoded
    R is merely rational-feasible (the irrational-R families).

    OPT-IN: runs only when ``claim.metadata['run_a_maximization']`` is
    truthy, returning NOT_APPLICABLE otherwise. NOT_APPLICABLE is
    non-blocking and never enters `failed_obligations`, so registering
    this obligation does not perturb any committed certificate / benchmark
    ground truth until a caller explicitly opts in. A claim may also pass
    ``flavor_u1_basis_electric`` / ``flavor_u1_basis_magnetic`` (Lean-style
    declared flavor bases); when absent the verifier-derived kernel is used.
    """

    if not claim.metadata.get("run_a_maximization"):
        return CheckResult(
            status=Status.NOT_APPLICABLE,
            message=(
                "a-maximization is opt-in; set "
                "metadata['run_a_maximization']=True to enable it."
            ),
        )

    try:
        electric_json = pure_quiver_to_json(claim.electric_theory)
        magnetic_json = pure_quiver_to_json(claim.magnetic_theory)
    except PureQuiverJSONError as exc:
        return CheckResult(
            status=Status.NOT_APPLICABLE,
            message=f"a-maximization requires pure-quiver theories: {exc}",
        )

    meta = claim.metadata
    try:
        electric = superconformal_central_charges(
            electric_json, flavor_basis=meta.get("flavor_u1_basis_electric")
        )
        magnetic = superconformal_central_charges(
            magnetic_json, flavor_basis=meta.get("flavor_u1_basis_magnetic")
        )
    except AMaxError as exc:
        status = Status.UNKNOWN if "sympy" in str(exc) else Status.NOT_APPLICABLE
        return CheckResult(status=status, message=f"a-maximization could not run: {exc}")

    details = {
        "electric": {
            "a": str(electric.a), "c": str(electric.c),
            "flavor_dim": electric.flavor_dim, "exact": electric.exact,
        },
        "magnetic": {
            "a": str(magnetic.a), "c": str(magnetic.c),
            "flavor_dim": magnetic.flavor_dim, "exact": magnetic.exact,
        },
    }
    warnings = electric.unitarity_warnings + magnetic.unitarity_warnings

    if not (electric.unitarity_ok and magnetic.unitarity_ok):
        return CheckResult(
            status=Status.NOT_APPLICABLE,
            message=(
                "a-maximization out of scope: a gauge-singlet chiral operator "
                "violates the unitarity bound (R < 2/3), so a free field "
                "decouples; v1 does not perform the decoupling correction."
            ),
            details=details,
            warnings=warnings,
        )

    a_ok, c_ok = central_charges_match(electric, magnetic)
    if a_ok and c_ok:
        return CheckResult(
            status=Status.CERTIFIED,
            message=(
                f"Independent a-maximization: a = {electric.a} and "
                f"c = {electric.c} match across the duality."
            ),
            details=details,
            warnings=warnings
            + (
                "Assumes the trial flavor space is complete and no operators "
                "decouple below the unitarity bound.",
            ),
        )

    mismatches = []
    if not a_ok:
        mismatches.append(f"a: {electric.a} vs {magnetic.a}")
    if not c_ok:
        mismatches.append(f"c: {electric.c} vs {magnetic.c}")
    return CheckResult(
        status=Status.FAILED,
        message="Independent a-maximization mismatch -- " + "; ".join(mismatches),
        details=details,
        warnings=warnings,
    )


def operator_unitarity_bound_check(claim: DualityClaim) -> CheckResult:
    """Check R >= 2/3 for encoded gauge-invariant chiral operators.

    The bound is applied only to gauge-invariant chiral operators represented
    by metadata or, for SQCD claims, to the standard meson and baryon maps. It
    assumes the encoded R is the superconformal R-charge.
    """

    operators = _encoded_operators(claim)
    if not operators:
        return CheckResult(
            status=Status.UNKNOWN,
            message="No gauge-invariant chiral operator R-charge data is encoded.",
            details={"bound": UNITARITY_R_BOUND},
        )

    failures: list[str] = []
    details: dict[str, dict[str, Fraction]] = {}
    for name, r_charge in operators:
        delta = Fraction(3, 2) * r_charge
        details[name] = {"R": r_charge, "Delta": delta}
        if r_charge < UNITARITY_R_BOUND:
            failures.append(f"{name} has R={r_charge} < 2/3")

    if failures:
        return CheckResult(
            status=Status.FAILED,
            message="Chiral-operator unitarity bound failed: " + "; ".join(failures),
            details=details,
        )
    return CheckResult(
        status=Status.CERTIFIED,
        message="Encoded gauge-invariant chiral operators satisfy R >= 2/3.",
        details=details,
        warnings=(
            "Unitarity is checked only for encoded/default SQCD gauge-invariant operators.",
        ),
    )


def r_symmetry_observables(theory: Theory) -> dict[str, Fraction]:
    """Compute Tr R, Tr R^3, a, and c from left-handed Weyl fermions."""

    gaugino_dim = sum(node.dim_adjoint for node in theory.gauge_nodes)
    tr_r = Fraction(gaugino_dim, 1)
    tr_r3 = Fraction(gaugino_dim, 1)
    nonabelian_globals = theory.nonabelian_globals()

    for field in theory.fields:
        if not field.is_chiral:
            continue
        r_fermion = field.r_charge - 1
        multiplicity = field.multiplicity
        for node in theory.gauge_nodes:
            multiplicity *= dimension(field.rep_for_node(node.label), node)
        for symmetry in nonabelian_globals:
            multiplicity *= dimension(field.rep_for_global(symmetry.label), symmetry)
        tr_r += multiplicity * r_fermion
        tr_r3 += multiplicity * r_fermion**3

    return {
        "TrR": tr_r,
        "TrR3": tr_r3,
        "a": Fraction(3, 32) * (3 * tr_r3 - tr_r),
        "c": Fraction(1, 32) * (9 * tr_r3 - 5 * tr_r),
    }


def _has_r_symmetry(theory: Theory) -> bool:
    return any(sym.is_r for sym in theory.u1_globals())


def _encoded_operators(claim: DualityClaim) -> tuple[tuple[str, Fraction], ...]:
    metadata_operators = claim.metadata.get("operators", ())
    parsed = []
    for item in metadata_operators:
        name = item.get("name")
        r_charge = item.get("R")
        if name is not None and r_charge is not None:
            parsed.append((str(name), Fraction(r_charge)))
    if parsed:
        return tuple(parsed)

    if claim.metadata.get("duality_profile") != "seiberg_sqcd":
        return ()

    parameters = claim.metadata.get("parameters", {})
    nc = parameters.get("Nc")
    if nc is None:
        return ()
    electric_fields = claim.electric_theory.field_map()
    magnetic_fields = claim.magnetic_theory.field_map()
    magnetic_rank = claim.magnetic_theory.gauge_nodes[0].N
    standard_maps = (
        ("meson electric Q Qtilde", (("Q", 1), ("Qtilde", 1)), electric_fields),
        ("meson magnetic M", (("M", 1),), magnetic_fields),
        ("baryon electric Q^Nc", (("Q", int(nc)),), electric_fields),
        ("baryon magnetic q^Nmag", (("q", magnetic_rank),), magnetic_fields),
        ("antibaryon electric Qtilde^Nc", (("Qtilde", int(nc)),), electric_fields),
        (
            "antibaryon magnetic qtilde^Nmag",
            (("qtilde", magnetic_rank),),
            magnetic_fields,
        ),
    )
    operators = []
    for name, factors, fields in standard_maps:
        r_charge = _operator_r_charge(factors, fields)
        if r_charge is not None:
            operators.append((name, r_charge))
    return tuple(operators)


def _operator_r_charge(
    factors: Iterable[tuple[str, int]],
    fields: dict[str, Field],
) -> Fraction | None:
    total = Fraction(0, 1)
    for field_name, power in factors:
        field = fields.get(field_name)
        if field is None:
            return None
        total += power * field.r_charge
    return total
