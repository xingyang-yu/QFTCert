"""Phase 2c-a MVP detection benchmark — manual Anthropic-API entry.

Drives a committed fixture set (`fixtures/detection_mvp.jsonl` by
default) through the live Anthropic Messages API and writes the four
artefacts (`fixtures.jsonl`, `results.jsonl`, `summary.json`,
`metadata.json`) into `runs/detection/<run_id>/`.

This script is NOT in CI. The user invokes it explicitly when ready to
spend the API credit. Per the locked plan §10, the MVP scale is ~30
samples × ~800 tokens RT, so a single run costs well under $1 on
current Sonnet pricing.

Required environment:
  - ANTHROPIC_API_KEY (or `anthropic` SDK's own credential lookup)
  - `pip install -e .[llm]` so the anthropic SDK is importable

Usage::

    python -m scripts.run_detection_benchmark
    python -m scripts.run_detection_benchmark --model claude-sonnet-4-6 --max-tokens 2048
    python -m scripts.run_detection_benchmark --fixtures fixtures/detection_smoke.jsonl
    python -m scripts.run_detection_benchmark --dry-run     # validates wiring only

A `--dry-run` mode uses a `MockLLMClient` that always replies "dual"
with low confidence — useful for confirming the runner is wired up
correctly before paying for the live call.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dualitycert.agent import AnthropicAdapter, MockLLMClient  # noqa: E402
from dualitycert.agent.detection import (  # noqa: E402
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
)
from dualitycert.benchmark import (  # noqa: E402
    read_fixtures_jsonl,
    run_detection_benchmark,
)


DEFAULT_FIXTURES = "fixtures/detection_mvp.jsonl"
DEFAULT_OUTPUT_DIR = "runs/detection"


def _build_dry_run_responses(n: int) -> list[dict]:
    """Canned "dual / low / dry-run" responses, one per fixture."""

    return [
        {"verdict": "dual", "confidence": "low", "reasoning": "dry-run placeholder"}
        for _ in range(n)
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures",
        default=DEFAULT_FIXTURES,
        type=Path,
        help=f"Path to JSONL fixture file (default: {DEFAULT_FIXTURES}).",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Anthropic model id (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--max-tokens",
        default=DEFAULT_MAX_TOKENS,
        type=int,
        help=f"max_tokens per call (default: {DEFAULT_MAX_TOKENS}).",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        type=Path,
        help=f"Where to write runs/<id>/ (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Run identifier (default: ISO-8601 UTC timestamp).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Skip the Anthropic API and use a MockLLMClient that "
            "replies 'dual / low' for every fixture. Useful for "
            "verifying wiring before paying for the live call."
        ),
    )
    args = parser.parse_args(argv)

    fixtures = read_fixtures_jsonl(args.fixtures)
    if not fixtures:
        print(f"No fixtures found at {args.fixtures}", file=sys.stderr)
        return 2

    if args.dry_run:
        client = MockLLMClient(
            structured_responses=_build_dry_run_responses(len(fixtures))
        )
        run_config = {"dry_run": True, "fixtures_path": str(args.fixtures)}
    else:
        client = AnthropicAdapter()
        run_config = {"dry_run": False, "fixtures_path": str(args.fixtures)}

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if args.dry_run and args.run_id is None:
        run_id = f"dryrun_{run_id}"

    result = run_detection_benchmark(
        fixtures,
        client=client,
        model=args.model,
        max_tokens=args.max_tokens,
        output_dir=args.output_dir,
        run_id=run_id,
        run_config=run_config,
    )

    print(f"Run directory: {result.run_dir}")
    print(
        "Summary: "
        + json.dumps(
            {
                "n_total": result.summary["n_total"],
                "accuracy": result.summary["accuracy"],
                "accuracy_by_class": result.summary.get("accuracy_by_class", {}),
                "accuracy_by_perturbation_type": result.summary.get(
                    "accuracy_by_perturbation_type", {}
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
