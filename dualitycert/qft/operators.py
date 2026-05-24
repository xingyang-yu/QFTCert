"""Minimal operator-map consistency checks for SQCD-like claims."""

from __future__ import annotations

from fractions import Fraction
from typing import Iterable, Mapping

from dualitycert.core.objects import CheckResult, DualityClaim, Field
from dualitycert.core.status import Status


BARYON_LABEL = "U(1)_B"
R_LABEL = "U(1)_R"


def minimal_operator_map_abelian_charges(claim: DualityClaim) -> CheckResult:
    """Check U(1)_B and U(1)_R charges of operator maps.

    For SQCD claims, the standard maps are checked by default:

    - meson: Q Qtilde <-> M
    - baryon: Q^Nc <-> q^Nmag
    - antibaryon: Qtilde^Nc <-> qtilde^Nmag

    Any user-supplied entries in `claim.operator_map` (electric monomial string
    -> magnetic monomial string) are also parsed and checked. Non-Abelian
    flavor representation matching is intentionally not checked here.
    """

    parameters = claim.metadata.get("parameters", {})
    nc = parameters.get("Nc")
    electric_fields = claim.electric_theory.field_map()
    magnetic_fields = claim.magnetic_theory.field_map()
    magnetic_rank = claim.magnetic_theory.gauge_nodes[0].N

    # SQCD default maps (meson M, baryons) only apply to Seiberg SQCD claims.
    # Other claim types (e.g. Kutasov) supply their own operator_map entries.
    default_maps: tuple[_OperatorMap, ...] = ()
    if nc is not None and claim.metadata.get("duality_profile") == "seiberg_sqcd":
        default_maps = (
            _OperatorMap("meson", (("Q", 1), ("Qtilde", 1)), (("M", 1),)),
            _OperatorMap("baryon", (("Q", int(nc)),), (("q", magnetic_rank),)),
            _OperatorMap(
                "antibaryon",
                (("Qtilde", int(nc)),),
                (("qtilde", magnetic_rank),),
            ),
        )

    claim_maps, parse_errors = _parse_user_operator_maps(claim.operator_map)

    # Merge: dedupe by (electric_factors, magnetic_factors). When the same map
    # appears in both default_maps and claim_maps, keep the SQCD-default's
    # canonical name ("meson"/"baryon"/...) for readable diagnostics. Entries
    # only in claim_maps keep their auto-generated names. claim.operator_map
    # is the source of truth for *what* is asserted; SQCD defaults only fill
    # in standard entries the claim did not assert.
    canonical: dict[tuple, _OperatorMap] = {}
    for m in default_maps:
        canonical[(m.electric_factors, m.magnetic_factors)] = m
    for m in claim_maps:
        key = (m.electric_factors, m.magnetic_factors)
        if key not in canonical:
            canonical[key] = m
    maps = tuple(canonical.values())

    # Computed via set difference so the count is correct even when the claim
    # has multiple syntactic spellings that parse to the same canonical key
    # (e.g., "Q Qtilde" and "Q^1 Qtilde").
    claim_keys = {(m.electric_factors, m.magnetic_factors) for m in claim_maps}
    default_keys = {(m.electric_factors, m.magnetic_factors) for m in default_maps}
    inferred_defaults_used = len(default_keys - claim_keys)

    if not maps:
        return CheckResult(
            status=Status.NOT_IMPLEMENTED,
            message=(
                "Minimal operator-map checker has no maps to check: SQCD "
                "metadata with Nc is missing and no claim operator_map is set."
            ),
            details={
                "implemented": ["U(1)_B", "U(1)_R"],
                "claim_operator_map_parse_errors": parse_errors,
            },
        )

    failures: list[str] = list(parse_errors)
    details: dict[str, dict] = {}
    for operator_map in maps:
        electric_charges = _operator_charges(
            operator_map.electric_factors,
            electric_fields,
        )
        magnetic_charges = _operator_charges(
            operator_map.magnetic_factors,
            magnetic_fields,
        )
        details[operator_map.name] = {
            "electric_operator": _format_factors(operator_map.electric_factors),
            "magnetic_operator": _format_factors(operator_map.magnetic_factors),
            "electric": electric_charges,
            "magnetic": magnetic_charges,
        }
        if "error" in electric_charges:
            failures.append(f"{operator_map.name}: {electric_charges['error']}")
            continue
        if "error" in magnetic_charges:
            failures.append(f"{operator_map.name}: {magnetic_charges['error']}")
            continue
        for label in (BARYON_LABEL, R_LABEL):
            if electric_charges[label] != magnetic_charges[label]:
                failures.append(
                    f"{operator_map.name} has mismatched {label}: "
                    f"electric={electric_charges[label]}, magnetic={magnetic_charges[label]}"
                )

    details["implemented_quantum_numbers"] = [BARYON_LABEL, R_LABEL]
    details["claim_operator_map_count"] = len(claim_maps)
    details["inferred_sqcd_default_count"] = inferred_defaults_used
    details["unique_maps_checked"] = len(maps)
    if parse_errors:
        details["claim_operator_map_parse_errors"] = parse_errors
    details["not_implemented"] = [
        "non-Abelian flavor representation matching",
        "chiral-ring relations",
        "operator normalization",
    ]

    if failures:
        return CheckResult(
            status=Status.FAILED,
            message="Minimal Abelian operator-map check failed: " + "; ".join(failures),
            details=details,
        )
    return CheckResult(
        status=Status.CERTIFIED,
        message="Standard SQCD operator maps match U(1)_B and U(1)_R charges.",
        details=details,
    )


