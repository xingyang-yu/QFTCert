"""Machine-readable SQCD-like claim loading.

The first loader intentionally supports JSON only to avoid dependency churn.
It is a thin adapter over the existing SQCD builder, not a general QFT schema.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

from dualitycert.core.objects import DualityClaim, SuperpotentialTerm
from dualitycert.qft.dualities import build_seiberg_sqcd_claim
from dualitycert.qft.kutasov import build_kutasov_claim


def load_claim_file(path: str | Path) -> DualityClaim:
    claim_path = Path(path)
    if claim_path.suffix.lower() != ".json":
        raise ValueError(
            "Only JSON claim files are supported in this dependency-light prototype."
        )
    with claim_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return build_claim_from_data(data)


def build_claim_from_data(data: Mapping[str, Any]) -> DualityClaim:
    duality_profile = data.get("duality_profile")
    if duality_profile == "kutasov":
        return _build_kutasov_claim_from_data(data)
    if duality_profile != "seiberg_sqcd":
        raise ValueError(f"Unsupported duality_profile: {duality_profile!r}")

    parameters = data.get("parameters", {})
    magnetic = data.get("magnetic", {})
    charges = magnetic.get("charges", {})
    superpotential = data.get("superpotential", {})

    claim = build_seiberg_sqcd_claim(
        Nc=int(parameters["Nc"]),
        Nf=int(parameters["Nf"]),
        magnetic_color_rank=_optional_int(magnetic.get("rank")),
        include_meson=bool(magnetic.get("include_meson", True)),
        include_magnetic_superpotential=bool(
            superpotential.get("include", True)
        ),
        magnetic_meson_r_charge=magnetic.get("meson_R_override"),
        magnetic_quark_r_charge=magnetic.get("quark_R_override"),
        magnetic_q_b_charge=charges.get("q_B_override"),
        magnetic_qtilde_b_charge=charges.get("qtilde_B_override"),
        claim_name=data.get("name"),
    )

    if "terms" in superpotential:
        claim = _replace_magnetic_superpotential(
            claim,
            superpotential_terms_from_lists(superpotential.get("terms", [])),
        )

    if "operator_map" in data:
        operator_map = data["operator_map"]
        if not isinstance(operator_map, Mapping):
            raise ValueError(
                "operator_map must be a JSON object mapping electric monomial "
                "strings to magnetic monomial strings."
            )
        # An explicit empty {} is honored as "the claim does not explicitly
        # assert any operator maps" and overrides any builder-provided default.
        # This is *not* a request to skip operator-map checking: the
        # SQCD-profile checker may still infer standard defaults from
        # duality_profile. A missing operator_map key preserves any
        # builder-provided default.
        claim = replace(
            claim,
            operator_map={str(k): str(v) for k, v in operator_map.items()},
        )

    metadata = dict(claim.metadata)
    metadata["source_schema"] = "sqcd_claim_json_v0"
    metadata.update(dict(data.get("metadata", {})))
    if "expected_outcome" in data:
        metadata["expected_outcome"] = data["expected_outcome"]
    for optional_key in (
        "global_symmetry_metadata",
        "operators",
        "chiral_ring",
        "moduli_space",
        "conformal_manifold",
        "generalized_symmetry",
        "protected_quantities",
        "deformations",
    ):
        if optional_key in data:
            metadata[optional_key] = data[optional_key]
    metadata["parameters"] = {
        **dict(metadata.get("parameters", {})),
        "requested_checks": list(data.get("requested_checks", [])),
    }
    return replace(claim, metadata=metadata)


def superpotential_terms_from_lists(terms: list[list[str]]) -> tuple[SuperpotentialTerm, ...]:
    parsed_terms = []
    for term in terms:
        counts = Counter(term)
        factors = tuple((field_name, power) for field_name, power in counts.items())
        parsed_terms.append(
            SuperpotentialTerm(
                factors=factors,
                label=" ".join(term),
            )
        )
    return tuple(parsed_terms)


def _replace_magnetic_superpotential(
    claim: DualityClaim,
    terms: tuple[SuperpotentialTerm, ...],
) -> DualityClaim:
    magnetic = replace(claim.magnetic_theory, superpotential_terms=terms)
    metadata = dict(claim.metadata)
    metadata["parameters"] = {
        **dict(metadata.get("parameters", {})),
        "superpotential_terms": [term.field_names for term in terms],
    }
    return replace(claim, magnetic_theory=magnetic, metadata=metadata)


def _build_kutasov_claim_from_data(data: Mapping[str, Any]) -> DualityClaim:
    parameters = data.get("parameters", {})
    magnetic = data.get("magnetic", {})

    claim = build_kutasov_claim(
        Nc=int(parameters["Nc"]),
        Nf=int(parameters["Nf"]),
        k=int(parameters["k"]),
        magnetic_color_rank=_optional_int(magnetic.get("rank")),
        claim_name=data.get("name"),
    )

    metadata = dict(claim.metadata)
    metadata["source_schema"] = "kutasov_claim_json_v0"
    metadata.update(dict(data.get("metadata", {})))
    if "expected_outcome" in data:
        metadata["expected_outcome"] = data["expected_outcome"]
    metadata["parameters"] = {
        **dict(metadata.get("parameters", {})),
        "requested_checks": list(data.get("requested_checks", [])),
    }
    return replace(claim, metadata=metadata)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)
