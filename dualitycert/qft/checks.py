"""Default registry of QFTCert consistency checks."""

from __future__ import annotations

from dualitycert.core.obligations import Obligation
from dualitycert.core.registry import CheckRegistry, CheckSpec
from dualitycert.core.theory_kind import theory_kind_classification_check
from dualitycert.qft.anomalies import (
    compare_anomaly_tables,
    gauge_anomaly_cancellation,
    gauge_global_mixed_anomaly_cancellation,
)
from dualitycert.qft.chiral_ring import sqcd_magnetic_meson_f_term_lifting_check
from dualitycert.qft.deformations import (
    sqcd_mesonic_flat_direction_flow_check,
    sqcd_one_flavor_mass_deformation_check,
)
from dualitycert.qft.kutasov import kutasov_meson_tower_completeness_check
from dualitycert.qft.operators import (
    minimal_operator_map_abelian_charges,
    sqcd_operator_map_nonabelian_flavor_labels,
)
from dualitycert.qft.quiver_chiral_ring import (
    bounded_chiral_ring_consistency_check,
)
from dualitycert.qft.rcharges import (
    central_charge_matching,
    operator_unitarity_bound_check,
)
from dualitycert.qft.scaffolds import (
    chiral_ring_metadata_check,
    conformal_manifold_metadata_check,
    generalized_symmetry_metadata_check,
    moduli_space_metadata_check,
    protected_quantity_hooks_check,
)
from dualitycert.qft.susy import superpotential_consistency
from dualitycert.qft.symmetries import global_symmetry_matching


