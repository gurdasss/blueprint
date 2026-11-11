"""`bp` command-line entry point. Argument parsing only; the work happens in the commands."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from blueprint import __version__
from blueprint.commands import apply as apply_cmd
from blueprint.commands import check as check_cmd
from blueprint.commands import describe as describe_cmd
from blueprint.commands import fmt as fmt_cmd
from blueprint.commands import inspect as inspect_cmd
from blueprint.commands import manifest as manifest_cmd
from blueprint.commands import theme as theme_cmd
from blueprint.guidelines import GuidelinesError
from blueprint.layouts import LayoutError
from blueprint.pbir.reader import ReportFormatError
from blueprint.pbir.registry import RegistryError
from blueprint.pbir.semantic import ModelError
from blueprint.pbir.theme import ThemeError
from blueprint.pbir.writer import WriteError
from blueprint.spec import SpecError

REPORT_HELP = "a .Report folder, a .pbip file, or a folder containing one .Report"
VISUALS_HELP = ("try a directory of your own visual contracts for this run, e.g. ./my-visuals "
                "(repeatable; added to extensions.custom_visuals.search_path, which is where a "
                "lasting opt-in belongs)")
SET_HELP = ("override one guidelines key for this run, e.g. --set spacing.grid=8 "
            "(repeatable; the key is a dotted path, the value is read as YAML)")


def _guideline_flags(p: argparse.ArgumentParser, *, visuals: bool = True) -> None:
    """The flags every command that loads guidelines takes: the file, layer-4 overrides, and
    (where contracts are read) extra visual directories."""
    p.add_argument("--guidelines", type=Path,
                   help="guidelines file (default: $BLUEPRINT_GUIDELINES)")
    p.add_argument("--set", dest="overrides", action="append", metavar="KEY=VALUE", help=SET_HELP)
    # Retired: it was the only key with a flag, so layer 4 existed for one key on two commands.
    p.add_argument("--grid", type=int, help=argparse.SUPPRESS)
    if visuals:
        p.add_argument("--visuals", type=Path, action="append", metavar="DIR", help=VISUALS_HELP)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bp", description=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("inspect", help="print pages, visuals, IDs and positions (read-only)")
    p.add_argument("--report", type=Path, required=True, help=REPORT_HELP)
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.set_defaults(func=inspect_cmd.run)

    p = sub.add_parser("check", help="validate against guidelines (read-only; exit 1 on errors)")
    p.add_argument("--report", type=Path, required=True, help=REPORT_HELP)
    _guideline_flags(p)
    out = p.add_mutually_exclusive_group()
    out.add_argument("--json", action="store_true", help="machine-readable output")
    out.add_argument("--github", action="store_true",
                     help="also print GitHub Actions annotations, one per finding")
    p.add_argument("--strict", action="store_true", help="exit 1 on warnings too")
    p.set_defaults(func=check_cmd.run)

    p = sub.add_parser("describe", help="what a page spec can use: syntax, visual types, layouts, "
                                        "guideline limits and, with --report, model fields (read-only)")
    p.add_argument("--report", type=Path, help=REPORT_HELP + "; adds its model fields and pages")
    _guideline_flags(p)
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.set_defaults(func=describe_cmd.run)

    p = sub.add_parser("apply", help="create or update pages from page specs (one page per spec)")
    p.add_argument("spec", type=Path, nargs="+",
                   help="page spec YAML file(s), or folders of them; all are checked before any is written")
    p.add_argument("--report", type=Path, required=True, help=REPORT_HELP)
    _guideline_flags(p)
    p.add_argument("--dry-run", action="store_true", help="print the planned writes; change nothing")
    p.add_argument("--force-schema", action="store_true",
                   help="write even when a file's schema major version is unknown")
    p.add_argument("--take-over", action="store_true",
                   help="build a page that another spec built (it becomes this spec's page)")
    p.add_argument("--overwrite-edits", action="store_true",
                   help="rebind Blueprint visuals whose fields were changed in Desktop to what the spec says")
    p.set_defaults(func=apply_cmd.run)

    p = sub.add_parser("manifest", help="(re)generate the manifest from the report's current state")
    p.add_argument("--report", type=Path, required=True, help=REPORT_HELP)
    _guideline_flags(p)
    p.add_argument("--dry-run", action="store_true", help="print the planned write; change nothing")
    p.set_defaults(func=manifest_cmd.run)

    p = sub.add_parser("theme", help="write a custom theme from the guidelines and use it")
    p.add_argument("--report", type=Path, required=True, help=REPORT_HELP)
    _guideline_flags(p, visuals=False)
    p.add_argument("--replace-theme", action="store_true",
                   help="switch away from the report's existing custom theme (its file is kept)")
    p.add_argument("--dry-run", action="store_true", help="print the planned writes; change nothing")
    p.add_argument("--force-schema", action="store_true",
                   help="write even when a file's schema major version is unknown")
    p.set_defaults(func=theme_cmd.run)

    p = sub.add_parser("fmt", help="snap visuals to the grid (idempotent)")
    p.add_argument("--report", type=Path, required=True, help=REPORT_HELP)
    _guideline_flags(p)
    p.add_argument("--dry-run", action="store_true", help="print the planned writes; change nothing")
    p.add_argument("--force-schema", action="store_true",
                   help="write even when a file's schema major version is unknown")
    p.set_defaults(func=fmt_cmd.run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if getattr(args, "grid", None) is not None:
            raise GuidelinesError(f"--grid was replaced by --set spacing.grid={args.grid}")
        return args.func(args)
    except (ReportFormatError, GuidelinesError, WriteError, SpecError, LayoutError, ModelError,
            RegistryError, ThemeError, apply_cmd.ApplyError) as exc:
        print(f"bp: error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:  # e.g. permission denied, read-only folder, disk full
        where = f" ({exc.filename})" if getattr(exc, "filename", None) else ""
        print(f"bp: error: {exc.strerror or exc}{where}; nothing was changed", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
