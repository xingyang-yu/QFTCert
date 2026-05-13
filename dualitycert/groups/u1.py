"""U(1) global symmetry helpers."""

from dualitycert.core.objects import GlobalSymmetry


def u1(label: str) -> GlobalSymmetry:
    return GlobalSymmetry("U1", label=label)


def u1_r(label: str = "U(1)_R") -> GlobalSymmetry:
    return GlobalSymmetry("U1_R", label=label)
