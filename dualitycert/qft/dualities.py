"""SQCD-like duality claim builders and obligation generation."""

from __future__ import annotations

from fractions import Fraction

from dualitycert.core.certificates import Certificate
from dualitycert.core.objects import (
    DualityClaim,
    Field,
    SuperpotentialTerm,
    SymmetryMap,
    Theory,
)
from dualitycert.core.obligations import Obligation
from dualitycert.groups.su import antifundamental, fundamental, singlet, su
from dualitycert.groups.u1 import u1, u1_r
from dualitycert.qft.anomalies import compare_anomaly_tables, gauge_anomaly_cancellation
from dualitycert.qft.susy import superpotential_consistency


def generate_obligations(claim: DualityClaim) -> tuple[Obligation, ...]:
    """Generate the first-prototype obligations for a duality claim."""

    electric = claim.electric_theory
    magnetic = claim.magnetic_theory
    return (
        Obligation(
            name="electric gauge anomaly cancellation",
            description="The electric SU(N) gauge cubic anomaly must cancel.",
            checker=lambda: gauge_anomaly_cancellation(electric),
        ),
        Obligation(
            name="magnetic gauge anomaly cancellation",
            description="The magnetic SU(N) gauge cubic anomaly must cancel.",
            checker=lambda: gauge_anomaly_cancellation(magnetic),
        ),
        Obligation(
            name="electric superpotential consistency",
            description="The electric superpotential must be invariant and have R-charge 2.",
            checker=lambda: superpotential_consistency(electric),
        ),
        Obligation(
            name="magnetic superpotential consistency",
            description="The magnetic superpotential must be invariant and have R-charge 2.",
            checker=lambda: superpotential_consistency(magnetic),
        ),
        Obligation(
            name="global anomaly matching",
            description="Global 't Hooft anomaly tables must match under the symmetry map.",
            checker=lambda: compare_anomaly_tables(
                electric,
                magnetic,
                claim.symmetry_map,
            ),
        ),
        Obligation(
            name="operator map consistency",
            description="Check that mapped operators have matching quantum numbers.",
        ),
        Obligation(
            name="index matching",
            description="Check equality of protected indices in a supported expansion.",
        ),
        Obligation(
            name="deformation checks",
            description="Check consistency under masses, Higgsing, and other deformations.",
        ),
    )


def evaluate_claim(claim: DualityClaim) -> Certificate:
    """Run generated obligations and assemble a certificate."""

    results = [obligation.run() for obligation in generate_obligations(claim)]
    return Certificate.from_results(claim.name, results)


def build_seiberg_sqcd_claim(
    Nc: int,
    Nf: int,
    *,
    magnetic_color_rank: int | None = None,
    include_meson: bool = True,
    include_magnetic_superpotential: bool = True,
    magnetic_meson_r_charge: Fraction | int | str | None = None,
    magnetic_quark_r_charge: Fraction | int | str | None = None,
    claim_name: str | None = None,
) -> DualityClaim:
    """Build the standard SQCD-like Seiberg duality example.

    The baryon number convention is B(Q)=1/Nc and B(q)=1/(Nf-Nc), using the
    actual magnetic color rank when a deliberately wrong rank is requested.
    """

    if Nc < 2:
        raise ValueError("Nc must be at least 2")
    if Nf <= Nc:
        raise ValueError("This SQCD builder requires Nf > Nc")

    Nm = magnetic_color_rank if magnetic_color_rank is not None else Nf - Nc
    if Nm < 2:
        raise ValueError("The supported magnetic SU(N) rank must be at least 2")

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

    rq_electric = Fraction(Nf - Nc, Nf)
    rq_magnetic = (
        Fraction(Nc, Nf)
        if magnetic_quark_r_charge is None
        else Fraction(magnetic_quark_r_charge)
    )
    rm = (
        Fraction(2 * (Nf - Nc), Nf)
        if magnetic_meson_r_charge is None
        else Fraction(magnetic_meson_r_charge)
    )

    electric = Theory(
        name=f"Electric SQCD SU({Nc}) with Nf={Nf}",
        gauge_group=su(Nc),
        global_symmetries=globals_,
        fields=(
            Field(
                name="Q",
                field_type="chiral multiplet",
                gauge_rep=fundamental(),
                global_reps={su_l_label: fundamental()},
                u1_charges={baryon_label: Fraction(1, Nc)},
                r_charge=rq_electric,
            ),
            Field(
                name="Qtilde",
                field_type="chiral multiplet",
                gauge_rep=antifundamental(),
                global_reps={su_r_label: antifundamental()},
                u1_charges={baryon_label: Fraction(-1, Nc)},
                r_charge=rq_electric,
            ),
        ),
        superpotential_terms=(),
    )

    magnetic_fields = [
        Field(
            name="q",
            field_type="chiral multiplet",
            gauge_rep=fundamental(),
            global_reps={su_l_label: antifundamental()},
            u1_charges={baryon_label: Fraction(1, Nm)},
            r_charge=rq_magnetic,
        ),
        Field(
            name="qtilde",
            field_type="chiral multiplet",
            gauge_rep=antifundamental(),
            global_reps={su_r_label: fundamental()},
            u1_charges={baryon_label: Fraction(-1, Nm)},
            r_charge=rq_magnetic,
        ),
    ]
    if include_meson:
        magnetic_fields.append(
            Field(
                name="M",
                field_type="chiral multiplet",
                gauge_rep=singlet(),
                global_reps={
                    su_l_label: fundamental(),
                    su_r_label: antifundamental(),
                },
                u1_charges={baryon_label: Fraction(0, 1)},
                r_charge=rm,
            )
        )

    magnetic_terms = (
        (
            SuperpotentialTerm(
                factors=(("M", 1), ("q", 1), ("qtilde", 1)),
                label="M q qtilde",
            ),
        )
        if include_magnetic_superpotential
        else ()
    )
    magnetic = Theory(
        name=f"Magnetic SQCD SU({Nm}) with Nf={Nf}",
        gauge_group=su(Nm),
        global_symmetries=globals_,
        fields=tuple(magnetic_fields),
        superpotential_terms=magnetic_terms,
    )

    return DualityClaim(
        name=claim_name or f"Seiberg SQCD Nc={Nc}, Nf={Nf}",
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
        operator_map={"Q Qtilde": "M"},
    )
