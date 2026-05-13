"""Status labels used by certificates and obligations."""

from enum import Enum


class Status(str, Enum):
    """Conservative status vocabulary for consistency checks.

    `PROVED` is intentionally present only as a reserved label. The first
    prototype does not use it for duality claims.
    """

    PROVED = "PROVED"
    CERTIFIED = "CERTIFIED"
    SUPPORTED = "SUPPORTED"
    PLAUSIBLE = "PLAUSIBLE"
    FAILED = "FAILED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
