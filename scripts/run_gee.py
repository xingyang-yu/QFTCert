"""Run the frozen GEE analyses exactly as reported in the paper.

Two invocations of the frozen estimator (dualitycert.experiments.gee_analysis):
the two-model primary family and the MiniMax extension family, each written to
its canonical output directory. Invoke with the project venv:

    .venv/bin/python scripts/run_gee.py
"""

from __future__ import annotations

from pathlib import Path

from dualitycert.experiments.gee_analysis import analyze_confirmatory

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs/experiments/repair_d1/runs"
OUT = ROOT / "runs/experiments/repair_d1/confirmatory_analysis"


def main() -> None:
    analyze_confirmatory(
        runs_root=RUNS,
        models={"deepseek": "conf_deepseek", "qwen": "conf_qwen"},
        out_dir=OUT,
    )
    analyze_confirmatory(
        runs_root=RUNS,
        models={"minimax": "conf_minimax"},
        out_dir=OUT / "minimax_extension",
    )
    print(f"wrote confirmatory_analysis.json under {OUT} (primary + minimax_extension)")


if __name__ == "__main__":
    main()
