"""Build the Desktop probe that saves `bp apply`'s legend column, legend off and totals (probe 33).

Usage:
    python scripts/probe_apply_legend_totals.py <dest folder> <data cache .abf>

Probe 32 showed Desktop draws and keeps these shapes when they are written **by hand** as
candidates. Blueprint now writes them (a `legend` slot on column and bar, `legend: off`, table
`totals`), which is a different claim: that Desktop accepts **what Blueprint wrote**. Same bar as
probe 21 after 20, 24 after 22/23 and 30 after 29. Nothing here is patched: every visual is
built by `bp apply` from specs, on the demo's model (so the demo's data cache fits and a Legend
can be Region or Order Date).

PREDICTIONS (written before the probe is opened):

 A1  Every visual draws exactly as its probe-32 candidate did: a Legend column side by side on the
     clustered column and bar (also beside a drill-down), `legend: off` hides the legend on a
     column, a bar and a line chart, `legend: top` shows it on top, no option shows it at the
     bottom, and the table with `totals: "off"` has no Total row (the other two show Total 500).
     No Desktop error anywhere.
 A2  A real refresh + Ctrl+S keeps every Blueprint-written `Series` projection (no `active`
     added), `objects.legend` (`position` or `show`, never both from one option) and
     `objects.total` as written. At most Desktop raises a file's `$schema` 2.13.0 -> 2.14.0, adds
     its usual condition-less auto `filterConfig`, and rewrites `pages.json` `activePageName`
     (what it did in probes 24 and 30). It drops or rewrites no `show`, `position`, `totals`
     or `Series` property.
 A3  Re-running the same specs on the saved report changes nothing but the manifest.
 A4  Editing one chart's spec from `legend: off` to `legend: top` and re-applying rewrites only
     that visual: `show` is gone, `position: 'Top'` is there. Desktop, reloaded through the bridge,
     draws that chart's legend on top and reports no error (the flip leaves nothing hidden).

All content is invented.
"""

import shutil
import sys
from pathlib import Path

from _probe import git, make_probe
from probe_apply_charts import DATE_COLUMN
from probe_apply_hierarchy import HIERARCHY

from blueprint.cli import main as bp

ROOT = Path(__file__).resolve().parent.parent
MEASURE = ("\tmeasure 'Target Amount' = 600\r\n\t\tformatString: 0\r\n"  # as scripts/demo.sh
           "\t\tlineageTag: 9ab090f9-bd7f-43c4-82be-86470a46784b\r\n\r\n")

ONE = '{category: "Sales[Country]", value: "[Total Amount]", legend: "Sales[Region]"}'
DRILL = '{category: ["Sales[Country]", "Sales[Region]"], value: "[Total Amount]", legend: "Sales[Order Date]"}'
TWO = '{category: "Sales[Country]", value: ["[Total Amount]", "[Target Amount]"]}'
COLS = '{columns: ["Sales[Country]", "Sales[Region]", "[Total Amount]"]}'


def page(name: str, rows: list[str]) -> str:
    return (f"page: {name}\nlayout: grid-2x3\nvisuals:\n  - {{type: header, title: {name}}}\n"
            + "".join(f"  - {row}\n" for row in rows))


def flip(option: str) -> str:
    return (f'{{type: column, id: flip, title: "Off then top", options: {{legend: {option}}}, '
            f'slots: {TWO}}}')


SPECS = {
    "legend-binding.yaml": page("Legend Binding", [
        f"{{type: column, id: lb-col, title: Column + legend, slots: {ONE}}}",
        f"{{type: bar, id: lb-bar, title: Bar + legend, slots: {ONE}}}",
        f"{{type: column, id: lb-col-drill, title: Column drill + legend, slots: {DRILL}}}",
        f"{{type: bar, id: lb-bar-drill, title: Bar drill + legend, slots: {DRILL}}}",
        f"{{type: column, id: lb-col-bottom, title: Column + legend bottom, options: {{legend: bottom}}, slots: {ONE}}}",
        f"{{type: line, id: lb-line, title: Line + legend, options: {{legend: right}}, slots: {ONE}}}"]),
    "legend-show.yaml": page("Legend Show", [
        f'{{type: column, id: ls-col-off, title: Column legend off, options: {{legend: "off"}}, slots: {TWO}}}',
        f'{{type: bar, id: ls-bar-off, title: Bar legend off, options: {{legend: "off"}}, slots: {TWO}}}',
        f'{{type: line, id: ls-line-off, title: Line legend off, options: {{legend: "off"}}, slots: {TWO}}}',
        f"{{type: column, id: ls-col-top, title: Column legend top, options: {{legend: top}}, slots: {TWO}}}",
        f"{{type: column, id: ls-col-default, title: No legend option, slots: {TWO}}}",
        flip('"off"')]),
    "table-totals.yaml": page("Table Totals", [
        f'{{type: table, id: tt-off, title: Totals off, options: {{totals: "off"}}, slots: {COLS}}}',
        f'{{type: table, id: tt-on, title: Totals on, options: {{totals: "on"}}, slots: {COLS}}}',
        f"{{type: table, id: tt-default, title: No totals option, slots: {COLS}}}"]),
}

STEPS = """\
# Probe 33: Desktop's save of bp apply's legend column, legend off and table totals

Blueprint built **Legend Binding**, **Legend Show** and **Table Totals** from specs, with nothing
patched by hand. Claude opens the report through the bridge and captures the pages; you only:

1. Click **Refresh now** on the banner (or **Home -> Refresh**), then **Ctrl+S**.

Never click a value inside a visual, and don't open a field's menu: this probe is about what
Desktop does with what Blueprint wrote, untouched. Tell Claude when it is saved; Claude then
re-applies the specs (once edited: one chart from `legend: off` to `legend: top`) and reloads.

What it settles: whether Desktop draws and keeps what Blueprint wrote (a Legend `Series`,
`legend.show`, `total.totals`), and whether the off -> top flip leaves the legend visible.
"""

if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    dest, cache = Path(sys.argv[1]), Path(sys.argv[2])
    make_probe(ROOT / "fixtures" / "02-card-and-chart", dest, STEPS, snap=True)
    tmdl = dest / "Fixture.SemanticModel" / "definition" / "tables" / "Sales.tmdl"
    text = tmdl.read_bytes().decode()
    text = text.replace("\tcolumn Country", MEASURE + "\tcolumn Country", 1)
    text = text.replace("\tpartition Sales = m", DATE_COLUMN + HIERARCHY + "\tpartition Sales = m", 1)
    tmdl.write_bytes(text.encode())
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "model: the demo's (Target Amount, Order Date, Geography)")

    specs = dest / "specs"
    specs.mkdir()
    for name, body in SPECS.items():
        (specs / name).write_text(body, encoding="utf-8")
    if bp(["apply", str(specs), "--report", str(dest),
           "--guidelines", str(ROOT / "guidelines" / "example.yaml")]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: apply specs/ (legend-binding, legend-show, table-totals)")

    shutil.copy2(cache, dest / "Fixture.SemanticModel" / ".pbi" / "cache.abf")
    print(f"data cache copied from {cache}\nProbe ready: {dest}")
