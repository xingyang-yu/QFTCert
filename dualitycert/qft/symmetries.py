"""Global-symmetry metadata and label consistency checks."""

from __future__ import annotations

from dualitycert.core.objects import CheckResult, DualityClaim, GlobalSymmetry
from dualitycert.core.status import Status


def global_symmetry_matching(claim: DualityClaim) -> CheckResult:
    """Check represented continuous global symmetry factors.

    This is a label-and-metadata check, not a derivation of the full global
    symmetry group. It verifies that each encoded electric continuous global
    symmetry has a compatible magnetic factor under the symmetry map. Discrete
    symmetries, quotient/global-form data, and charge-normalization metadata
    are reported when encoded and otherwise marked as not checked.
    """

    electric = claim.electric_theory.global_symmetry_map()
    magnetic = claim.magnetic_theory.global_symmetry_map()
    failures: list[str] = []
    checked: dict[str, dict[str, str | int | None]] = {}

    for electric_label, electric_symmetry in electric.items():
        magnetic_label = claim.symmetry_map.magnetic_label(electric_label)
        magnetic_symmetry = magnetic.get(magnetic_label)
        if magnetic_symmetry is None:
            failures.append(
                f"{electric_label} maps to missing magnetic symmetry {magnetic_label}"
            )
            continue
        mismatch = _symmetry_mismatch(electric_symmetry, magnetic_symmetry)
        checked[electric_label] = {
            "magnetic_label": magnetic_label,
            "electric_kind": electric_symmetry.kind,
            "magnetic_kind": magnetic_symmetry.kind,
            "electric_N": electric_symmetry.N,
            "magnetic_N": magnetic_symmetry.N,
        }
        if mismatch:
            failures.append(f"{electric_label}->{magnetic_label}: {mismatch}")

    expected_magnetic = {
        claim.symmetry_map.magnetic_label(label) for label in electric
    }
    unexpected = sorted(set(magnetic) - expected_magnetic)
    for label in unexpected:
        failures.append(f"unexpected represented magnetic global symmetry {label}")

    metadata = claim.metadata.get("global_symmetry_metadata", {})
    details = {
        "continuous_factors": checked,
        "unexpected_magnetic_factors": unexpected,
        "encoded_metadata": metadata,
        "scaffold_only": [
            "discrete symmetries",
            "charge-normalization equivalence classes",
            "global-form or quotient data",
        ],
    }

    warnings = []
    if not metadata:
        warnings.append(
            "No discrete/global-form/charge-normalization metadata was encoded; "
            "only represented continuous factor labels were checked."
        )

    if failures:
        return CheckResult(
            status=Status.FAILED,
            message="Global symmetry matching failed: " + "; ".join(failures),
            details=details,
            warnings=tuple(warnings),
        )
    return CheckResult(
        status=Status.CERTIFIED,
        message="Represented continuous global symmetry factors match under the symmetry map.",
        details=details,
        warnings=tuple(warnings),
    )


def _symmetry_mismatch(
    electric_symmetry: GlobalSymmetry,
    magnetic_symmetry: GlobalSymmetry,
) -> str | None:
    if electric_symmetry.kind != magnetic_symmetry.kind:
        return f"kind mismatch {electric_symmetry.kind} != {magnetic_symmetry.kind}"
    if electric_symmetry.N != magnetic_symmetry.N:
        return f"rank/size mismatch {electric_symmetry.N} != {magnetic_symmetry.N}"
    return None
