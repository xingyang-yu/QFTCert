"""Generate the paper's LaTeX tables directly from run artifacts.

Reads runs/experiments/repair_d1/runs/conf_* and
confirmatory_analysis/confirmatory_analysis.json; writes paper/tables/*.tex.
No number in the paper is typed by hand: rerun this script after any
analysis change. Invoke with the project venv:

    .venv/bin/python scripts/paper_tables.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs/experiments/repair_d1/runs"
ANALYSIS = ROOT / "runs/experiments/repair_d1/confirmatory_analysis/confirmatory_analysis.json"
OUT = ROOT / "paper/tables"

MODELS = {"deepseek": "conf_deepseek", "qwen": "conf_qwen"}
MODEL_LABEL = {"deepseek": r"\textsc{deepseek-chat}", "qwen": r"\textsc{qwen-plus}"}
ARMS = [
    ("single_shot_repair", "single-shot"),
    ("generic_retry", "generic retry"),
    ("verifier_feedback", "verifier feedback"),
    ("vf_masked", "masked feedback"),
    ("best_of_n", "best-of-11"),
]
REPS = (1, 2, 3)

ENDPOINT_LABEL = {
    "E1_vf_vs_gr": r"E1: feedback content (vf $-$ gr)",
    "E2_gr_vs_ss": r"E2: iteration+filter (gr $-$ ss)",
    "E4_portfolio_vs_control": r"E4: portfolio $-$ best-of-11",
    "E5_vf_vs_masked": r"E5: obligation identity (vf $-$ masked)",
    "E3_vf_at1_vs_gr_at1": r"E3: round-1 content (vf@1 $-$ gr@1)",
}


def _summary(run_id: str) -> dict:
    return json.loads((RUNS / run_id / "summary.json").read_text())


def per_rep_table() -> str:
    """Success counts per model x arm x rep (descriptive)."""
    lines = [
        r"\begin{tabular}{llccc}",
        r"\toprule",
        r"model & policy & rep 1 & rep 2 & rep 3 \\",
        r"\midrule",
    ]
    for mkey, prefix in MODELS.items():
        for i, (arm, label) in enumerate(ARMS):
            cells = []
            for r in REPS:
                s = _summary(f"{prefix}_{arm}_r{r}")
                n = s["n_fixtures"]
                cells.append(f"{s['n_success']}/{n}")
            head = MODEL_LABEL[mkey] if i == 0 else ""
            lines.append(f"{head} & {label} & " + " & ".join(cells) + r" \\")
        lines.append(r"\midrule" if mkey == "deepseek" else r"\bottomrule")
    lines.append(r"\end{tabular}")
    return "\n".join(lines)


def primary_table() -> str:
    """Frozen GEE endpoints with Holm-adjusted p-values."""
    rep = json.loads(ANALYSIS.read_text())
    lines = [
        r"\begin{tabular}{llrrr}",
        r"\toprule",
        r"model & endpoint & RD (pp) & 95\% CI & $p_{\mathrm{Holm}}$ \\",
        r"\midrule",
    ]

    def rows(results, ptag):
        out = []
        for r in results:
            rd = 100 * r["rd"]
            ci = (
                f"[{100*r['ci_lo']:+.1f}, {100*r['ci_hi']:+.1f}]"
                if r["ci_lo"] is not None
                else "--"
            )
            p = r.get("holm_adjusted_p")
            ptxt = f"{p:.4f}" if p is not None else f"{r['p']:.3f}$^\\dagger$"
            out.append(
                f"{MODEL_LABEL[r['model']]} & {ENDPOINT_LABEL[r['endpoint']]} & "
                f"{rd:+.1f} & {ci} & {ptxt} \\\\"
            )
        return out

    lines += rows(rep["primary_family_holm"], "primary")
    lines.append(r"\midrule")
    lines += rows(rep["secondary_e5_family_holm"], "e5")
    lines += rows(rep["secondary_e3_descriptive"], "e3")
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines)


def cost_table() -> str:
    """Total calls/tokens per model over the confirmatory campaigns."""
    lines = [
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        r"model & model calls & input tokens & output tokens \\",
        r"\midrule",
    ]
    for mkey, prefix in MODELS.items():
        calls = tin = tout = 0
        for arm, _ in ARMS:
            for r in REPS:
                s = _summary(f"{prefix}_{arm}_r{r}")
                calls += s.get("total_model_calls", 0)
                tin += s.get("total_input_tokens", 0)
                tout += s.get("total_output_tokens", 0)
        lines.append(
            f"{MODEL_LABEL[mkey]} & {calls:,} & {tin/1e6:.1f}M & {tout/1e6:.1f}M \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "per_rep.tex").write_text(per_rep_table() + "\n")
    (OUT / "primary.tex").write_text(primary_table() + "\n")
    (OUT / "cost.tex").write_text(cost_table() + "\n")
    print(f"wrote {len(list(OUT.glob('*.tex')))} tables to {OUT}")


if __name__ == "__main__":
    main()
