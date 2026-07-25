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
MM_ANALYSIS = (
    ROOT
    / "runs/experiments/repair_d1/confirmatory_analysis/minimax_extension/confirmatory_analysis.json"
)
OUT = ROOT / "paper/tables"
FIG_OUT = ROOT / "paper/figures"

MODELS = {"deepseek": "conf_deepseek", "qwen": "conf_qwen"}
MODEL_LABEL = {
    "deepseek": r"\textsc{deepseek-chat}",
    "qwen": r"\textsc{qwen-plus}",
    "minimax": r"\textsc{MiniMax-M2.5}",
}
# Ladder order of section 3 (E2 before E1), used for row ordering.
LADDER = {"E2_gr_vs_ss": 0, "E1_vf_vs_gr": 1, "E4_portfolio_vs_control": 2}
ARMS = [
    ("single_shot_repair", "single-shot"),
    ("generic_retry", "generic retry"),
    ("verifier_feedback", "verifier feedback"),
    ("vf_masked", "masked feedback"),
    ("best_of_n", "best-of-11"),
]
REPS = (1, 2, 3)

ENDPOINT_LABEL = {
    "E1_vf_vs_gr": r"E1 (\texttt{vf} $-$ \texttt{gr})",
    "E2_gr_vs_ss": r"E2 (\texttt{gr} $-$ \texttt{ss})",
    "E4_portfolio_vs_control": r"E4 (portfolio $-$ \texttt{best\_of\_n})",
    "E5_vf_vs_masked": r"E5 (\texttt{vf} $-$ \texttt{vf\_masked})",
    "E3_vf_at1_vs_gr_at1": r"E3 (\texttt{vf}@1 $-$ \texttt{gr}@1)",
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
            if r["endpoint"] == "E3_vf_at1_vs_gr_at1":
                ptxt = "--"  # E3: effect and interval only (protocol section 6)
            elif p is not None:
                ptxt = "$<10^{-4}$" if p < 5e-5 else f"{p:.4f}"
            else:
                ptxt = f"{r['p']:.3f}$^\\dagger$"
            out.append(
                f"{MODEL_LABEL[r['model']]} & {ENDPOINT_LABEL[r['endpoint']]} & "
                f"{rd:+.1f} & {ci} & {ptxt} \\\\"
            )
        return out

    primary_sorted = sorted(
        rep["primary_family_holm"],
        key=lambda r: (r["model"], LADDER.get(r["endpoint"], 9)),
    )
    lines += rows(primary_sorted, "primary")
    lines.append(r"\midrule")
    lines += rows(rep["secondary_e5_family_holm"], "e5")
    lines += rows(rep["secondary_e3_descriptive"], "e3")

    # Separately preregistered MiniMax-M2.5 extension (own Holm family).
    mm = json.loads(MM_ANALYSIS.read_text())
    lines += [
        r"\midrule",
        r"\multicolumn{5}{l}{\emph{preregistered \textsc{MiniMax-M2.5} extension"
        r" (separate three-hypothesis Holm family)}} \\",
        r"\midrule",
    ]
    mm_primary = sorted(
        mm["primary_family_holm"], key=lambda r: LADDER.get(r["endpoint"], 9)
    )
    lines += rows(mm_primary, "primary")
    # Extension E5 is secondary and unadjusted: report raw p with dagger.
    for r in mm["secondary_e5_family_holm"]:
        rd = 100 * r["rd"]
        ci = f"[{100*r['ci_lo']:+.1f}, {100*r['ci_hi']:+.1f}]"
        lines.append(
            f"{MODEL_LABEL[r['model']]} & {ENDPOINT_LABEL[r['endpoint']]} & "
            f"{rd:+.1f} & {ci} & {r['p']:.3f}$^\\dagger$ \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines)


def e4_forest_figure() -> str:
    """TikZ forest plot of the E4 risk differences (primary + extension)."""
    rep = json.loads(ANALYSIS.read_text())
    mm = json.loads(MM_ANALYSIS.read_text())

    def e4_row(report, model):
        for r in report["primary_family_holm"]:
            if r["endpoint"] == "E4_portfolio_vs_control" and r["model"] == model:
                return r
        raise KeyError(model)

    entries = [
        ("deepseek", e4_row(rep, "deepseek"), 2.0),
        ("qwen", e4_row(rep, "qwen"), 1.2),
        ("minimax", e4_row(mm, "minimax"), 0.3),
    ]
    # Per-replication sign check (asserted so prose claims stay honest).
    for name, r, _ in entries:
        signs = {v > 0 for v in r["per_rep_rd"]}
        assert len(signs) == 1, f"E4 per-rep signs mixed for {name}: {r['per_rep_rd']}"

    xmin, xmax, scale = -22.0, 24.0, 0.20  # pp range; cm per pp

    def x(pp: float) -> float:
        return (pp - xmin) * scale

    L = [r"\begin{tikzpicture}[font=\footnotesize]"]
    # Zero line and axis.
    L.append(
        rf"\draw[dashed, gray] ({x(0):.2f},-0.15) -- ({x(0):.2f},2.45);"
    )
    L.append(rf"\draw ({x(xmin):.2f},-0.25) -- ({x(xmax):.2f},-0.25);")
    for t in (-20, -10, 0, 10, 20):
        L.append(
            rf"\draw ({x(t):.2f},-0.25) -- ({x(t):.2f},-0.32)"
            rf" node[below] {{\scriptsize ${t:+d}$}};"
            if t
            else rf"\draw ({x(t):.2f},-0.25) -- ({x(t):.2f},-0.32)"
            rf" node[below] {{\scriptsize $0$}};"
        )
    L.append(
        rf"\node[below] at ({x(1):.2f},-0.62) {{\scriptsize E4: portfolio $-$ "
        rf"\texttt{{best\_of\_n}} (pp)}};"
    )
    # Direction annotations.
    L.append(
        rf"\node[anchor=east, gray] at ({x(-3):.2f},2.62) "
        r"{\scriptsize resampling higher $\leftarrow$};"
    )
    L.append(
        rf"\node[anchor=west, gray] at ({x(3):.2f},2.62) "
        r"{\scriptsize $\rightarrow$ portfolio higher};"
    )
    # Divider between primary family and extension.
    L.append(
        rf"\draw[dotted, gray] ({x(xmin):.2f},0.75) -- ({x(xmax):.2f},0.75)"
        r" node[pos=1, right] {\scriptsize extension};"
    )
    for name, r, y in entries:
        lo, hi, rd = 100 * r["ci_lo"], 100 * r["ci_hi"], 100 * r["rd"]
        L.append(rf"\node[anchor=east] at ({x(xmin)-0.15:.2f},{y}) {{{MODEL_LABEL[name]}}};")
        for pr in r["per_rep_rd"]:
            L.append(
                rf"\draw[gray!60] ({x(100*pr):.2f},{y}) circle (0.045);"
            )
        L.append(
            rf"\draw[thick] ({x(lo):.2f},{y}) -- ({x(hi):.2f},{y});"
        )
        L.append(rf"\draw[thick] ({x(lo):.2f},{y-0.07}) -- ({x(lo):.2f},{y+0.07});")
        L.append(rf"\draw[thick] ({x(hi):.2f},{y-0.07}) -- ({x(hi):.2f},{y+0.07});")
        L.append(rf"\fill ({x(rd):.2f},{y}) circle (0.06);")
    L.append(r"\end{tikzpicture}")
    return "\n".join(L)


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


def _manifest_classes() -> dict[str, str]:
    man = ROOT / "runs/experiments/repair_d1/fixtures/manifest.jsonl"
    out: dict[str, str] = {}
    for line in man.read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("repairable"):
            out[rec["fixture_id"]] = rec["perturbation_class"]
    return out


def _results(run_id: str) -> list[dict]:
    path = RUNS / run_id / "repair_results.jsonl"
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


CLASS_LABEL = {
    "drop_w_term": r"\texttt{drop\_w\_term}",
    "flip_w_sign": r"\texttt{flip\_w\_sign}",
    "r_charge_perturb": r"\texttt{r\_charge\_perturb}",
    "rank_perturb": r"\texttt{rank\_perturb}",
}
ALL_MODELS = {**MODELS, "minimax": "conf_minimax"}


def per_class_table() -> str:
    """Per-perturbation-class success counts for gr/vf (descriptive)."""
    classes = _manifest_classes()
    order = ["drop_w_term", "flip_w_sign", "r_charge_perturb", "rank_perturb"]
    counts: dict = {m: {a: {} for a in ("generic_retry", "verifier_feedback")} for m in ALL_MODELS}
    for m, prefix in ALL_MODELS.items():
        for arm in ("generic_retry", "verifier_feedback"):
            succ: dict[str, int] = {c: 0 for c in order}
            tot: dict[str, int] = {c: 0 for c in order}
            for r in REPS:
                for rec in _results(f"{prefix}_{arm}_r{r}"):
                    c = classes.get(rec["fixture_id"])
                    if c:
                        tot[c] += 1
                        succ[c] += 1 if rec.get("success") else 0
            counts[m][arm] = {c: (succ[c], tot[c]) for c in order}
    lines = [
        r"\begin{tabular}{lcccccc}",
        r"\toprule",
        r" & \multicolumn{2}{c}{\dscode{}} & \multicolumn{2}{c}{\qwcode{}}"
        r" & \multicolumn{2}{c}{\mmcode{} (ext.)} \\",
        r"class & \texttt{gr} & \texttt{vf} & \texttt{gr} & \texttt{vf}"
        r" & \texttt{gr} & \texttt{vf} \\",
        r"\midrule",
    ]
    for c in order:
        cells = []
        for m in ("deepseek", "qwen", "minimax"):
            for arm in ("generic_retry", "verifier_feedback"):
                s, t = counts[m][arm][c]
                cells.append(f"{s}/{t}")
        lines.append(f"{CLASS_LABEL[c]} & " + " & ".join(cells) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines)


def minimax_ext_table() -> str:
    """Full extension GEE table incl. E3 (descriptive)."""
    mm = json.loads(MM_ANALYSIS.read_text())
    lines = [
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        r"endpoint & RD (pp) & 95\% CI & $p$ \\",
        r"\midrule",
    ]

    def row(r, holm: bool):
        rd = 100 * r["rd"]
        ci = f"[{100*r['ci_lo']:+.1f}, {100*r['ci_hi']:+.1f}]"
        if r["endpoint"] == "E3_vf_at1_vs_gr_at1":
            ptxt = "--"  # E3: effect and interval only
        elif holm:
            p = r["holm_adjusted_p"]
            ptxt = "$<10^{-4}$" if p < 5e-5 else f"{p:.4f}"
        else:
            ptxt = f"{r['p']:.3f}$^\\dagger$"
        return f"{ENDPOINT_LABEL[r['endpoint']]} & {rd:+.1f} & {ci} & {ptxt} \\\\"

    for r in sorted(mm["primary_family_holm"], key=lambda x: LADDER.get(x["endpoint"], 9)):
        lines.append(row(r, holm=True))
    for r in mm["secondary_e5_family_holm"]:
        lines.append(row(r, holm=False))
    for r in mm["secondary_e3_descriptive"]:
        lines.append(row(r, holm=False))
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines)


def per_rep_minimax_table() -> str:
    """Extension per-replication success counts (plus invalid rates)."""
    lines = [
        r"\begin{tabular}{lcccc}",
        r"\toprule",
        r"policy & rep 1 & rep 2 & rep 3 & invalid \\",
        r"\midrule",
    ]
    for arm, label in ARMS:
        cells = []
        inv = tot = 0
        for r in REPS:
            recs = _results(f"conf_minimax_{arm}_r{r}")
            n_succ = sum(1 for x in recs if x.get("success"))
            cells.append(f"{n_succ}/{len(recs)}")
            inv += sum(1 for x in recs if x.get("invalid"))
            tot += len(recs)
        arm_tex = arm.replace("_", r"\_")
        lines.append(
            f"\\texttt{{{arm_tex}}} & " + " & ".join(cells) + f" & {100*inv/tot:.0f}\\% \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines)




def registry_table() -> str:
    """Full obligation registry with statuses on a committed positive fixture.

    Runs the verifier's evaluate_claim on the first positive fixture of the
    frozen manifest, so the table always reflects the code's actual registry.
    """
    import json as _json
    from pathlib import Path as _Path

    from dualitycert.core.objects import DualityClaim
    from dualitycert.experiments.config import VerifierConfig
    from dualitycert.experiments.single_shot import load_theory
    from dualitycert.experiments.verifier import _is_gauge_singlet_field
    from dualitycert.qft.dualities import evaluate_claim
    from dualitycert.qft.pure_quiver_json import pure_quiver_from_json

    root = _Path("runs/experiments/repair_d1/fixtures")
    recs = [_json.loads(l) for l in open(root / "manifest.jsonl") if l.strip()]
    pos = next(r for r in recs if not r.get("repairable"))
    ej = load_theory(root, pos["theory_a_path"])
    cj = load_theory(root, pos["theory_b_path"])
    cfg = VerifierConfig.from_dict(pos["verifier_config"])
    et = pure_quiver_from_json(dict(ej))
    ct = pure_quiver_from_json(dict(cj))
    grading = (
        "r_charge"
        if any(_is_gauge_singlet_field(f) for f in (*et.fields, *ct.fields))
        else "length"
    )
    meta = {
        "duality_profile": cfg.duality_profile,
        "bounded_chiral_ring": cfg.bounded_chiral_ring_metadata(grading=grading),
    }
    cert = evaluate_claim(
        DualityClaim(name="registry", electric_theory=et, magnetic_theory=ct, metadata=meta)
    )
    order = ["CERTIFIED", "NOT_APPLICABLE", "NOT_IMPLEMENTED", "UNKNOWN"]
    label = {
        "CERTIFIED": "certified",
        "NOT_APPLICABLE": "not applicable",
        "NOT_IMPLEMENTED": "not implemented",
        "UNKNOWN": "unknown",
    }
    lines = [r"\begin{tabular}{ll}", r"\toprule",
             r"obligation & status on a positive fixture \\", r"\midrule"]
    for i, status in enumerate(order):
        rows = [r for r in cert.obligation_results if r.status.value == status]
        for r in rows:
            lines.append(f"{r.name} & {label[status]} \\\\")
        if i < len(order) - 1:
            lines.append(r"\midrule")
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines)



def seeds_table() -> str:
    """Seed catalog: geometry, artifact label, ranks, dualized nodes, counts."""
    import re as _re

    GEOM = {
        "dp0_toric": r"$dP_0$ (cone over $\mathbb{P}^2$)",
        "dp1": r"$dP_1$",
        "dp2_phase1": r"$dP_2$",
        "f0_phase_ii": r"$F_0$ ($\mathbb{P}^1\times\mathbb{P}^1$)",
        "spp": r"SPP",
        "c3_z2z2": r"$\mathbb{C}^3/(\mathbb{Z}_2\times\mathbb{Z}_2)$",
    }
    rows: dict[str, dict] = {}
    for line in (ROOT / "runs/experiments/repair_d1/fixtures/manifest.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if not rec.get("repairable"):
            continue
        fam, N, node = _re.match(r"(.+?)_N(\d+)_d1_node(\d+)", rec["fixture_id"]).groups()
        e = rows.setdefault(fam, {"N": set(), "nodes": set(), "n": 0})
        e["N"].add(int(N)); e["nodes"].add(int(node)); e["n"] += 1
    order = ["dp0_toric", "dp1", "dp2_phase1", "f0_phase_ii", "spp", "c3_z2z2"]
    lines = [r"\begin{tabular}{llccc}", r"\toprule",
             r"geometry & artifact label & seed ranks $N$ & dualized nodes & fixtures \\",
             r"\midrule"]
    for fam in order:
        e = rows[fam]
        Ns = ", ".join(str(x) for x in sorted(e["N"]))
        nodes = ", ".join(str(x) for x in sorted(e["nodes"]))
        label = r"\texttt{" + fam.replace("_", r"\_") + "}"
        lines.append(f"{GEOM[fam]} & {label} & {Ns} & {nodes} & {e['n']} " + r"\\")
    lines += [r"\midrule",
              r"total & 14 family/rank/node cells & & & 145 \\",
              r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    FIG_OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "per_rep.tex").write_text(per_rep_table() + "\n")
    (OUT / "primary.tex").write_text(primary_table() + "\n")
    (OUT / "cost.tex").write_text(cost_table() + "\n")
    (OUT / "per_class.tex").write_text(per_class_table() + "\n")
    (OUT / "minimax_ext.tex").write_text(minimax_ext_table() + "\n")
    (OUT / "per_rep_minimax.tex").write_text(per_rep_minimax_table() + "\n")
    (FIG_OUT / "e4_forest.tex").write_text(e4_forest_figure() + "\n")
    (OUT / "registry.tex").write_text(registry_table() + "\n")
    (OUT / "seeds.tex").write_text(seeds_table() + "\n")
    print(f"wrote {len(list(OUT.glob('*.tex')))} tables to {OUT}")
    print(f"wrote e4_forest.tex to {FIG_OUT}")


if __name__ == "__main__":
    main()
