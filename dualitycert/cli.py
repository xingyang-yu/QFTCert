"""Command-line entry point for certificates and verifier-gated experiments."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dualitycert.qft.claims import load_claim_file
from dualitycert.qft.critic import build_critic_report, build_repair_prompt
from dualitycert.qft.dualities import evaluate_claim


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dualitycert",
        description=(
            "Emit auditable QFT consistency certificates and run "
            "verifier-gated agent experiments."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser(
        "check",
        help="Load a supported JSON duality claim and run implemented checks.",
    )
    check_parser.add_argument("claim_file", help="Path to a JSON claim file.")
    check_parser.add_argument(
        "--json",
        action="store_true",
        help="Print a JSON certificate instead of human-readable text.",
    )

    critique_parser = subparsers.add_parser(
        "critique",
        help="Print a critic report derived from implemented check results.",
    )
    critique_parser.add_argument("claim_file", help="Path to a JSON claim file.")
    critique_parser.add_argument(
        "--out",
        help="Optional path to write the critic report.",
    )

    repair_parser = subparsers.add_parser(
        "repair-prompt",
        help="Print a repair prompt derived from failed obligations.",
    )
    repair_parser.add_argument("claim_file", help="Path to a JSON claim file.")
    repair_parser.add_argument(
        "--out",
        help="Optional path to write the repair prompt.",
    )

    llm_parser = subparsers.add_parser(
        "llm-repair",
        help="Run the verifier-in-the-loop with Claude as the repair agent (requires ANTHROPIC_API_KEY).",
    )
    llm_parser.add_argument("claim_file", help="Path to a JSON claim file.")
    llm_parser.add_argument(
        "--model",
        default=None,
        help="Anthropic model id (default: claude-sonnet-4-6).",
    )
    llm_parser.add_argument(
        "--max-iterations",
        type=int,
        default=4,
        help="Max LLM repair attempts before giving up.",
    )
    llm_parser.add_argument(
        "--trace",
        help="Optional path to write the full iteration trace as JSON.",
    )

    # Paper-scale experiment harness subcommands (Deliverable 9). Handlers
    # live in dualitycert.experiments.cli and lazily import the heavy
    # experiment modules, so the core commands above stay lightweight.
    from dualitycert.experiments.cli import add_subparsers as _add_experiment_subparsers

    _add_experiment_subparsers(subparsers)

    args = parser.parse_args(argv)

    # Experiment subcommands attach a `func` handler via set_defaults.
    handler = getattr(args, "func", None)
    if handler is not None:
        try:
            return handler(args)
        except Exception as exc:  # clean message, matching the CLI's style
            # Long-running experiment commands need the WHERE, not just the
            # message: a bare "[Errno 60] Operation timed out" once cost an
            # hour of diagnosis (an iCloud-evicted fixture file failing in
            # _load_theory, nowhere near the network client).
            import traceback

            traceback.print_exc(file=sys.stderr)
            print(f"dualitycert: {exc}", file=sys.stderr)
            return 2

    if args.command == "check":
        try:
            claim = load_claim_file(args.claim_file)
            certificate = evaluate_claim(claim)
        except Exception as exc:
            print(f"dualitycert: {exc}", file=sys.stderr)
            return 2

        if args.json:
            print(certificate.to_json())
        else:
            print(certificate.render_text())
        return 0

    if args.command in {"critique", "repair-prompt"}:
        try:
            claim = load_claim_file(args.claim_file)
            certificate = evaluate_claim(claim)
            if args.command == "critique":
                output = build_critic_report(claim, certificate)
            else:
                output = build_repair_prompt(claim, certificate)
        except Exception as exc:
            print(f"dualitycert: {exc}", file=sys.stderr)
            return 2

        if args.out:
            Path(args.out).write_text(output + "\n", encoding="utf-8")
        else:
            print(output)
        return 0

    if args.command == "llm-repair":
        return _run_llm_repair_cli(args)

    parser.error(f"Unsupported command: {args.command}")
    return 2


def _run_llm_repair_cli(args) -> int:
    from dualitycert.agent import run_llm_repair_loop

    try:
        initial_data = json.loads(Path(args.claim_file).read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"dualitycert: failed to load claim file: {exc}", file=sys.stderr)
        return 2

    kwargs = {"max_iterations": args.max_iterations}
    if args.model:
        kwargs["model"] = args.model

    try:
        result = run_llm_repair_loop(initial_data, **kwargs)
    except Exception as exc:
        print(f"dualitycert: LLM repair loop failed: {exc}", file=sys.stderr)
        return 2

    print(f"Model:              {result.model}")
    print(f"Iterations:         {result.iteration_count}")
    print(f"Converged:          {result.converged}")
    print(f"Final outward:      {result.final_outward_status}")
    print()
    for it in result.iterations:
        verdict = "PASS" if it.outward_status in {"PASSED_IMPLEMENTED_OBLIGATIONS", "PARTIAL_WITH_NOT_IMPLEMENTED_OBLIGATIONS"} else "FAIL"
        print(f"--- iteration {it.iteration}: {verdict} ({it.outward_status}) ---")
        if it.failed_obligation_names:
            print(f"  failed: {', '.join(it.failed_obligation_names)}")
        if it.parse_error:
            print(f"  parse_error: {it.parse_error}")
        if it.llm_raw_response:
            preview = it.llm_raw_response[:200].replace("\n", " ")
            print(f"  llm_response[:200]: {preview}")
        print()

    if args.trace:
        trace_data = {
            "model": result.model,
            "converged": result.converged,
            "final_outward_status": result.final_outward_status,
            "iterations": [
                {
                    "iteration": it.iteration,
                    "outward_status": it.outward_status,
                    "failed_obligation_names": list(it.failed_obligation_names),
                    "claim_data": it.claim_data,
                    "prompt_sent": it.prompt_sent,
                    "llm_raw_response": it.llm_raw_response,
                    "llm_repaired_data": it.llm_repaired_data,
                    "parse_error": it.parse_error,
                }
                for it in result.iterations
            ],
        }
        Path(args.trace).write_text(
            json.dumps(trace_data, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Wrote full trace to {args.trace}")

    return 0 if result.converged else 1


if __name__ == "__main__":
    raise SystemExit(main())
