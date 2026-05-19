"""Kutasov-Schwimmer duality claim builder and Kutasov-specific checks.

Electric: SU(Nc), Nf flavors Q/Qtilde + adjoint X, W_el = Tr(X^{k+1}).
Magnetic: SU(kNf-Nc), Nf flavors q/qtilde + adjoint Y + meson tower
          M_j (j=0..k-1), W_mag = Tr(Y^{k+1}) + sum_j M_j q Y^{k-1-j} qtilde.

R-charge assignments follow from the anomaly-free condition for each gauge group:
  R(X) = R(Y) = 2/(k+1)
  R_el  = 1 - 2*Nc  / (Nf*(k+1))
  R_mag = 1 - 2*Nm  / (Nf*(k+1))   [uses the claimed magnetic rank Nm]
  R(M_j) = 2*R_el + j * R(X)        [M_j = tr(Qtilde X^j Q)]
"""

from __future__ import annotations

from fractions import Fraction

from dualitycert.core.objects import (
    CheckResult,
    DualityClaim,
    Field,
    SuperpotentialTerm,
    SymmetryMap,
    Theory,
)
from dualitycert.core.status import Status
from dualitycert.groups.su import adjoint, antifundamental, fundamental, su
from dualitycert.groups.u1 import u1, u1_r


def build_kutasov_claim(
    Nc: int,
    Nf: int,
    k: int,
    *,
    magnetic_color_rank: int | None = None,
    claim_name: str | None = None,
) -> DualityClaim:
    """Build the Kutasov-Schwimmer duality claim."""

    if k < 1:
        raise ValueError("k must be at least 1")
    if Nc < 2:
        raise ValueError("Nc must be at least 2")
    if Nf < 1:
        raise ValueError("Nf must be at least 1")

    Nm = magnetic_color_rank if magnetic_color_rank is not None else k * Nf - Nc
    if Nm < 2:
        raise ValueError("Magnetic SU(N) rank must be at least 2")

    su_l_label = "SU(Nf)_L"
    su_r_label = "SU(Nf)_R"
    baryon_label = "U(1)_B"
    r_label = "U(1)_R"

    globals_ = (
        su(Nf, label=su_l_label, global_symmetry=True),
        su(Nf, label=su_r_label, global_symmetry=True),
        u1(baryon_label),
        u1_r(r_label),
    )

    r_X = Fraction(2, k + 1)
    r_el = 1 - Fraction(2 * Nc, Nf * (k + 1))
    r_mag = 1 - Fraction(2 * Nm, Nf * (k + 1))

    el_node = su(Nc)
    mag_node = su(Nm)

    electric_fields = (
        Field(
            name="Q",
            field_type="chiral multiplet",
            gauge_reps={el_node.label: fundamental()},
            global_reps={su_l_label: fundamental()},
            u1_charges={baryon_label: Fraction(1, Nc)},
            r_charge=r_el,
        ),
        Field(
            name="Qtilde",
            field_type="chiral multiplet",
            gauge_reps={el_node.label: antifundamental()},
            global_reps={su_r_label: antifundamental()},
            u1_charges={baryon_label: Fraction(-1, Nc)},
            r_charge=r_el,
        ),
        Field(
            name="X",
            field_type="chiral multiplet",
            gauge_reps={el_node.label: adjoint()},
            global_reps={},
            u1_charges={baryon_label: Fraction(0)},
            r_charge=r_X,
        ),
    )

    electric = Theory(
        name=f"Kutasov electric SU({Nc}) Nf={Nf} k={k}",
        gauge_nodes=(el_node,),
        global_symmetries=globals_,
        fields=electric_fields,
        superpotential_terms=(
            SuperpotentialTerm(
                factors=(("X", k + 1),),
                label=f"Tr(X^{k + 1})",
            ),
        ),
    )

    magnetic_fields: list[Field] = [
        Field(
            name="q",
            field_type="chiral multiplet",
            gauge_reps={mag_node.label: fundamental()},
            global_reps={su_l_label: antifundamental()},
            u1_charges={baryon_label: Fraction(1, Nm)},
            r_charge=r_mag,
        ),
        Field(
            name="qtilde",
            field_type="chiral multiplet",
            gauge_reps={mag_node.label: antifundamental()},
            global_reps={su_r_label: fundamental()},
            u1_charges={baryon_label: Fraction(-1, Nm)},
            r_charge=r_mag,
        ),
        Field(
            name="Y",
            field_type="chiral multiplet",
            gauge_reps={mag_node.label: adjoint()},
            global_reps={},
            u1_charges={baryon_label: Fraction(0)},
            r_charge=r_X,
        ),
    ]

    # Meson tower: M_j = tr(Qtilde X^j Q), j = 0, ..., k-1
    for j in range(k):
        r_Mj = 2 * r_el + j * r_X
        magnetic_fields.append(
            Field(
                name=f"M{j}",
                field_type="chiral multiplet",
                gauge_reps={},
                global_reps={
                    su_l_label: fundamental(),
                    su_r_label: antifundamental(),
                },
                u1_charges={baryon_label: Fraction(0)},
                r_charge=r_Mj,
            )
        )

    # Magnetic superpotential: Tr(Y^{k+1}) + sum_j M_j q Y^{k-1-j} qtilde
    mag_terms: list[SuperpotentialTerm] = [
        SuperpotentialTerm(
            factors=(("Y", k + 1),),
            label=f"Tr(Y^{k + 1})",
        )
    ]
    for j in range(k):
        power_Y = k - 1 - j
        if power_Y > 0:
            factors: tuple[tuple[str, int], ...] = (
                (f"M{j}", 1),
                ("q", 1),
                ("Y", power_Y),
                ("qtilde", 1),
            )
            label = f"M{j} q Y^{power_Y} qtilde"
        else:
            factors = ((f"M{j}", 1), ("q", 1), ("qtilde", 1))
            label = f"M{j} q qtilde"
        mag_terms.append(SuperpotentialTerm(factors=factors, label=label))

    magnetic = Theory(
        name=f"Kutasov magnetic SU({Nm}) Nf={Nf} k={k}",
        gauge_nodes=(mag_node,),
        global_symmetries=globals_,
        fields=tuple(magnetic_fields),
        superpotential_terms=tuple(mag_terms),
    )

    # Operator map: meson tower M_j = tr(Qtilde X^j Q) for j=0..k-1.
    # Bare baryon maps (Q^Nc <-> q^Nm) are omitted: in Kutasov-Schwimmer
    # duality with k>=2 the correct baryon operators are X-dressed and their
    # R-charges do not match the naive Q^Nc / q^Nm power.
    operator_map: dict[str, str] = {}
    for j in range(k):
        if j == 0:
            el_op = "Qtilde Q"
        elif j == 1:
            el_op = "Qtilde X Q"
        else:
            el_op = f"Qtilde X^{j} Q"
        operator_map[el_op] = f"M{j}"

    return DualityClaim(
        name=claim_name or f"Kutasov SU({Nc}) Nf={Nf} k={k}",
        electric_theory=electric,
        magnetic_theory=magnetic,
        symmetry_map=SymmetryMap(
            {
                su_l_label: su_l_label,
                su_r_label: su_r_label,
                baryon_label: baryon_label,
                r_label: r_label,
            }
        ),
        operator_map=operator_map,
        metadata={
            "duality_profile": "kutasov",
            "parameters": {
                "Nc": Nc,
                "Nf": Nf,
                "k": k,
                "magnetic_rank": Nm,
                "expected_magnetic_rank": k * Nf - Nc,
            },
        },
    )


