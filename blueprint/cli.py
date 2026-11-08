"""`bp` command-line entry point. Argument parsing only; the work happens in the commands."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from blueprint import __version__
from blueprint.commands import fmt as fmt_cmd
from blueprint.commands import inspect as inspect_cmd
from blueprint.guidelines import GuidelinesError
from blueprint.pbir.reader import ReportFormatError
from blueprint.pbir.writer import WriteError

REPORT_HELP = "a .Report folder, a .pbip file, or a folder containing one .Report"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bp", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("inspect", help="print pages, visuals, IDs and positions (read-only)")
    p.add_argument("--report", type=Path, required=True, help=REPORT_HELP)
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.set_defaults(func=inspect_cmd.run)

    p = sub.add_parser("fmt", help="snap visuals to the grid (idempotent)")
    p.add_argument("--report", type=Path, required=True, help=REPORT_HELP)
    p.add_argument("--guidelines", type=Path, help="guidelines file (default: $BLUEPRINT_GUIDELINES)")
    p.add_argument("--grid", type=int, help="override grid.size")
    p.add_argument("--dry-run", action="store_true", help="print the planned writes; change nothing")
    p.add_argument("--force-schema", action="store_true",
                   help="write even when a file's schema major version is unknown")
    p.set_defaults(func=fmt_cmd.run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ReportFormatError, GuidelinesError, WriteError) as exc:
        print(f"bp: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
