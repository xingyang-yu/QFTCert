"""Verify the released depth-1 confirmatory artifacts against their frozen hashes.

Independent integrity check for the artifact set promised by the paper's
section 6 (artifact statement). Verifies, from the repository alone:

  1. paper/execution_manifest.json: config and fixture-manifest SHA-256,
     and the frozen prompt/schema hashes against the code in
     dualitycert/experiments/repair.py (dicts are hashed as
     json.dumps(obj, sort_keys=True); strings as raw UTF-8).
  2. The frozen benchmark: manifest rows, theory files on disk, attrition
     disjointness, and the 145-fixture runnable set (159 rows minus the 14
     CERTIFIED positive controls).
  3. Campaign structure: all 57 conf_* run directories with their required
     files; every arm run covers exactly the 145 runnable fixtures once.
  4. The MiniMax contamination-audit trail
     (runs/experiments/repair_d1/quarantine_preclean_20260721/): quarantined
     originals match their recorded hashes; each recorded filtered state is
     reproduced by removing exactly the rows in contaminated_ids.json from
     the quarantined original; live files are byte-identical to the original
     where no filtering happened, and otherwise contain only original rows
     plus reruns of the removed fixture ids; no live row matches the frozen
     contamination predicate (predicate.txt).

Not checked here: manifest final_theory_hash values (internal canonical-form
hashes, not file digests) and the GEE statistics themselves (regenerate via
scripts/paper_tables.py and the analysis pipeline).

Run with the project venv, from any directory:

    .venv/bin/python scripts/verify_release_artifacts.py
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D1 = ROOT / "runs/experiments/repair_d1"
RUNS = D1 / "runs"
FIXTURES = D1 / "fixtures"
QUARANTINE = D1 / "quarantine_preclean_20260721"
ANALYSIS_DIR = D1 / "confirmatory_analysis"
EXEC_MANIFEST = ROOT / "paper/execution_manifest.json"

MODELS = ("deepseek", "qwen", "minimax")
ARMS = ("single_shot_repair", "generic_retry", "verifier_feedback", "best_of_n", "vf_masked")
REPS = (1, 2, 3)
N_RUNNABLE = 145

# Mirrors of the two feedback strings built inline by build_feedback() in
# dualitycert/experiments/repair.py; the manifest froze their hashes.
GENERIC_RETRY_FEEDBACK = (
    "The candidate failed verification. Try a different edit to make "
    "Theory B a valid dual of Theory A."
)
MASKED_BULLET_TEMPLATE = "  - obligation-{i} (category: category-{i})"

_failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    tag = "PASS" if ok else "FAIL"
    line = f"[{tag}] {name}" + (f": {detail}" if detail else "")
    print(line)
    if not ok:
        _failures.append(name)


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(p: Path) -> str:
    return sha_bytes(p.read_bytes())


def jsonl_lines(p: Path) -> list[bytes]:
    return p.read_bytes().splitlines(keepends=True)


def fixture_ids(lines: list[bytes]) -> list[str]:
    return [json.loads(ln)["fixture_id"] for ln in lines]


def check_execution_manifest() -> None:
    m = json.loads(EXEC_MANIFEST.read_text())
    for rel, expected in m["config_sha256"].items():
        p = ROOT / rel
        check(f"config sha256 {rel}", p.exists() and sha_file(p) == expected)
    check(
        "fixture manifest sha256",
        sha_file(FIXTURES / "manifest.jsonl") == m["fixture_manifest_sha256"],
    )

    sys.path.insert(0, str(ROOT))
    from dualitycert.experiments import repair as repair_mod

    def prompt_hash(obj: object) -> str:
        if isinstance(obj, str):
            return sha_bytes(obj.encode())
        return sha_bytes(json.dumps(obj, sort_keys=True).encode())

    recorded = m["prompt_hashes_sha256"]
    for name in (
        "REPAIR_TOOL_NAME",
        "REPAIR_SYSTEM_PROMPT",
        "REPAIR_SYSTEM_PROMPT_FULL",
        "REPAIR_DECISION_SCHEMA",
        "REPAIR_DECISION_SCHEMA_FULL",
    ):
        check(
            f"prompt hash {name}",
            prompt_hash(getattr(repair_mod, name)) == recorded[name],
        )
    check(
        "prompt hash generic_retry_feedback_string",
        prompt_hash(GENERIC_RETRY_FEEDBACK) == recorded["generic_retry_feedback_string"],
    )
    check(
        "prompt hash masked_bullet_template",
        prompt_hash(MASKED_BULLET_TEMPLATE) == recorded["masked_bullet_template"],
    )


def runnable_fixture_ids() -> set[str]:
    rows = [json.loads(ln) for ln in jsonl_lines(FIXTURES / "manifest.jsonl")]
    ids = [r["fixture_id"] for r in rows]
    check("benchmark manifest rows unique", len(ids) == len(set(ids)), f"{len(ids)} rows")

    missing = [
        r[k]
        for r in rows
        for k in ("theory_a_path", "theory_b_path")
        if not (FIXTURES / r[k]).exists()
    ]
    check("theory files on disk", not missing, f"{2 * len(rows)} expected, {len(missing)} missing")

    attrition_ids = {
        json.loads(ln)["fixture_id"] for ln in jsonl_lines(FIXTURES / "attrition.jsonl")
    }
    check(
        "attrition disjoint from manifest",
        not (attrition_ids & set(ids)),
        f"{len(attrition_ids)} attrition rows",
    )

    positives = {r["fixture_id"] for r in rows if r["label"] == "CERTIFIED"}
    runnable = set(ids) - positives
    check(
        "runnable set = manifest minus CERTIFIED positives",
        len(runnable) == N_RUNNABLE and all(not r["repairable"] for r in rows if r["fixture_id"] in positives),
        f"{len(ids)} - {len(positives)} = {len(runnable)}",
    )
    return runnable


def expected_run_dirs() -> dict[str, str]:
    dirs: dict[str, str] = {}
    for model in MODELS:
        for arm in ARMS:
            for r in REPS:
                dirs[f"conf_{model}_{arm}_r{r}"] = "arm"
        for r in REPS:
            dirs[f"conf_{model}_e4_r{r}"] = "e4"
    for r in REPS:
        dirs[f"conf_minimax_e4_r{r}_preclean"] = "e4"
    return dirs


def check_campaign_structure(runnable: set[str]) -> None:
    expected = expected_run_dirs()
    on_disk = {p.name for p in RUNS.glob("conf_*")}
    check(
        "conf_* run directories",
        on_disk == set(expected),
        f"{len(on_disk)} on disk, {len(expected)} expected",
    )

    bad_files: list[str] = []
    bad_cover: list[str] = []
    for name, kind in sorted(expected.items()):
        d = RUNS / name
        need = (
            ("metadata.json", "repair_results.jsonl", "summary.json")
            if kind == "arm"
            else ("e4_replay.jsonl", "e4_summary.json")
        )
        if not all((d / f).exists() for f in need):
            bad_files.append(name)
            continue
        if kind == "arm":
            counts = Counter(fixture_ids(jsonl_lines(d / "repair_results.jsonl")))
            if set(counts) != runnable or any(c != 1 for c in counts.values()):
                bad_cover.append(name)
            if json.loads((d / "summary.json").read_text())["n_fixtures"] != N_RUNNABLE:
                bad_cover.append(name + " (summary)")
    check("required files per run dir", not bad_files, ", ".join(bad_files) or "all present")
    check(
        f"each arm run covers the {N_RUNNABLE} runnable fixtures once",
        not bad_cover,
        ", ".join(bad_cover) or "45 arm runs",
    )

    for rel in (
        "confirmatory_analysis.json",
        "minimax_extension/confirmatory_analysis.json",
        "minimax_extension/confirmatory_analysis_preclean.json",
    ):
        check(f"analysis report {rel}", (ANALYSIS_DIR / rel).exists())
    missing_e4 = [
        n
        for r in REPS
        for n in (f"e4_minimax_r{r}", f"e4_minimax_r{r}_preclean")
        if not (ANALYSIS_DIR / n).is_dir()
    ]
    check("extension E4 replay dirs", not missing_e4, ", ".join(missing_e4) or "6 dirs")

    for rel in (
        "paper/analysis_protocol.md",
        "paper/analysis_protocol_amendment1.md",
        "minimax_data_audit.md",
        "scripts/paper_tables.py",
    ):
        check(f"promised artifact {rel}", (ROOT / rel).exists())


def contamination_predicate() -> re.Pattern[str]:
    text = (QUARANTINE / "predicate.txt").read_text()
    regex = text[text.index("(?isx)") :]
    return re.compile(regex)


def row_is_contaminated(row: dict, predicate: re.Pattern[str]) -> bool:
    for rnd in row.get("rounds", []):
        if (
            rnd.get("action") == "call_error"
            and rnd.get("model_called") is not False
            and isinstance(rnd.get("apply_error"), str)
            and predicate.match(rnd["apply_error"])
        ):
            return True
    return False


def check_quarantine_trail() -> None:
    manifest = json.loads((QUARANTINE / "sha256_manifest.json").read_text())
    ids = json.loads((QUARANTINE / "contaminated_ids.json").read_text())
    predicate = contamination_predicate()

    expected_runs = {f"conf_minimax_{arm}_r{r}" for arm in ARMS for r in REPS}
    check(
        "quarantine manifest covers the 15 MiniMax arm runs",
        set(manifest) == expected_runs,
    )
    # Pass-1 removals are keyed by run; later audit passes live under the
    # meta-keys "_pass2"/"_pass3" as {run: [fixture_ids]}.
    pass_records = {k: v for k, v in ids.items() if k.startswith("_pass")}
    ids = {k: v for k, v in ids.items() if not k.startswith("_pass")}
    check(
        "contaminated_ids keys = runs with a filtered state",
        set(ids) == {k for k, v in manifest.items() if "filtered_sha256" in v},
    )
    for pass_key, per_run in sorted(pass_records.items()):
        n = pass_key.removeprefix("_pass")
        for run, expected_ids in sorted(per_run.items()):
            removed_files = sorted(QUARANTINE.glob(f"{run}.pass{n}_removed_row*.jsonl"))
            found = {
                fid for f in removed_files for fid in fixture_ids(jsonl_lines(f))
            }
            check(
                f"contaminated_ids {pass_key} matches removed rows {run}",
                bool(removed_files) and found == set(expected_ids),
            )

    for run, entry in sorted(manifest.items()):
        qfile = QUARANTINE / f"{run}.repair_results.jsonl"
        original = jsonl_lines(qfile)
        check(
            f"quarantined original {run}",
            sha_bytes(b"".join(original)) == entry["original_sha256"],
        )

        live = jsonl_lines(RUNS / run / "repair_results.jsonl")
        if "filtered_sha256" not in entry:
            check(
                f"live file untouched {run}",
                sha_bytes(b"".join(live)) == entry["original_sha256"],
            )
        else:
            removed = set(ids[run])
            kept = [ln for ln in original if json.loads(ln)["fixture_id"] not in removed]
            check(
                f"filtered state reproducible {run}",
                sha_bytes(b"".join(kept)) == entry["filtered_sha256"]
                and entry["removed"] == len(removed),
                f"{len(removed)} rows removed",
            )
            # Rows removed in later audit passes (best_of_n_r2) also count as
            # legitimately rerun fixture ids for the live-file provenance check.
            rerun_ok = set(removed)
            for extra in QUARANTINE.glob(f"{run}.pass*_removed_row*.jsonl"):
                rerun_ok |= set(fixture_ids(jsonl_lines(extra)))
            original_set = set(original)
            foreign = [ln for ln in live if ln not in original_set]
            check(
                f"live rows are original or rerun-of-removed {run}",
                all(json.loads(ln)["fixture_id"] in rerun_ok for ln in foreign),
                f"{len(foreign)} rerun rows",
            )
            check(
                f"live fixture multiset preserved {run}",
                sorted(fixture_ids(live)) == sorted(fixture_ids(original)),
            )

        check(
            f"live file predicate-clean {run}",
            not any(row_is_contaminated(json.loads(ln), predicate) for ln in live),
        )

    # Multi-pass chain for conf_minimax_best_of_n_r2: prefilter snapshots and
    # removed-row files reproduce the recorded pass hashes.
    run = "conf_minimax_best_of_n_r2"
    entry = manifest[run]
    p2pre = jsonl_lines(QUARANTINE / f"{run}.repair_results.pass2_prefilter.jsonl")
    check(
        "pass2 prefilter snapshot hash",
        sha_bytes(b"".join(p2pre)) == entry["pass2_prefilter_sha256"],
    )
    rm2 = set(jsonl_lines(QUARANTINE / f"{run}.pass2_removed_row.jsonl"))
    check(
        "pass2 filtered state reproducible",
        sha_bytes(b"".join(ln for ln in p2pre if ln not in rm2))
        == entry["pass2_filtered_sha256"],
    )
    p3pre = jsonl_lines(QUARANTINE / f"{run}.repair_results.pass3_prefilter.jsonl")
    rm3 = set(jsonl_lines(QUARANTINE / f"{run}.pass3_removed_rows.jsonl"))
    check(
        "pass3 filtered state reproducible",
        sha_bytes(b"".join(ln for ln in p3pre if ln not in rm3))
        == entry["pass3_filtered_sha256"],
    )


def check_depth2_exploratory() -> None:
    """The appendix cites the depth-2 campaigns descriptively; pin those counts."""
    d2runs = ROOT / "runs/experiments/repair_d2/runs"
    cited = {
        "d2_single_shot_repair": 7,
        "d2_generic_retry": 8,
        "d2_verifier_feedback": 5,
        "d2_vf_detailed": 2,
        "d2p2_single_shot_repair": 0,
        "d2p2_generic_retry": 3,
        "d2p2_verifier_feedback": 1,
    }
    for run, n_succ in sorted(cited.items()):
        recs = [json.loads(l) for l in jsonl_lines(d2runs / run / "repair_results.jsonl")]
        check(
            f"depth-2 {run} cited count",
            len(recs) == 120 and sum(1 for r in recs if r.get("success")) == n_succ,
            f"expected {n_succ}/120",
        )
    aborted = [
        json.loads(l)
        for arm in ("single_shot_repair", "generic_retry", "verifier_feedback")
        for l in jsonl_lines(d2runs / f"d2p_{arm}" / "repair_results.jsonl")
    ]
    check(
        "depth-2 aborted attempt produced no model output",
        len(aborted) == 360 and all(r.get("invalid") for r in aborted),
    )


def main() -> int:
    check_execution_manifest()
    runnable = runnable_fixture_ids()
    check_campaign_structure(runnable)
    check_quarantine_trail()
    check_depth2_exploratory()
    print()
    if _failures:
        print(f"{len(_failures)} check(s) FAILED:")
        for name in _failures:
            print(f"  - {name}")
        return 1
    print("all release artifact checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
