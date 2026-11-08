"""`bp fmt`: snap existing visuals to the grid. Idempotent."""

from __future__ import annotations

import argparse
import sys

from blueprint import grid, guidelines
from blueprint.pbir import writer
from blueprint.pbir.reader import read_report
from blueprint.plan import Plan


def build_plan(args: argparse.Namespace) -> Plan:
    report = read_report(args.report)
    overrides = {"grid": {"size": args.grid}} if args.grid is not None else None
    rules = guidelines.load(args.guidelines, report.root, overrides)
    if not rules.grid.snap:
        plan = Plan(root=report.root)
        plan.warnings.append("grid.snap is false in the guidelines; nothing to do")
        return plan
    result = grid.snap_report(report, rules.grid.size)
    plan = writer.plan_writes(report, force_schema=args.force_schema)
    plan.warnings = report.warnings + result.warnings + plan.warnings
    return plan


def run(args: argparse.Namespace) -> int:
    plan = build_plan(args)
    if args.dry_run:
        print(plan.render())
        return 0
    writer.apply(plan)
    print(plan.render())
    if not plan.empty:
        print(
            f"\nWrote {len(plan.writes)} file(s). If the report is open in Power BI Desktop, "
            "accept 'Apply external changes' (unsaved Desktop edits will be overwritten).",
            file=sys.stderr,
        )
    return 0