def kutasov_meson_tower_completeness_check(claim: DualityClaim) -> CheckResult:
    """Check that the magnetic theory contains exactly the k expected meson fields.

    For a Kutasov-Schwimmer duality with parameter k, the magnetic theory must
    contain k meson fields M0, M1, ..., M{k-1} as gauge-singlet chiral multiplets
    transforming in (fund_L, antifund_R) of the flavor group.
    """

    parameters = claim.metadata.get("parameters", {})
    k = parameters.get("k")
    if k is None:
        return CheckResult(
            status=Status.UNKNOWN,
            message="Kutasov parameter k is missing from claim metadata.",
        )
    k = int(k)

    magnetic_fields = claim.magnetic_theory.field_map()
    expected_names = [f"M{j}" for j in range(k)]
    present = [name for name in expected_names if name in magnetic_fields]
    missing = [name for name in expected_names if name not in magnetic_fields]
    unexpected = [
        name
        for name in magnetic_fields
        if name.startswith("M") and name not in expected_names
    ]

    details = {
        "k": k,
        "expected_mesons": expected_names,
        "present": present,
        "missing": missing,
        "unexpected_M_fields": unexpected,
    }

    if missing or unexpected:
        parts = []
        if missing:
            parts.append(f"missing: {missing}")
        if unexpected:
            parts.append(f"unexpected: {unexpected}")
        return CheckResult(
            status=Status.FAILED,
            message="Kutasov meson tower incomplete: " + "; ".join(parts),
            details=details,
        )
    return CheckResult(
        status=Status.CERTIFIED,
        message=f"Meson tower M0..M{k - 1} is complete ({k} fields present).",
        details=details,
    )
