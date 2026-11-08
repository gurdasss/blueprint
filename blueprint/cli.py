"""`bp` command-line entry point. Argument parsing only; the work happens in the commands."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from blueprint import __version__
from blueprint.commands import inspect as inspect_cmd
from blueprint.pbir.reader import ReportFormatError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bp", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("inspect", help="print pages, visuals, IDs and positions (read-only)")
    p.add_argument("--report", type=Path, required=True,
                   help="a .Report folder, a .pbip file, or a folder containing one .Report")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.set_defaults(func=inspect_cmd.run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except ReportFormatError as exc:
        print(f"bp: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
