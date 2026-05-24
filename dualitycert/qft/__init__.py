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
from dualitycert.qft.kutasov import (
    build_kutasov_claim,
    kutasov_meson_tower_completeness_check,
)
from dualitycert.qft.operators import minimal_operator_map_abelian_charges
from dualitycert.qft.claims import build_claim_from_data, load_claim_file
from dualitycert.qft.critic import (
    build_critic_report,
    build_repair_prompt,
)
from dualitycert.qft.susy import (
    superpotential_R_charge_equals_2,
    superpotential_consistency,
    superpotential_invariance,
)

__all__ = [
    "build_kutasov_claim",
    "build_seiberg_sqcd_claim",
    "build_claim_from_data",
    "build_critic_report",
    "build_repair_prompt",
    "compare_anomaly_tables",
    "evaluate_claim",
    "gauge_anomaly_cancellation",
    "generate_obligations",
    "global_tHooft_anomaly_table",
    "kutasov_meson_tower_completeness_check",
    "load_claim_file",
    "minimal_operator_map_abelian_charges",
    "superpotential_R_charge_equals_2",
    "superpotential_consistency",
    "superpotential_invariance",
]
