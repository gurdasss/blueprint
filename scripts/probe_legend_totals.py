"""Build the Desktop probe for the legend binding, legend show/hide and table totals (probe 32).

Usage:
    python scripts/probe_legend_totals.py <dest folder> <data cache .abf>

Three gaps in the core seven's "basic richness", ranked by a survey of two real reports (48
visuals; counts only, nothing from them is kept): a Legend column on a clustered chart (3 of 6
clustered column/bar charts have one), `legend.show = false` (5 of 18 legends), and the table's
`total.totals` (set on 2 of 2 tables, once to false). Nothing here has been probed: probes 22/28
put a Legend column only on the *stacked*, line and area charts, probe 28's clustered column used
a legend of *measure names*, and no probe has touched `legend.show` or a table total.

Like probes 22, 23 and 28 it writes **candidate** shapes (opened and reloaded through the bridge,
one page capture per round), then asks the user for one refresh + save to see whether Desktop
keeps them as written (the probe 24 / 31 method). The model is the demo's (fixture 02 + Target
Amount + Order Date + the Geography hierarchy), so the demo's refreshed data cache fits it.

PREDICTIONS (written before the probe is opened; the survey's real reports are the basis):

 P1  A Legend column on a **clustered column** and a **clustered bar**: Desktop draws one colour
     per Legend value, side by side, and keeps `queryState.Series.projections = [{field: Column
     Sales.Region, queryRef "Sales.Region", nativeQueryRef "Region"}]` as written: no `active`
     (the stacked charts and line have none either, probe 22), roles alphabetical (Category,
     Series, Y), `visualType` unchanged. Same on both types.
 P2  A drill-down `Category` (Country, Region) together with a Legend (Order Date) draws on both,
     as on the stacked charts (probe 28): the axis expanded, one colour per Legend value.
 P3  Two measures together with a Legend column: Desktop **refuses** ("There's too many columns
     in the Legend bucket"), on the clustered charts as on line and stacked (probe 28). This is
     the one prediction I'm least sure of: probe 28 showed it for stacked, area, 100%; the clustered
     charts were never tried with a column Legend.
 P4  A second Legend column (Region and Order Date): refused with the same error (as line, probe 27).
 P5  `objects.legend[0].properties.show = false` hides the legend on a clustered column, a clustered
     bar and a line chart (each with two measures, so a legend of measure names would otherwise
     show) and is kept as written. `position` alongside it is also kept. `show = true` written
     explicitly is kept too (the real reports write both `position` and `show`).
 P6  `objects.total[0].properties.totals = false` removes the table's Total row; `true` written
     explicitly keeps it; a table with no `total` object shows the Total row (Desktop's default).
     All three shapes survive a save untouched, apart from what any save does ($schema bump to
     2.14.0, a condition-less auto filterConfig, pages.json activePageName).

All content is invented.
"""

import shutil
import sys
from pathlib import Path

from _probe import git, make_probe
from probe_apply_charts import DATE_COLUMN
from probe_apply_hierarchy import HIERARCHY
from probe_chart_variants import REGION, spec_id

from blueprint.cli import main as bp
from blueprint.pbir import jsonfmt

ROOT = Path(__file__).resolve().parent.parent
MEASURE = ("\tmeasure 'Target Amount' = 600\r\n\t\tformatString: 0\r\n"  # as scripts/demo.sh
           "\t\tlineageTag: 9ab090f9-bd7f-43c4-82be-86470a46784b\r\n\r\n")
ORDER_DATE = {"field": {"Column": {"Expression": {"SourceRef": {"Entity": "Sales"}}, "Property": "Order Date"}},
              "queryRef": "Sales.Order Date", "nativeQueryRef": "Order Date"}

ONE = '{category: "Sales[Country]", value: "[Total Amount]"}'
DRILL = '{category: ["Sales[Country]", "Sales[Region]"], value: "[Total Amount]"}'
TWO = '{category: "Sales[Country]", value: ["[Total Amount]", "[Target Amount]"]}'
COLS = '{columns: ["Sales[Country]", "Sales[Region]", "[Total Amount]"]}'


def page(name: str, title: str, rows: list[tuple[str, str, str, str]]) -> str:
    lines = [f"page: {name}", "layout: grid-2x3", "visuals:", f"  - {{type: header, title: {title}}}"]
    lines += [f"  - {{type: {t}, id: {sid}, title: {ttl}, slots: {slots}}}" for sid, t, ttl, slots in rows]
    return "\n".join(lines) + "\n"


