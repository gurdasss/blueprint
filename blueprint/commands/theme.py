"""`bp theme`: write a custom theme from the guidelines and make the report use it.

The theme holds only overrides on top of the report's base theme (as Desktop's own customised
themes do): palette.categorical -> dataColors, palette.text/background -> foreground/background
(and the colour of every text class), typography.title/callout -> textClasses.title/callout,
typography.card_label -> visualStyles.cardVisual["*"].label.
Visuals with their own colours or fonts aren't changed; `bp check` still reports them.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from blueprint import guidelines
from blueprint.pbir import jsonfmt, theme, writer
from blueprint.pbir.reader import read_report
from blueprint.plan import Plan


def build_plan(args: argparse.Namespace) -> Plan:
    report = read_report(args.report)
    rules = guidelines.load(args.guidelines, report.root, guidelines.overrides_from(getattr(args, "overrides", None)))
    doc, notes = theme.build(rules)
    report_doc = report.source.documents.get(Path("definition/report.json"))
    if report_doc is None:
        raise theme.ThemeError("definition/report.json is missing")
    plan = Plan(root=report.root)
    plan.warnings.extend(notes)
    writer.add_file(plan, theme.REL_PATH, jsonfmt.dump_bytes(doc),
                    f"theme {doc['name']!r} from guidelines: " + ", ".join(k for k in doc if k != "name"))
    writer.add_modify(plan, report_doc, theme.with_theme(report_doc.data, replace=args.replace_theme),
                      f"custom theme -> {theme.FILE_NAME}", force_schema=args.force_schema)
    return plan


def run(args: argparse.Namespace) -> int:
    plan = build_plan(args)
    if not args.dry_run:
        writer.apply(plan)
    print(plan.render())
    if plan.writes and not args.dry_run:
        print(f"\nWrote {len(plan.writes)} file(s). If the report is open in Power BI Desktop, "
              "accept 'Apply external changes' (unsaved Desktop edits will be overwritten).",
              file=sys.stderr)
    return 0