def sqcd_operator_map_nonabelian_flavor_labels(claim: DualityClaim) -> CheckResult:
    """Check flavor-representation labels for standard SQCD operator maps.

    This checker is deliberately narrower than a full tensor-product engine.
    It recognizes the standard SQCD maps

    - Q Qtilde <-> M,
    - Q^Nc <-> q^Nmag,
    - Qtilde^Nc <-> qtilde^Nmag,

    and compares their SU(Nf)_L and SU(Nf)_R representation labels, including
    the epsilon-tensor equivalence Lambda^k F ~= Lambda^(N-k) anti-F.
    """

    if claim.metadata.get("duality_profile") != "seiberg_sqcd":
        return CheckResult(
            status=Status.NOT_APPLICABLE,
            message="Non-Abelian operator flavor-label checker is SQCD-specific.",
        )

    parameters = claim.metadata.get("parameters", {})
    nc = parameters.get("Nc")
    nf = parameters.get("Nf")
    if nc is None or nf is None:
        return CheckResult(
            status=Status.UNKNOWN,
            message="SQCD metadata is missing Nc or Nf.",
            details={"required": ["Nc", "Nf"]},
        )

    electric_fields = claim.electric_theory.field_map()
    magnetic_fields = claim.magnetic_theory.field_map()
    magnetic_rank = claim.magnetic_theory.gauge_nodes[0].N
    flavor_labels = ("SU(Nf)_L", "SU(Nf)_R")

    maps = (
        _OperatorMap("meson", (("Q", 1), ("Qtilde", 1)), (("M", 1),)),
        _OperatorMap("baryon", (("Q", int(nc)),), (("q", magnetic_rank),)),
        _OperatorMap(
            "antibaryon",
            (("Qtilde", int(nc)),),
            (("qtilde", magnetic_rank),),
        ),
    )

    failures: list[str] = []
    details: dict[str, dict] = {}
    for operator_map in maps:
        electric_labels = _operator_flavor_labels(
            operator_map.electric_factors,
            electric_fields,
            flavor_labels,
            int(nf),
        )
        magnetic_labels = _operator_flavor_labels(
            operator_map.magnetic_factors,
            magnetic_fields,
            flavor_labels,
            int(nf),
        )
        details[operator_map.name] = {
            "electric_operator": _format_factors(operator_map.electric_factors),
            "magnetic_operator": _format_factors(operator_map.magnetic_factors),
            "electric": electric_labels,
            "magnetic": magnetic_labels,
        }
        if "error" in electric_labels:
            failures.append(f"{operator_map.name}: {electric_labels['error']}")
            continue
        if "error" in magnetic_labels:
            failures.append(f"{operator_map.name}: {magnetic_labels['error']}")
            continue
        for label in flavor_labels:
            if electric_labels[label] != magnetic_labels[label]:
                failures.append(
                    f"{operator_map.name} has mismatched {label} label: "
                    f"electric={electric_labels[label]}, magnetic={magnetic_labels[label]}"
                )

    details["implemented"] = [
        "standard SQCD meson flavor labels",
        "standard SQCD baryon epsilon-tensor flavor labels",
    ]
    details["not_implemented"] = [
        "general tensor-product decomposition",
        "Young-tableau multiplicities",
        "operator normalization",
    ]

    if failures:
        return CheckResult(
            status=Status.FAILED,
            message="SQCD non-Abelian operator flavor-label check failed: "
            + "; ".join(failures),
            details=details,
        )
    return CheckResult(
        status=Status.CERTIFIED,
        message="Standard SQCD operator maps match supported non-Abelian flavor labels.",
        details=details,
    )


class _OperatorMap:
    def __init__(
        self,
        name: str,
        electric_factors: tuple[tuple[str, int], ...],
        magnetic_factors: tuple[tuple[str, int], ...],
    ) -> None:
        self.name = name
        self.electric_factors = electric_factors
        self.magnetic_factors = magnetic_factors


