"""`bp inspect`: print a report's structure. Read-only."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from blueprint.model import Report
from blueprint.pbir.reader import read_report


def run(args: argparse.Namespace) -> int:
    report = read_report(args.report)
    print(to_json(report) if args.json else to_text(report))
    return 0


def _num(v: float | None) -> str:
    if v is None:
        return "-"
    return str(int(v)) if float(v).is_integer() else f"{v:.2f}"


def to_text(report: Report) -> str:
    lines = [f"Report: {report.root.name}"]
    for kind, versions in report.schema_versions.items():
        lines.append(f"  schema {kind}: {', '.join(versions)}")
    for i, page in enumerate(report.pages, 1):
        active = "  (active)" if page.name == report.active_page else ""
        size = f"{_num(page.width)}x{_num(page.height)}"
        lines.append("")
        lines.append(f"[{i}] {page.display_name}  id={page.name}  {size} {page.display_option}{active}")
        visuals = sorted(page.visuals, key=lambda v: (v.rect.y, v.rect.x, v.name))
        for v in visuals:
            r = v.rect
            flags = [f for f, on in (("group", v.is_group), ("hidden", v.hidden),
                                     ("ignored", v.ignored), ("unpositioned", not v.positioned)) if on]
            if v.parent_group:
                flags.append(f"in:{v.parent_group}")
            lines.append(
                f"    {v.name:<22} {v.visual_type or '-':<22} "
                f"x={_num(r.x):>7} y={_num(r.y):>7} w={_num(r.width):>7} h={_num(r.height):>7}"
                + (f"  {v.title!r}" if v.title else "")
                + (f"  [{' '.join(flags)}]" if flags else "")
            )
    if report.warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"  - {w}" for w in report.warnings)
    return "\n".join(lines)


def to_json(report: Report) -> str:
    def page(p):
        d = asdict(p)
        d.pop("source")
        for v in d["visuals"]:
            v.pop("source")
        return d

    return json.dumps(
        {
            "report": report.root.name,
            "schema_versions": report.schema_versions,
            "active_page": report.active_page,
            "pages": [page(p) for p in report.pages],
            "warnings": report.warnings,
        },
        indent=2,
        ensure_ascii=False,
    )
