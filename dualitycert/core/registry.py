"""Small registry for modular consistency checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping

from dualitycert.core.objects import DualityClaim
from dualitycert.core.obligations import Obligation
from dualitycert.core.theory_kind import FLAVORED_QUIVER, infer_claim_theory_kind


ObligationFactory = Callable[[DualityClaim], Obligation]


@dataclass(frozen=True)
class CheckSpec:
    """A named checker that can generate an obligation for a claim."""

    key: str
    name: str
    description: str
    factory: ObligationFactory
    # Allowlist of duality_profile values; None = applies to all profiles.
    applicable_duality_profiles: frozenset[str] | None = None
    # Allowlist of theory_kind values; None = applies to all non-flavored_quiver kinds.
    applicable_kinds: frozenset[str] | None = None
    # True = runs regardless of theory_kind (e.g., the classification check itself).
    always_run: bool = False

    def obligation_for(self, claim: DualityClaim) -> Obligation:
        return self.factory(claim)


class CheckRegistry:
    """Ordered collection of check specs."""

    def __init__(self, specs: Iterable[CheckSpec] = ()) -> None:
        self._specs: dict[str, CheckSpec] = {}
        for spec in specs:
            self.register(spec)

    def register(self, spec: CheckSpec) -> None:
        if spec.key in self._specs:
            raise ValueError(f"Duplicate check key: {spec.key}")
        self._specs[spec.key] = spec

    def keys(self) -> tuple[str, ...]:
        return tuple(self._specs)

    def specs(self) -> tuple[CheckSpec, ...]:
        return tuple(self._specs.values())

    def obligations_for(
        self,
        claim: DualityClaim,
        *,
        requested_keys: Iterable[str] | None = None,
    ) -> tuple[Obligation, ...]:
        theory_kind = infer_claim_theory_kind(claim)
        duality_profile = claim.metadata.get("duality_profile")

        if requested_keys is None:
            specs: list[CheckSpec] = []
            for s in self.specs():
                if s.always_run:
                    specs.append(s)
                    continue
                if theory_kind == FLAVORED_QUIVER:
                    continue
                if (
                    s.applicable_duality_profiles is not None
                    and duality_profile not in s.applicable_duality_profiles
                ):
                    continue
                if (
                    s.applicable_kinds is not None
                    and theory_kind not in s.applicable_kinds
                ):
                    continue
                specs.append(s)
        else:
            key_list = list(requested_keys)
            missing = [key for key in key_list if key not in self._specs]
            if missing:
                raise ValueError(f"Unknown check keys: {', '.join(missing)}")
            specs = [self._specs[key] for key in key_list]

        return tuple(spec.obligation_for(claim) for spec in specs)

    def as_dict(self) -> Mapping[str, CheckSpec]:
        return dict(self._specs)