SPECS = {
    "legend-binding.yaml": page("Legend Binding", "Legend column on clustered charts", [
        ("lb-col", "column", "Column + legend", ONE), ("lb-bar", "bar", "Bar + legend", ONE),
        ("lb-col-drill", "column", "Column drill + legend", DRILL), ("lb-bar-drill", "bar", "Bar drill + legend", DRILL),
        ("lb-col-measures", "column", "Column 2 measures + legend", TWO), ("lb-col-two", "column", "Column 2 legend columns", ONE)]),
    "legend-show.yaml": page("Legend Show", "legend show and hide", [
        ("ls-col-hide", "column", "Column legend hidden", TWO), ("ls-bar-hide", "bar", "Bar legend hidden", TWO),
        ("ls-line-hide", "line", "Line legend hidden", TWO), ("ls-col-hide-right", "column", "Hidden + Right", TWO),
        ("ls-col-show-top", "column", "Show true + Top", TWO), ("ls-col-default", "column", "No legend object", TWO)]),
    "table-totals.yaml": page("Table Totals", "table totals", [
        ("tt-off", "table", "Totals false", COLS), ("tt-on", "table", "Totals true", COLS),
        ("tt-default", "table", "No total object", COLS)]),
}


def lit(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


def props(**kw: str) -> list[dict]:
    return [{"properties": {k: lit(v) for k, v in sorted(kw.items())}}]  # alphabetical, as Desktop writes


# spec id -> (Legend projections to add as Series, visual.objects to set or None)
CANDIDATES = {
    "lb-col": ([REGION], None), "lb-bar": ([REGION], None),
    "lb-col-drill": ([ORDER_DATE], None), "lb-bar-drill": ([ORDER_DATE], None),
    "lb-col-measures": ([REGION], None), "lb-col-two": ([REGION, ORDER_DATE], None),
    "ls-col-hide": ([], {"legend": props(show="false")}),
    "ls-bar-hide": ([], {"legend": props(show="false")}),
    "ls-line-hide": ([], {"legend": props(show="false")}),
    "ls-col-hide-right": ([], {"legend": props(position="'Right'", show="false")}),
    "ls-col-show-top": ([], {"legend": props(position="'Top'", show="true")}),
    "tt-off": ([], {"total": props(totals="false")}),
    "tt-on": ([], {"total": props(totals="true")}),
}

STEPS = """\
# Probe 32: legend binding on clustered charts, legend show/hide, table totals

Blueprint built three pages (**Legend Binding**, **Legend Show**, **Table Totals**) and changed
visuals to candidates. Claude opens the report through the bridge, reloads and captures each page,
and commits each step. Nothing for you to do until Claude says the captures are done; then:

| # | In Power BI Desktop | Then run |
|---|---|---|
| 1 | Click **Refresh now** on the banner (or **Home -> Refresh**), then **Ctrl+S**. Change nothing else. | `bash snap.sh "02 refresh and save"` |

Then close Desktop and tell Claude "probe 32 done", with anything Desktop refused or moved.

What the diff settles: whether Desktop keeps each candidate as written through a save (a Legend
`Series` on a clustered column and bar, `legend.show`, `total.totals`), and what it adds around them.
"""


def make_candidates(report: Path) -> list[str]:
    changed = []
    for f in sorted(report.glob("definition/pages/*/visuals/*/visual.json")):
        doc = jsonfmt.load(f)
        sid = spec_id(doc)
        if sid not in CANDIDATES:
            continue
        legend, objects = CANDIDATES[sid]
        body = doc["visual"]
        if legend:
            state = body["query"]["queryState"]
            state["Series"] = {"projections": [dict(p) for p in legend]}
            body["query"]["queryState"] = {role: state[role] for role in sorted(state)}  # alphabetical
        if objects:
            body["objects"] = {**body.get("objects", {}), **objects}
        f.write_bytes(jsonfmt.dump_bytes(doc))
        changed.append(f"{sid} ({body['visualType']})"
                       f"{' + Legend ' + ', '.join(p['nativeQueryRef'] for p in legend) if legend else ''}"
                       f"{' + objects ' + ', '.join(objects) if objects else ''}")
    return changed


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
    guide = str(ROOT / "guidelines" / "example.yaml")
    for name, body in SPECS.items():
        (specs / name).write_text(body, encoding="utf-8")
    if bp(["apply", str(specs), "--report", str(dest), "--guidelines", guide]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: apply specs/ (verified shapes only)")

    print("\n".join(make_candidates(dest / "Fixture.Report")))
    if bp(["manifest", "--report", str(dest), "--guidelines", guide]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "probe: candidate Legend columns, legend.show and total.totals")

    shutil.copy2(cache, dest / "Fixture.SemanticModel" / ".pbi" / "cache.abf")
    print(f"data cache copied from {cache}\nProbe ready: {dest}")
