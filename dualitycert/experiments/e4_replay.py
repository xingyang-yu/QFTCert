"""E4 portfolio replay + scoring (paper/analysis_protocol.md, frozen).

The confirmatory design collects COMPLETE, mutually independent ss / gr /
vf-med outcomes per fixture-rep (they supply E1 and E2), then constructs the
E4 portfolio outcome by deterministic replay in the frozen order
ss -> gr -> vf-med: the replay stops at the first recorded final
certificate; an invalid output terminates only its arm; calls after the
stopping point are excluded from the DEPLOYED-policy accounting but stay in
the audit trail. The best-of-11 control is a separately executed policy
(arm "best_of_n") compared pairwise under the same 11-model-call cap.

Because component calls are independent and later arms cannot affect
earlier outcomes, the replay preserves the success distribution of the
executable stop-first policy while retaining complete E1/E2 data
(convergence-loop Round 4, verbatim rationale).
"""

from __future__ import annotations

import json
from math import comb
from pathlib import Path
from typing import Any, Mapping

from dualitycert.experiments.repair import round_model_called

PORTFOLIO_ORDER = ("ss", "gr", "vf")

__all__ = ["load_run_records", "mcnemar_exact", "replay_fixture", "score_e4"]


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value from discordant counts (b, c)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = 2.0 * sum(comb(n, i) for i in range(k + 1)) / 2.0**n
    return min(p, 1.0)


def load_run_records(run_dir: Path | str) -> dict[str, dict[str, Any]]:
    """fixture_id -> record dict from a run dir's repair_results.jsonl."""
    path = Path(run_dir) / "repair_results.jsonl"
    records: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        fid = rec["fixture_id"]
        if fid in records:
            raise ValueError(f"duplicate fixture_id {fid!r} in {path}")
        records[fid] = rec
    if not records:
        raise ValueError(f"no records in {path}")
    return records


def _record_costs(rec: Mapping[str, Any]) -> tuple[int, int, int, int]:
    """(model_calls, verifier_calls, input_tokens, output_tokens) of a record."""
    model_calls = sum(1 for rd in rec.get("rounds", []) if round_model_called(rd))
    in_tok = sum(rd.get("input_tokens") or 0 for rd in rec.get("rounds", []))
    out_tok = sum(rd.get("output_tokens") or 0 for rd in rec.get("rounds", []))
    return model_calls, int(rec.get("verifier_calls", 0)), in_tok, out_tok


def replay_fixture(
    components: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Deterministic stop-first replay over one fixture's arm records.

    `components` maps the arm keys "ss", "gr", "vf" to that fixture's
    records. Deployed accounting sums each arm's own calls up to and
    including the arm where the first final certificate was recorded;
    later arms' calls are excluded (they exist only because collection is
    complete for E1/E2).
    """
    deployed_model_calls = 0
    deployed_verifier_calls = 0
    deployed_input_tokens = 0
    deployed_output_tokens = 0
    stopped_at: str | None = None
    for key in PORTFOLIO_ORDER:
        rec = components[key]
        mc, vc, it, ot = _record_costs(rec)
        deployed_model_calls += mc
        deployed_verifier_calls += vc
        deployed_input_tokens += it
        deployed_output_tokens += ot
        if rec.get("success"):
            stopped_at = key
            break
    return {
        "portfolio_success": stopped_at is not None,
        "stopped_at_arm": stopped_at,
        "deployed_model_calls": deployed_model_calls,
        "deployed_verifier_calls": deployed_verifier_calls,
        "deployed_input_tokens": deployed_input_tokens,
        "deployed_output_tokens": deployed_output_tokens,
        "component_success": {k: bool(components[k].get("success")) for k in PORTFOLIO_ORDER},
    }


def score_e4(
    *,
    ss_dir: Path | str,
    gr_dir: Path | str,
    vf_dir: Path | str,
    control_dir: Path | str | None = None,
    out_dir: Path | str,
) -> dict[str, Any]:
    """Replay the E4 portfolio over three component runs; write artefacts.

    Writes e4_replay.jsonl (per fixture) and e4_summary.json under out_dir.
    With a control run (arm best_of_n), adds the paired comparison and the
    exact McNemar p-value.
    """
    runs = {
        "ss": load_run_records(ss_dir),
        "gr": load_run_records(gr_dir),
        "vf": load_run_records(vf_dir),
    }
    ids = set(runs["ss"])
    for key in ("gr", "vf"):
        if set(runs[key]) != ids:
            missing = ids ^ set(runs[key])
            raise ValueError(
                f"fixture sets differ between ss and {key} "
                f"(symmetric difference {sorted(missing)[:5]}...)"
            )
    control = load_run_records(control_dir) if control_dir else None
    if control is not None and set(control) != ids:
        raise ValueError("control fixture set differs from the component runs")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    stopped_counts: dict[str, int] = {k: 0 for k in PORTFOLIO_ORDER}
    n_success = 0
    totals = {
        "deployed_model_calls": 0,
        "deployed_verifier_calls": 0,
        "deployed_input_tokens": 0,
        "deployed_output_tokens": 0,
    }
    paired = {"both": 0, "portfolio_only": 0, "control_only": 0, "neither": 0}
    control_success = 0
    control_costs = [0, 0, 0, 0]

    for fid in sorted(ids):
        row = {"fixture_id": fid}
        row.update(replay_fixture({k: runs[k][fid] for k in PORTFOLIO_ORDER}))
        if row["portfolio_success"]:
            n_success += 1
            stopped_counts[row["stopped_at_arm"]] += 1
        for key in totals:
            totals[key] += row[key]
        if control is not None:
            c_rec = control[fid]
            c_succ = bool(c_rec.get("success"))
            row["control_success"] = c_succ
            control_success += c_succ
            for i, v in enumerate(_record_costs(c_rec)):
                control_costs[i] += v
            p, c = row["portfolio_success"], c_succ
            paired[
                "both" if p and c else
                "portfolio_only" if p else
                "control_only" if c else
                "neither"
            ] += 1
        rows.append(row)

    n = len(ids)
    summary: dict[str, Any] = {
        "n_fixtures": n,
        "portfolio_n_success": n_success,
        "portfolio_success_rate": n_success / n,
        "portfolio_stopped_at_arm_counts": stopped_counts,
        **{f"portfolio_{k}": v for k, v in totals.items()},
        "component_runs": {
            "ss": str(ss_dir), "gr": str(gr_dir), "vf": str(vf_dir),
        },
    }
    if control is not None:
        summary.update(
            {
                "control_run": str(control_dir),
                "control_n_success": control_success,
                "control_success_rate": control_success / n,
                "control_model_calls": control_costs[0],
                "control_verifier_calls": control_costs[1],
                "control_input_tokens": control_costs[2],
                "control_output_tokens": control_costs[3],
                "paired": paired,
                "mcnemar_exact_p": mcnemar_exact(
                    paired["portfolio_only"], paired["control_only"]
                ),
            }
        )

    with (out / "e4_replay.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False))
            fh.write("\n")
    (out / "e4_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary
