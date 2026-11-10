"""`bp check`: validate a report against guidelines. Read-only.

Exit status: 0 if no errors, 1 if there are errors (or any warnings, with ``--strict``),
2 if the report or guidelines couldn't be read. The exit codes are stable so CI can rely on them.
``--github`` adds GitHub Actions workflow commands, so each finding is annotated on its
``page.json``/``visual.json`` (the composite action in ``action.yml`` uses it).
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

from blueprint import guidelines, manifest
from blueprint.guidelines import Guidelines
from blueprint.model import Report
from blueprint.pbir import schemas
from blueprint.pbir.reader import read_report
from blueprint.validate import CheckResult, Finding, check_report


def run_check(args: argparse.Namespace) -> tuple[Report, Guidelines, CheckResult]:
    report = read_report(args.report)
    overrides = {"spacing": {"grid": args.grid}} if args.grid is not None else None
    rules = guidelines.load(args.guidelines, report.root, overrides)
    result = check_report(report, rules)
    level = rules.check.severity["format"]
    if level != "off":
        result.findings[:0] = _format_findings(report, level)
    label = f"{rules.name}@{rules.version}"
    for page in report.pages:
        if page.guidelines and page.guidelines != label:
            result.notes.append(f"{page.display_name}: built with guidelines {page.guidelines}, "
                                f"checked against {label}")
    stale = _manifest_state(report, rules)
    if stale:
        result.notes.append(stale)
    if rules.unchecked:
        result.notes.append("not checked yet (set in guidelines, not implemented): "
                            + ", ".join(rules.unchecked))
    return report, rules, result


def _manifest_state(report: Report, rules: Guidelines) -> str | None:
    """A note when the committed manifest no longer describes the report."""
    path = report.root / manifest.FILE
    if not path.exists():
        return None if not any(p.spec_page for p in report.pages) else (
            f"no {manifest.FILE}; run `bp manifest`")
    if manifest.render(report, rules, path.read_bytes()) != path.read_bytes():
        return f"{manifest.FILE} is out of date (the report changed since it was generated); run `bp manifest`"
    return None


def _format_findings(report: Report, level: str) -> list[Finding]:
    found = [Finding("format", level, w) for w in report.warnings]
    for doc in schemas.validate_documents(report.source.documents.values()):
        if not doc.approximate:
            found += [Finding("format", level, f"{doc.path}: {e}") for e in doc.errors]
            continue
        # Desktop writes schema versions before Microsoft publishes them. Against the older
        # vendored schema, a newer *property* shows up as "Additional properties are not
        # allowed": that's probably fine. Any other error (a wrong type, a missing required
        # key) is wrong in every version, so it stays at full severity.
        newer = [e for e in doc.errors if "Additional properties are not allowed" in e]
        found += [Finding("format", level, f"{doc.path}: {e}") for e in doc.errors if e not in newer]
        if newer:
            listed = "; ".join(newer[:3]) + ("; …" if len(newer) > 3 else "")
            found.append(Finding("format", "warning",
                f"{doc.path}: {len(newer)} unknown propert{'y' if len(newer) == 1 else 'ies'} "
                f"against schema {doc.used}, but the file declares {doc.declared}, which isn't "
                f"vendored yet. Probably newer properties: vendor {doc.declared} with "
                f"scripts/vendor_schemas.py once Microsoft publishes it. ({listed})"))
    return found


def _ordered(report: Report, findings: list[Finding]) -> list[Finding]:
    index = {p.name: i for i, p in enumerate(report.pages)}
    return sorted(findings, key=lambda f: (-1 if f.page is None else index.get(f.page, 1 << 30),
                                           f.visual or "", f.rule, f.message))


def to_text(report: Report, rules: Guidelines, result: CheckResult) -> str:
    layers = " < ".join(rules.sources)
    lines = [f"Report:     {report.root.name}",
             f"Guidelines: {rules.name or '(unnamed)'} v{rules.version}  [{layers}]", ""]
    names = {p.name: p.display_name for p in report.pages}
    current = object()
    for f in _ordered(report, result.findings):
        if f.page != current:
            current = f.page
            header = "Report" if f.page is None else f"{names.get(f.page, f.page)} ({f.page})"
            lines.append(header)
        target = f.visual or "(page)" if f.page is not None else ""
        lines.append(f"  {f.severity:<7}  {f.rule:<9}  {target:<18}  {f.message}".rstrip())
    if result.findings:
        lines.append("")
    for n in result.notes:
        lines.append(f"note: {n}")
    errors = sum(f.severity == "error" for f in result.findings)
    warnings = sum(f.severity == "warning" for f in result.findings)
    lines.append(f"{errors} error(s), {warnings} warning(s) across {len(report.pages)} page(s)")
    return "\n".join(lines)


def to_json(report: Report, rules: Guidelines, result: CheckResult) -> str:
    return json.dumps({
        "report": report.root.name,
        "guidelines": {"name": rules.name, "version": rules.version, "sources": list(rules.sources)},
        "findings": [asdict(f) for f in _ordered(report, result.findings)],
        "notes": result.notes,
        "errors": sum(f.severity == "error" for f in result.findings),
        "warnings": sum(f.severity == "warning" for f in result.findings),
    }, indent=2, ensure_ascii=False)


# GitHub's documented cap per step and type (actions/toolkit docs/problem-matchers.md); the job
# allows 50 in all.
GITHUB_ANNOTATIONS_PER_STEP = 10


def _escape(text: str, prop: bool = False) -> str:
    """Escape a workflow command's message (or, with ``prop``, a property value)."""
    text = text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    return text.replace(":", "%3A").replace(",", "%2C") if prop else text


