"""Metadata-level scaffold checks for harder QFT consistency obligations."""

from __future__ import annotations

from typing import Any

from dualitycert.core.objects import CheckResult, DualityClaim
from dualitycert.core.status import Status


def chiral_ring_metadata_check(claim: DualityClaim) -> CheckResult:
    """Compare encoded chiral-ring generators and relations, if present.

    This is a metadata scaffold. It does not compute a chiral ring from a
    superpotential or prove equivalence of polynomial ideals.
    """

    return _compare_optional_metadata(
        claim,
        key="chiral_ring",
        label="chiral-ring metadata",
        missing_message=(
            "No chiral-ring metadata is encoded; F-term ideals, quantum constraints, "
            "flipped operators, and truncations were not checked."
        ),
    )


def moduli_space_metadata_check(claim: DualityClaim) -> CheckResult:
    """Compare encoded moduli-space branch metadata, if present.

    Supported metadata can include branch labels, dimensions, coordinates,
    generators, and constraints. This does not prove moduli-space isomorphism.
    """

    return _compare_optional_metadata(
        claim,
        key="moduli_space",
        label="moduli-space metadata",
        missing_message=(
            "No moduli-space metadata is encoded; branch dimensions, generators, "
            "constraints, and Higgs/baryonic/mixed branch data were not checked."
        ),
    )


def conformal_manifold_metadata_check(claim: DualityClaim) -> CheckResult:
    """Compare encoded conformal-manifold metadata, if present.

    The intended metadata includes marginal operators, redundant currents,
    generic preserved symmetry, and a claimed conformal-manifold dimension.
    """

    return _compare_optional_metadata(
        claim,
        key="conformal_manifold",
        label="conformal-manifold metadata",
        missing_message=(
            "No conformal-manifold metadata is encoded; marginal operators, "
            "redundant currents, and conformal-manifold dimension were not checked."
        ),
    )


def generalized_symmetry_metadata_check(claim: DualityClaim) -> CheckResult:
    """Compare encoded generalized-symmetry and defect metadata, if present.

    This scaffold can carry 1-form symmetries, line-operator lattices, global
    form, discrete theta data, and mixed 0-form/1-form anomaly metadata.
    """

    return _compare_optional_metadata(
        claim,
        key="generalized_symmetry",
        label="generalized-symmetry metadata",
        missing_message=(
            "No generalized-symmetry metadata is encoded; 1-form symmetries, "
            "line operators, global-form data, and mixed higher-form anomalies "
            "were not checked."
        ),
    )


def protected_quantity_hooks_check(claim: DualityClaim) -> CheckResult:
    """Compare encoded protected quantities or report available hook status.

    The hook is intentionally lightweight. If explicit electric/magnetic data
    is provided, it is compared exactly; otherwise the checker reports UNKNOWN.
    Future integrations can attach superconformal index, lens-space index,
    twisted index, Hilbert series, or other protected-quantity data here.
    """

    return _compare_optional_metadata(
        claim,
        key="protected_quantities",
        label="protected-quantity metadata",
        missing_message=(
            "No protected-quantity data is encoded; index, partition-function, "
            "and Hilbert-series hooks are available only as metadata interfaces."
        ),
    )


def _compare_optional_metadata(
    claim: DualityClaim,
    *,
    key: str,
    label: str,
    missing_message: str,
) -> CheckResult:
    data = claim.metadata.get(key)
    if data is None:
        return CheckResult(
            status=Status.UNKNOWN,
            message=missing_message,
            details={"metadata_key": key},
        )

    comparisons = _extract_comparisons(data)
    if not comparisons:
        return CheckResult(
            status=Status.UNKNOWN,
            message=(
                f"{label} is present but does not contain comparable electric/magnetic "
                "entries."
            ),
            details={"metadata_key": key, "encoded": data},
        )

    mismatches = [
        name
        for name, electric_value, magnetic_value in comparisons
        if electric_value != magnetic_value
    ]
    details = {
        "metadata_key": key,
        "comparisons": [
            {
                "name": name,
                "electric": electric_value,
                "magnetic": magnetic_value,
            }
            for name, electric_value, magnetic_value in comparisons
        ],
    }
    if mismatches:
        return CheckResult(
            status=Status.FAILED,
            message=f"{label} mismatch: " + ", ".join(mismatches),
            details=details,
        )
    return CheckResult(
        status=Status.CERTIFIED,
        message=f"Encoded {label} entries match exactly.",
        details=details,
    )


def _extract_comparisons(data: Any) -> list[tuple[str, Any, Any]]:
    if isinstance(data, dict):
        if "electric" in data and "magnetic" in data:
            return [("metadata", data["electric"], data["magnetic"])]
        comparisons = []
        for name, value in data.items():
            if isinstance(value, dict) and "electric" in value and "magnetic" in value:
                comparisons.append((str(name), value["electric"], value["magnetic"]))
        return comparisons
    if isinstance(data, list):
        comparisons = []
        for index, value in enumerate(data):
            if isinstance(value, dict) and "electric" in value and "magnetic" in value:
                comparisons.append(
                    (str(value.get("name", f"entry_{index}")), value["electric"], value["magnetic"])
                )
        return comparisons
    return []
