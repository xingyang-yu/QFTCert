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
from dualitycert.core.obligations import Obligation, ObligationResult
from dualitycert.groups.su import antifundamental, fundamental, su
from dualitycert.groups.u1 import u1, u1_r
from dualitycert.core.theory_kind import infer_claim_theory_kind
from dualitycert.qft.checks import build_default_registry


def generate_obligations(claim: DualityClaim) -> tuple[Obligation, ...]:
    """Generate the first-prototype obligations for a duality claim.

    Convenience wrapper — does NOT propagate upstream results between
    obligations. `evaluate_claim` does that propagation when running them.
    """

    return build_default_registry().obligations_for(claim)


def evaluate_claim(claim: DualityClaim) -> Certificate:
    """Run obligations and assemble a certificate.

    Each obligation is constructed from its `CheckSpec.factory` and run
    in registry order. The accumulating `prior_results` dict is passed
    to every spec via `obligation_for`, so a 2-arg factory can read the
    `ObligationResult` of any earlier check by key (option A from Phase
    2a design doc §14 step 4).
    """

    registry = build_default_registry()
    prior_results: dict[str, ObligationResult] = {}
    results: list[ObligationResult] = []
    for spec in registry.applicable_specs(claim):
        obligation = spec.obligation_for(claim, prior_results)
        result = obligation.run()
        results.append(result)
        prior_results[spec.key] = result
    return Certificate.from_results(
        claim.name,
        tuple(results),
        duality_profile=claim.metadata.get("duality_profile"),
        theory_kind=infer_claim_theory_kind(claim),
        parameters=claim.metadata.get("parameters", {}),
    )


def build_seiberg_sqcd_claim(
    Nc: int,
    Nf: int,
    *,
    magnetic_color_rank: int | None = None,
    include_meson: bool = True,
    include_magnetic_superpotential: bool = True,
    magnetic_meson_r_charge: Fraction | int | str | None = None,
    magnetic_quark_r_charge: Fraction | int | str | None = None,
    magnetic_q_b_charge: Fraction | int | str | None = None,
    magnetic_qtilde_b_charge: Fraction | int | str | None = None,
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
    q_b = Fraction(1, Nm) if magnetic_q_b_charge is None else Fraction(magnetic_q_b_charge)
    qtilde_b = (
        Fraction(-1, Nm)
        if magnetic_qtilde_b_charge is None
        else Fraction(magnetic_qtilde_b_charge)
    )

    el_node = su(Nc)
    mag_node = su(Nm)

    electric = Theory(
        name=f"Electric SQCD SU({Nc}) with Nf={Nf}",
        gauge_nodes=(el_node,),
        global_symmetries=globals_,
        fields=(
            Field(
                name="Q",
                field_type="chiral multiplet",
                gauge_reps={el_node.label: fundamental()},
                global_reps={su_l_label: fundamental()},
                u1_charges={baryon_label: Fraction(1, Nc)},
                r_charge=rq_electric,
            ),
            Field(
                name="Qtilde",
                field_type="chiral multiplet",
                gauge_reps={el_node.label: antifundamental()},
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
            gauge_reps={mag_node.label: fundamental()},
            global_reps={su_l_label: antifundamental()},
            u1_charges={baryon_label: q_b},
            r_charge=rq_magnetic,
        ),
        Field(
            name="qtilde",
            field_type="chiral multiplet",
            gauge_reps={mag_node.label: antifundamental()},
            global_reps={su_r_label: fundamental()},
            u1_charges={baryon_label: qtilde_b},
            r_charge=rq_magnetic,
        ),
    ]
    if include_meson:
        magnetic_fields.append(
            Field(
                name="M",
                field_type="chiral multiplet",
                gauge_reps={},
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
        gauge_nodes=(mag_node,),
        global_symmetries=globals_,
        fields=tuple(magnetic_fields),
        superpotential_terms=magnetic_terms,
    )

    # A-route: claim self-describes its asserted operator map.
    # The mesonic entry is dropped when there is no magnetic M field, so the
    # claim only asserts operators that actually exist on both sides.
    operator_map_dict: dict[str, str] = {}
    if include_meson:
        operator_map_dict["Q Qtilde"] = "M"
    operator_map_dict[f"Q^{Nc}"] = f"q^{Nm}"
    operator_map_dict[f"Qtilde^{Nc}"] = f"qtilde^{Nm}"

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
        operator_map=operator_map_dict,
        metadata={
            "duality_profile": "seiberg_sqcd",
            "parameters": {
                "Nc": Nc,
                "Nf": Nf,
                "magnetic_rank": Nm,
                "expected_magnetic_rank": Nf - Nc,
                "include_meson": include_meson,
                "include_magnetic_superpotential": include_magnetic_superpotential,
            },
        },
    )