def _operator_charges(
    factors: Iterable[tuple[str, int]],
    fields: dict[str, Field],
) -> dict[str, Fraction | str]:
    charges = {BARYON_LABEL: Fraction(0, 1), R_LABEL: Fraction(0, 1)}
    for field_name, power in factors:
        field = fields.get(field_name)
        if field is None:
            return {"error": f"operator references unknown field {field_name}"}
        charges[BARYON_LABEL] += power * field.u1_charge(BARYON_LABEL, fermion=False)
        charges[R_LABEL] += power * field.r_charge
    return charges


def _operator_flavor_labels(
    factors: Iterable[tuple[str, int]],
    fields: dict[str, Field],
    flavor_labels: tuple[str, ...],
    group_rank: int,
) -> dict[str, str]:
    labels = {label: "singlet" for label in flavor_labels}
    for flavor_label in flavor_labels:
        nontrivial: list[tuple[str, int]] = []
        for field_name, power in factors:
            field = fields.get(field_name)
            if field is None:
                return {"error": f"operator references unknown field {field_name}"}
            rep = field.rep_for_global(flavor_label)
            if not rep.is_singlet:
                nontrivial.append((rep.name, power))
        labels[flavor_label] = _compose_supported_flavor_label(
            nontrivial,
            group_rank,
        )
    return labels


def _compose_supported_flavor_label(
    nontrivial: list[tuple[str, int]],
    group_rank: int,
) -> str:
    if not nontrivial:
        return "singlet"
    if len(nontrivial) == 1:
        rep_name, power = nontrivial[0]
        if power == 1:
            return rep_name
        return _canonical_antisymmetric_label(rep_name, power, group_rank)
    return "tensor_product(" + ",".join(
        f"{rep_name}^{power}" if power != 1 else rep_name
        for rep_name, power in nontrivial
    ) + ")"


def _canonical_antisymmetric_label(
    rep_name: str,
    power: int,
    group_rank: int,
) -> str:
    if power < 0:
        return "unsupported"
    if power == 0 or power == group_rank:
        return "singlet"
    if rep_name not in {"fundamental", "antifundamental"}:
        return f"antisym^{power}({rep_name})"
    if power > group_rank:
        return f"unsupported_antisym^{power}({rep_name})_for_SU({group_rank})"

    orientation = "F" if rep_name == "fundamental" else "anti-F"
    conjugate_orientation = "anti-F" if orientation == "F" else "F"
    direct = (power, orientation)
    epsilon_dual = (group_rank - power, conjugate_orientation)
    rank, canonical_orientation = min(
        direct,
        epsilon_dual,
        key=lambda item: (item[0], item[1]),
    )
    if rank == 1:
        return "fundamental" if canonical_orientation == "F" else "antifundamental"
    return f"antisym^{rank}({canonical_orientation})"


def _format_factors(factors: Iterable[tuple[str, int]]) -> str:
    pieces = []
    for field_name, power in factors:
        pieces.append(field_name if power == 1 else f"{field_name}^{power}")
    return " ".join(pieces)


def _parse_monomial_string(text: str) -> tuple[tuple[str, int], ...] | str:
    """Parse "Q Qtilde" or "Q^3 qtilde^2" into factor tuples; return error string on failure."""

    tokens = text.split()
    if not tokens:
        return f"empty operator monomial {text!r}"
    factors: list[tuple[str, int]] = []
    for token in tokens:
        if "^" in token:
            name, _, power_str = token.partition("^")
            name = name.strip()
            power_str = power_str.strip()
            if not name or not power_str:
                return f"malformed operator token {token!r}"
            try:
                power = int(power_str)
            except ValueError:
                return f"non-integer power in token {token!r}"
            if power < 1:
                return f"non-positive power in token {token!r}"
            factors.append((name, power))
        else:
            factors.append((token, 1))
    return tuple(factors)


def _parse_user_operator_maps(
    raw_map: object,
) -> tuple[tuple["_OperatorMap", ...], list[str]]:
    """Parse claim.operator_map entries into _OperatorMap objects.

    Accepts a mapping from electric monomial string to magnetic monomial string.
    Returns the parsed maps plus any parse-error messages.
    """

    if not raw_map or not isinstance(raw_map, Mapping):
        return (), []
    parsed: list[_OperatorMap] = []
    errors: list[str] = []
    for index, (electric_text, magnetic_text) in enumerate(raw_map.items()):
        electric = _parse_monomial_string(str(electric_text))
        magnetic = _parse_monomial_string(str(magnetic_text))
        if isinstance(electric, str):
            errors.append(f"claim_map[{electric_text!r}]: electric {electric}")
            continue
        if isinstance(magnetic, str):
            errors.append(f"claim_map[{electric_text!r}]: magnetic {magnetic}")
            continue
        parsed.append(
            _OperatorMap(
                name=f"claim_map[{index}]: {electric_text} <-> {magnetic_text}",
                electric_factors=electric,
                magnetic_factors=magnetic,
            )
        )
    return tuple(parsed), errors