def _finding_file(report: Report, f: Finding, workspace: Path) -> str | None:
    """The finding's visual.json (or page.json), relative to the workspace; None if outside it."""
    if f.page is None:
        return None
    try:
        page = report.page(f.page)
    except KeyError:
        return None
    obj = next((v for v in page.visuals if v.name == f.visual), None) if f.visual else page
    if obj is None or obj.source is None:
        return None
    path = Path(os.path.abspath(report.root / obj.source.path))
    try:
        return path.relative_to(workspace).as_posix()
    except ValueError:
        return None


def to_github(report: Report, rules: Guidelines, result: CheckResult) -> str:
    """One workflow command per finding (error/warning) and note (notice), then the text report.
    Files are relative to $GITHUB_WORKSPACE (else the current directory), as GitHub expects."""
    workspace = Path(os.path.abspath(os.environ.get("GITHUB_WORKSPACE") or os.getcwd()))
    names = {p.name: p.display_name for p in report.pages}
    lines = []
    for f in _ordered(report, result.findings):
        props = [f"title={_escape(f'bp check: {f.rule}', prop=True)}"]
        file = _finding_file(report, f, workspace)
        if file:
            props.insert(0, f"file={_escape(file, prop=True)}")
        where = "" if f.page is None else f"{names.get(f.page, f.page)}"
        where += f" / {f.visual}" if f.visual else ""
        message = f"{where}: {f.message}" if where else f.message
        lines.append(f"::{f.severity} {','.join(props)}::{_escape(message)}")
    hidden = {s: n - GITHUB_ANNOTATIONS_PER_STEP for s in ("error", "warning")
              if (n := sum(f.severity == s for f in result.findings)) > GITHUB_ANNOTATIONS_PER_STEP}
    if hidden:  # GitHub drops the rest without saying so; the full report is in the log and summary
        lines.append("::notice title=bp check::GitHub shows at most "
                     f"{GITHUB_ANNOTATIONS_PER_STEP} error and {GITHUB_ANNOTATIONS_PER_STEP} warning "
                     "annotations per step, so "
                     + " and ".join(f"{n} more {s}(s)" for s, n in hidden.items())
                     + " aren't annotated: see the full report in the log or the job summary")
    for n in result.notes:
        lines.append(f"::notice title=bp check::{_escape(n)}")
    return "\n".join(lines + [to_text(report, rules, result)])


def exit_code(result: CheckResult, strict: bool) -> int:
    failing = {"error", "warning"} if strict else {"error"}
    return 1 if any(f.severity in failing for f in result.findings) else 0


def run(args: argparse.Namespace) -> int:
    report, rules, result = run_check(args)
    render = to_json if args.json else to_github if args.github else to_text
    print(render(report, rules, result))
    return exit_code(result, args.strict)
