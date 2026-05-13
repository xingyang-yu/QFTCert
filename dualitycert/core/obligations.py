"""Obligation data structures and execution helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from dualitycert.core.objects import CheckResult
from dualitycert.core.status import Status


Checker = Callable[[], CheckResult]


@dataclass(frozen=True)
class ObligationResult:
    name: str
    description: str
    status: Status
    message: str
    details: dict = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return self.status == Status.CERTIFIED


@dataclass(frozen=True)
class Obligation:
    name: str
    description: str
    checker: Checker | None = None
    status: Status = Status.NOT_IMPLEMENTED

    def run(self) -> ObligationResult:
        if self.checker is None:
            return ObligationResult(
                name=self.name,
                description=self.description,
                status=Status.NOT_IMPLEMENTED,
                message="No checker is implemented for this obligation.",
            )
        result = self.checker()
        return ObligationResult(
            name=self.name,
            description=self.description,
            status=result.status,
            message=result.message,
            details=dict(result.details),
            warnings=result.warnings,
        )
