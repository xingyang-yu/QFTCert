from dualitycert.core.status import Status
from dualitycert.qft.dualities import build_seiberg_sqcd_claim
from dualitycert.qft.operators import (
    minimal_operator_map_abelian_charges,
    sqcd_operator_map_nonabelian_flavor_labels,
)


def test_correct_sqcd_operator_map_abelian_charges_pass():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5)

    result = minimal_operator_map_abelian_charges(claim)

    assert result.status == Status.CERTIFIED
    assert (
        result.details["meson"]["electric"]["U(1)_R"]
        == result.details["meson"]["magnetic"]["U(1)_R"]
    )
    assert (
        result.details["baryon"]["electric"]["U(1)_B"]
        == result.details["baryon"]["magnetic"]["U(1)_B"]
    )
    assert "non-Abelian flavor representation matching" in result.details["not_implemented"]


def test_wrong_meson_r_charge_fails_meson_operator_map():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5, magnetic_meson_r_charge=1)

    result = minimal_operator_map_abelian_charges(claim)

    assert result.status == Status.FAILED
    assert "meson has mismatched U(1)_R" in result.message


def test_wrong_magnetic_baryon_charge_fails_baryon_operator_map():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5, magnetic_q_b_charge=0)

    result = minimal_operator_map_abelian_charges(claim)

    assert result.status == Status.FAILED
    assert "baryon has mismatched U(1)_B" in result.message


def test_missing_meson_fails_meson_operator_map_clearly():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5, include_meson=False)

    result = minimal_operator_map_abelian_charges(claim)

    assert result.status == Status.FAILED
    assert "unknown field M" in result.message


def test_correct_sqcd_operator_map_nonabelian_flavor_labels_pass():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5)

    result = sqcd_operator_map_nonabelian_flavor_labels(claim)

    assert result.status == Status.CERTIFIED
    assert result.details["meson"]["electric"]["SU(Nf)_L"] == "fundamental"
    assert result.details["meson"]["electric"]["SU(Nf)_R"] == "antifundamental"
    assert (
        result.details["baryon"]["electric"]["SU(Nf)_L"]
        == result.details["baryon"]["magnetic"]["SU(Nf)_L"]
    )
    assert (
        result.details["antibaryon"]["electric"]["SU(Nf)_R"]
        == result.details["antibaryon"]["magnetic"]["SU(Nf)_R"]
    )


def test_wrong_magnetic_rank_fails_nonabelian_baryon_flavor_label():
    claim = build_seiberg_sqcd_claim(Nc=3, Nf=5, magnetic_color_rank=3)

    result = sqcd_operator_map_nonabelian_flavor_labels(claim)

    assert result.status == Status.FAILED
    assert "baryon has mismatched SU(Nf)_L label" in result.message
