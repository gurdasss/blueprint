"""`bp manifest`: (re)generate the manifest from the report's current state."""

from __future__ import annotations

import argparse
from pathlib import Path

from blueprint import guidelines, manifest
from blueprint.model import Report
from blueprint.pbir import writer
from blueprint.pbir.reader import read_report
from blueprint.plan import FileWrite, Plan


def plan_for(report: Report, rules: guidelines.Guidelines) -> Plan:
    target = report.root / manifest.FILE
    previous = target.read_bytes() if target.exists() else None
    data = manifest.render(report, rules, previous)
    plan = Plan(root=report.root)
    if data != previous:
        pages = len(report.pages)
        visuals = sum(len(p.visuals) for p in report.pages)
        plan.writes.append(FileWrite(Path(manifest.FILE), previous, data,
                                     (f"manifest: {pages} page(s), {visuals} visual(s)",)))
    return plan


def run(args: argparse.Namespace) -> int:
    report = read_report(args.report)
    rules = guidelines.load(args.guidelines, report.root, guidelines.overrides_from(getattr(args, "overrides", None)),
                            visuals=getattr(args, "visuals", None) or ())
    plan = plan_for(report, rules)
    if not args.dry_run:
        writer.apply(plan)
    print(plan.render())
    return 0