def build_default_registry() -> CheckRegistry:
    """Build the ordered default obligation registry for DualityCert-0."""

    return CheckRegistry(
        (
            CheckSpec(
                key="theory_kind_classification",
                name="theory kind classification",
                description=(
                    "Classify the claim as pure_quiver, flavored_single_gauge, or flavored_quiver "
                    "and confirm verifier scope."
                ),
                always_run=True,
                factory=lambda claim: Obligation(
                    name="theory kind classification",
                    description=(
                        "Classify the claim as pure_quiver, flavored_single_gauge, or "
                        "flavored_quiver and confirm verifier scope."
                    ),
                    checker=lambda: theory_kind_classification_check(claim),
                    checker_name="theory_kind_classification_check",
                ),
            ),
            CheckSpec(
                key="electric_gauge_anomaly",
                name="electric gauge anomaly cancellation",
                description="The electric SU(N) gauge cubic anomaly must cancel.",
                factory=lambda claim: Obligation(
                    name="electric gauge anomaly cancellation",
                    description="The electric SU(N) gauge cubic anomaly must cancel.",
                    checker=lambda: gauge_anomaly_cancellation(claim.electric_theory),
                    checker_name="gauge_anomaly_cancellation",
                ),
            ),
            CheckSpec(
                key="magnetic_gauge_anomaly",
                name="magnetic gauge anomaly cancellation",
                description="The magnetic SU(N) gauge cubic anomaly must cancel.",
                factory=lambda claim: Obligation(
                    name="magnetic gauge anomaly cancellation",
                    description="The magnetic SU(N) gauge cubic anomaly must cancel.",
                    checker=lambda: gauge_anomaly_cancellation(claim.magnetic_theory),
                    checker_name="gauge_anomaly_cancellation",
                ),
            ),
            CheckSpec(
                key="electric_gauge_global_mixed_anomaly",
                name="electric gauge-global mixed anomaly cancellation",
                description="The electric SU(gauge)^2 U(1) mixed anomalies must cancel.",
                factory=lambda claim: Obligation(
                    name="electric gauge-global mixed anomaly cancellation",
                    description="The electric SU(gauge)^2 U(1) mixed anomalies must cancel.",
                    checker=lambda: gauge_global_mixed_anomaly_cancellation(
                        claim.electric_theory
                    ),
                    checker_name="gauge_global_mixed_anomaly_cancellation",
                ),
            ),
            CheckSpec(
                key="magnetic_gauge_global_mixed_anomaly",
                name="magnetic gauge-global mixed anomaly cancellation",
                description="The magnetic SU(gauge)^2 U(1) mixed anomalies must cancel.",
                factory=lambda claim: Obligation(
                    name="magnetic gauge-global mixed anomaly cancellation",
                    description="The magnetic SU(gauge)^2 U(1) mixed anomalies must cancel.",
                    checker=lambda: gauge_global_mixed_anomaly_cancellation(
                        claim.magnetic_theory
                    ),
                    checker_name="gauge_global_mixed_anomaly_cancellation",
                ),
            ),
            CheckSpec(
                key="electric_superpotential",
                name="electric superpotential consistency",
                description="The electric superpotential must be invariant and have R-charge 2.",
                factory=lambda claim: Obligation(
                    name="electric superpotential consistency",
                    description="The electric superpotential must be invariant and have R-charge 2.",
                    checker=lambda: superpotential_consistency(claim.electric_theory),
                    checker_name="superpotential_consistency",
                ),
            ),
            CheckSpec(
                key="magnetic_superpotential",
                name="magnetic superpotential consistency",
                description="The magnetic superpotential must be invariant and have R-charge 2.",
                factory=lambda claim: Obligation(
                    name="magnetic superpotential consistency",
                    description="The magnetic superpotential must be invariant and have R-charge 2.",
                    checker=lambda: superpotential_consistency(claim.magnetic_theory),
                    checker_name="superpotential_consistency",
                ),
            ),
            CheckSpec(
                key="global_symmetry_matching",
                name="global symmetry matching",
                description="Represented continuous global symmetry factors should match.",
                factory=lambda claim: Obligation(
                    name="global symmetry matching",
                    description="Represented continuous global symmetry factors should match.",
                    checker=lambda: global_symmetry_matching(claim),
                    checker_name="global_symmetry_matching",
                ),
            ),
            CheckSpec(
                key="global_anomaly_matching",
                name="global anomaly matching",
                description="Global 't Hooft anomaly tables must match under the symmetry map.",
                factory=lambda claim: Obligation(
                    name="global anomaly matching",
                    description="Global 't Hooft anomaly tables must match under the symmetry map.",
                    checker=lambda: compare_anomaly_tables(
                        claim.electric_theory,
                        claim.magnetic_theory,
                        claim.symmetry_map,
                    ),
                    checker_name="compare_anomaly_tables",
                ),
            ),
            CheckSpec(
                key="central_charge_matching",
                name="central charge matching from encoded R-symmetry",
                description="Compare Tr R, Tr R^3, a, and c from the encoded R-symmetry.",
                factory=lambda claim: Obligation(
                    name="central charge matching from encoded R-symmetry",
                    description="Compare Tr R, Tr R^3, a, and c from the encoded R-symmetry.",
                    checker=lambda: central_charge_matching(claim),
                    checker_name="central_charge_matching",
                ),
            ),
            CheckSpec(
                key="operator_map_abelian_charges",
                name="operator map Abelian charge matching",
                description="Check U(1)_B and U(1)_R charges for standard SQCD operator maps.",
                factory=lambda claim: Obligation(
                    name="operator map Abelian charge matching",
                    description="Check U(1)_B and U(1)_R charges for standard SQCD operator maps.",
                    checker=lambda: minimal_operator_map_abelian_charges(claim),
                    checker_name="minimal_operator_map_abelian_charges",
                ),
            ),
            CheckSpec(
                key="operator_unitarity_bound",
                name="operator unitarity bound from encoded R-symmetry",
                description="Check R >= 2/3 for encoded gauge-invariant chiral operators.",
                factory=lambda claim: Obligation(
                    name="operator unitarity bound from encoded R-symmetry",
                    description="Check R >= 2/3 for encoded gauge-invariant chiral operators.",
                    checker=lambda: operator_unitarity_bound_check(claim),
                    checker_name="operator_unitarity_bound_check",
                ),
            ),
            CheckSpec(
                key="operator_map_nonabelian_flavor",
                name="operator map non-Abelian flavor matching",
                description="Check non-Abelian flavor representations of mapped operators.",
                applicable_duality_profiles=frozenset({"seiberg_sqcd"}),
                factory=lambda claim: Obligation(
                    name="operator map non-Abelian flavor matching",
                    description="Check non-Abelian flavor representations of mapped operators.",
                    checker=lambda: sqcd_operator_map_nonabelian_flavor_labels(claim),
                    checker_name="sqcd_operator_map_nonabelian_flavor_labels",
                ),
            ),
            CheckSpec(
                key="sqcd_magnetic_meson_f_term_lifting",
                name="SQCD magnetic meson F-term lifting",
                description="Check that encoded F-terms constrain magnetic q qtilde.",
                applicable_duality_profiles=frozenset({"seiberg_sqcd"}),
                factory=lambda claim: Obligation(
                    name="SQCD magnetic meson F-term lifting",
                    description="Check that encoded F-terms constrain magnetic q qtilde.",
                    checker=lambda: sqcd_magnetic_meson_f_term_lifting_check(claim),
                    checker_name="sqcd_magnetic_meson_f_term_lifting_check",
                ),
            ),
            CheckSpec(
                key="sqcd_mass_deformation",
                name="SQCD one-flavor mass deformation",
                description="Check the rank flow under one-flavor SQCD mass deformation.",
                applicable_duality_profiles=frozenset({"seiberg_sqcd"}),
                factory=lambda claim: Obligation(
                    name="SQCD one-flavor mass deformation",
                    description="Check the rank flow under one-flavor SQCD mass deformation.",
                    checker=lambda: sqcd_one_flavor_mass_deformation_check(claim),
                    checker_name="sqcd_one_flavor_mass_deformation_check",
                ),
            ),
            CheckSpec(
                key="sqcd_mesonic_flat_direction",
                name="SQCD mesonic flat-direction flow",
                description="Check rank flow along supported SQCD mesonic flat directions.",
                applicable_duality_profiles=frozenset({"seiberg_sqcd"}),
                factory=lambda claim: Obligation(
                    name="SQCD mesonic flat-direction flow",
                    description="Check rank flow along supported SQCD mesonic flat directions.",
                    checker=lambda: sqcd_mesonic_flat_direction_flow_check(claim),
                    checker_name="sqcd_mesonic_flat_direction_flow_check",
                ),
            ),
            CheckSpec(
                key="kutasov_meson_tower_completeness",
                name="Kutasov meson tower completeness",
                description="Check that the magnetic theory contains all k meson fields M0..M{k-1}.",
                applicable_duality_profiles=frozenset({"kutasov"}),
                factory=lambda claim: Obligation(
                    name="Kutasov meson tower completeness",
                    description="Check that the magnetic theory contains all k meson fields M0..M{k-1}.",
                    checker=lambda: kutasov_meson_tower_completeness_check(claim),
                    checker_name="kutasov_meson_tower_completeness_check",
                ),
            ),
            CheckSpec(
                key="bounded_chiral_ring_consistency",
                name="bounded chiral-ring consistency",
                description=(
                    "Compare two pure_quiver theories block-wise on bounded "
                    "cyclic-word quotient dimensions (Phase 2a, design doc sections 6/7)."
                ),
                applicable_kinds=frozenset({"pure_quiver"}),
                factory=lambda claim, prior: Obligation(
                    name="bounded chiral-ring consistency",
                    description=(
                        "Compare two pure_quiver theories block-wise on bounded "
                        "cyclic-word quotient dimensions (Phase 2a, design doc sections 6/7)."
                    ),
                    checker=lambda: bounded_chiral_ring_consistency_check(claim, prior),
                    checker_name="bounded_chiral_ring_consistency_check",
                ),
            ),
            CheckSpec(
                key="chiral_ring_metadata",
                name="chiral ring / F-term metadata",
                description="Compare encoded chiral-ring generators and relations, if present.",
                factory=lambda claim: Obligation(
                    name="chiral ring / F-term metadata",
                    description="Compare encoded chiral-ring generators and relations, if present.",
                    checker=lambda: chiral_ring_metadata_check(claim),
                    checker_name="chiral_ring_metadata_check",
                ),
            ),
            CheckSpec(
                key="moduli_space_metadata",
                name="moduli-space metadata",
                description="Compare encoded branch labels, dimensions, and constraints.",
                factory=lambda claim: Obligation(
                    name="moduli-space metadata",
                    description="Compare encoded branch labels, dimensions, and constraints.",
                    checker=lambda: moduli_space_metadata_check(claim),
                    checker_name="moduli_space_metadata_check",
                ),
            ),
            CheckSpec(
                key="conformal_manifold_metadata",
                name="conformal-manifold metadata",
                description="Compare encoded marginal-operator and current-multiplet metadata.",
                factory=lambda claim: Obligation(
                    name="conformal-manifold metadata",
                    description="Compare encoded marginal-operator and current-multiplet metadata.",
                    checker=lambda: conformal_manifold_metadata_check(claim),
                    checker_name="conformal_manifold_metadata_check",
                ),
            ),
            CheckSpec(
                key="generalized_symmetry_metadata",
                name="generalized-symmetry / defect metadata",
                description="Compare encoded 1-form symmetry, line-operator, and global-form data.",
                factory=lambda claim: Obligation(
                    name="generalized-symmetry / defect metadata",
                    description="Compare encoded 1-form symmetry, line-operator, and global-form data.",
                    checker=lambda: generalized_symmetry_metadata_check(claim),
                    checker_name="generalized_symmetry_metadata_check",
                ),
            ),
            CheckSpec(
                key="protected_quantity_hooks",
                name="protected quantity hooks",
                description="Compare encoded index, partition-function, or Hilbert-series data.",
                factory=lambda claim: Obligation(
                    name="protected quantity hooks",
                    description="Compare encoded index, partition-function, or Hilbert-series data.",
                    checker=lambda: protected_quantity_hooks_check(claim),
                    checker_name="protected_quantity_hooks_check",
                ),
            ),
            CheckSpec(
                key="index_matching",
                name="index matching",
                description="Check equality of protected indices in a supported expansion.",
                factory=lambda claim: Obligation(
                    name="index matching",
                    description="Check equality of protected indices in a supported expansion.",
                ),
            ),
            CheckSpec(
                key="deformation_checks",
                name="deformation checks",
                description="Check general masses, Higgsing, and other deformations.",
                factory=lambda claim: Obligation(
                    name="deformation checks",
                    description="Check general masses, Higgsing, and other deformations.",
                ),
            ),
        )
    )
