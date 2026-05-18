"""Small registry for modular consistency checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Mapping

from dualitycert.core.objects import DualityClaim
from dualitycert.core.obligations import Obligation


ObligationFactory = Callable[[DualityClaim], Obligation]


@dataclass(frozen=True)
class CheckSpec:
    """A named checker that can generate an obligation for a claim."""

    key: str
    name: str
    description: str
    factory: ObligationFactory
    applicable_claim_types: frozenset[str] | None = None

    def obligation_for(self, claim: DualityClaim) -> Obligation:
        return self.factory(claim)


class CheckRegistry:
    """Ordered collection of check specs.

    The registry keeps QFTCert from hard-coding one large duality-specific
    checklist. Individual physics modules can register small, auditable
    obligation factories.
    """

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
        claim_type = claim.metadata.get("claim_type")
        if requested_keys is None:
            specs = tuple(
                s for s in self.specs()
                if s.applicable_claim_types is None
                or claim_type in s.applicable_claim_types
            )
        else:
            missing = [key for key in requested_keys if key not in self._specs]
            if missing:
                raise ValueError(f"Unknown check keys: {', '.join(missing)}")
            specs = tuple(self._specs[key] for key in requested_keys)
        return tuple(spec.obligation_for(claim) for spec in specs)

    def as_dict(self) -> Mapping[str, CheckSpec]:
        return dict(self._specs)
