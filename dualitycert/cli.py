"""Small command-line entry point for checking machine-readable claims."""

from __future__ import annotations

import argparse
import sys

from dualitycert.qft.claims import load_claim_file
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

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
