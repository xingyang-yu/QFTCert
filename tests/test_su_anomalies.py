from fractions import Fraction

from dualitycert.core.objects import Field, Theory
from dualitycert.groups.su import antifundamental, fundamental, su
from dualitycert.qft.anomalies import gauge_anomaly_cancellation
from dualitycert.core.status import Status


def test_vector_like_sqcd_electric_gauge_anomaly_cancels():
    nf = 5
    node = su(3)
    theory = Theory(
        name="Vector-like SQCD",
        gauge_nodes=(node,),
        global_symmetries=(su(nf, label="SU(Nf)_L", global_symmetry=True),),
        fields=(
            Field(
                name="Q",
                field_type="chiral multiplet",
                gauge_reps={node.label: fundamental()},
                global_reps={"SU(Nf)_L": fundamental()},
                r_charge=Fraction(2, 5),
            ),
            Field(
                name="Qtilde",
                field_type="chiral multiplet",
                gauge_reps={node.label: antifundamental()},
                global_reps={"SU(Nf)_L": fundamental()},
                r_charge=Fraction(2, 5),
            ),
        ),
    )

    result = gauge_anomaly_cancellation(theory)

    assert result.status == Status.CERTIFIED
    assert result.details[node.label]["total"] == 0
    assert result.details[node.label]["field_contributions"]["Q"] == nf
    assert result.details[node.label]["field_contributions"]["Qtilde"] == -nf
