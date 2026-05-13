"""QFT-specific checkers and SQCD duality builders."""

from dualitycert.qft.anomalies import (
    compare_anomaly_tables,
    gauge_anomaly_cancellation,
    global_tHooft_anomaly_table,
)
from dualitycert.qft.dualities import (
    build_seiberg_sqcd_claim,
    evaluate_claim,
    generate_obligations,
)
from dualitycert.qft.susy import (
    superpotential_R_charge_equals_2,
    superpotential_consistency,
    superpotential_invariance,
)

__all__ = [
    "build_seiberg_sqcd_claim",
    "compare_anomaly_tables",
    "evaluate_claim",
    "gauge_anomaly_cancellation",
    "generate_obligations",
    "global_tHooft_anomaly_table",
    "superpotential_R_charge_equals_2",
    "superpotential_consistency",
    "superpotential_invariance",
]
