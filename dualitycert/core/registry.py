"""Small registry for modular consistency checks."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping

from dualitycert.core.objects import DualityClaim
from dualitycert.core.obligations import Obligation, ObligationResult
from dualitycert.core.theory_kind import FLAVORED_QUIVER, infer_claim_theory_kind


# Factories may take just the claim, or the claim plus an accumulator of
# prior obligation results (option A from Phase 2a design doc §14 step 4).
# The registry uses `inspect.signature` to dispatch automatically so existing
# 1-arg factories do not need to change.
ObligationFactory = Callable[..., Obligation]


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

    def obligation_for(
        self,
        claim: DualityClaim,
        prior_results: Mapping[str, ObligationResult] | None = None,
    ) -> Obligation:
        """Invoke the registered factory.

        Factories accept either `(claim,)` (legacy) or
        `(claim, prior_results)` (opt-in via option A). Arity is detected
        once per call via `inspect.signature` so existing factories work
        unchanged; new factories that need upstream `ObligationResult`s
        just take a second argument.
        """

        if prior_results is None:
            prior_results = {}
        parameters = inspect.signature(self.factory).parameters
        if len(parameters) >= 2:
            return self.factory(claim, prior_results)
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

    def applicable_specs(
        self,
        claim: DualityClaim,
        *,
        requested_keys: Iterable[str] | None = None,
    ) -> tuple[CheckSpec, ...]:
        """Return the filtered, ordered specs that apply to `claim`.

        Filtering rules (mirrors the historical `obligations_for` logic):
          - `always_run` specs always included;
          - FLAVORED_QUIVER claims skip every non-`always_run` spec
            (OUT_OF_SCOPE path);
          - `applicable_duality_profiles` and `applicable_kinds` allowlists
            are honoured.
        """

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
            return tuple(specs)

        key_list = list(requested_keys)
        missing = [key for key in key_list if key not in self._specs]
        if missing:
            raise ValueError(f"Unknown check keys: {', '.join(missing)}")
        return tuple(self._specs[key] for key in key_list)

    def obligations_for(
        self,
        claim: DualityClaim,
        *,
        requested_keys: Iterable[str] | None = None,
    ) -> tuple[Obligation, ...]:
        """Legacy: build all applicable obligations with no upstream context.

        New code that needs upstream `ObligationResult`s should iterate
        `applicable_specs` and call `spec.obligation_for(claim, prior_results)`
        per spec — that is what `evaluate_claim` does.
        """

        specs = self.applicable_specs(claim, requested_keys=requested_keys)
        return tuple(spec.obligation_for(claim) for spec in specs)

    def as_dict(self) -> Mapping[str, CheckSpec]:
        return dict(self._specs)
