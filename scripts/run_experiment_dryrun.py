"""End-to-end dry-run of the paper-scale harness (no API key required).

Generates a verifier-gated manifest, runs single-shot detection +
diagnosis with the offline `DryRunModelClient`, then runs the repair
loop (verifier_feedback arm) on the repairable negatives. Doubles as a
smoke test and a worked example for `docs/experiments.md`.

Run from repo root::

    python -m scripts.run_experiment_dryrun
    python -m scripts.run_experiment_dryrun --config configs/mvp.json --out runs/dryrun_demo
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dualitycert.agent.dryrun import DryRunModelClient  # noqa: E402
from dualitycert.experiments.config import ExperimentConfig  # noqa: E402
from dualitycert.experiments.generation import generate_fixtures  # noqa: E402
from dualitycert.experiments.repair import run_repair_experiment  # noqa: E402
from dualitycert.experiments.single_shot import run_single_shot  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/mvp.json")
    parser.add_argument(
        "--out",
        default=None,
        help="Output directory (default: a fresh temp directory).",
    )
    args = parser.parse_args(argv)

    out = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="qftcert_dryrun_"))
    config = ExperimentConfig.from_json_file(args.config)

    print(f"[1/3] generate-fixtures  config={config.name}")
    gen = generate_fixtures(config, out_dir=out / "fixtures")
    print(
        f"      manifest={len(gen.manifest)} {gen.label_counts()} "
        f"attrition={len(gen.attrition)}"
    )

    print("[2/3] run-single-shot     model=dryrun")
    ss = run_single_shot(
        gen.manifest,
        theory_root=out / "fixtures",
        client=DryRunModelClient(),
        out_dir=out / "single_shot",
        model="dryrun",
        tasks=("detection", "diagnosis"),
        run_id="dryrun",
    )
    det = ss.summary["detection"]
    print(
        f"      detection acc={det['accuracy']:.3f} "
        f"bal_acc={det['balanced_accuracy']} invalid={det['invalid_rate']:.3f}"
    )

    print("[3/3] run-repair-loop     arm=verifier_feedback model=dryrun")
    rep = run_repair_experiment(
        gen.manifest,
        theory_root=out / "fixtures",
        client=DryRunModelClient(),
        config=config,
        arm="verifier_feedback",
        out_dir=out / "repair",
        run_id="dryrun",
    )
    s = rep.summary
    print(
        f"      success_rate={s['success_rate']:.3f} @1={s['success_at_1']:.3f} "
        f"@5={s['success_at_5']:.3f} invalid={s['invalid_json_rate']:.3f}"
    )
    print(f"\nArtifacts under: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
