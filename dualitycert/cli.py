"""Small command-line entry point for checking machine-readable claims."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dualitycert.qft.claims import load_claim_file
from dualitycert.qft.critic import build_critic_report, build_repair_prompt
from dualitycert.qft.dualities import evaluate_claim


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dualitycert",
        description="Check SQCD-like duality claims and emit consistency certificates.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser(
        "check",
        help="Load a JSON SQCD-like claim and run implemented consistency checks.",
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

    args = parser.parse_args(argv)
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

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
