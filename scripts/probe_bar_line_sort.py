"""Build the Desktop probe for the core charts' options and an explicit sort (probe 31).

Usage:
    python scripts/probe_bar_line_sort.py <dest folder>

Two gaps in the core seven's "basic richness":

- **Options on bar and line.** Probe 23 verified `objects.labels[0].properties.show = true` and
  `objects.legend[0].properties.position` on the column chart and the stacked charts, never on the
  clustered **bar** or the **line**. So today `column` has both options and the two other core
  chart types have none — an accident of probe history, not a decision. This probe writes the same
  shapes onto a bar and a line as **candidates** (as probes 22/23 did), for Desktop to draw.

- **An explicit sort.** `query.sortDefinition` is `{"sort": [{"field": …, "direction":
  "Ascending"|"Descending"}], "isDefaultSort": true}` — but every example so far is the sort
  *Desktop* adds by itself (`isDefaultSort: true`). What a user's own "Sort axis" choice writes is
  unverified: whether `isDefaultSort` goes away, turns false, or stays. Blueprint can't own a sort
  until that's known, and today `render.with_bindings` keeps a sort only while its fields are
  bound, so a user's sort is discarded whenever the fields change.

Uses fixture 02 (table Sales: Region, Country, Amount; measure Total Amount). All invented.
"""

import sys
from pathlib import Path

from _probe import git, make_probe

from blueprint.cli import main as bp
from blueprint.pbir import jsonfmt, render

ROOT = Path(__file__).resolve().parent.parent

SPEC = """\
page: Options And Sort
layout: grid-2x3
visuals:
  - {type: header, title: Options And Sort}
  - {type: card, title: Total, slots: {value: "[Total Amount]"}}
  - {type: bar, title: Bar labels legend, slots: {category: "Sales[Country]", value: ["[Total Amount]", "[Target Amount]"]}}
  - {type: line, title: Line labels legend, slots: {category: "Sales[Country]", value: ["[Total Amount]", "[Target Amount]"]}}
  - {type: column, title: Column to sort, slots: {category: "Sales[Country]", value: "[Total Amount]"}}
  - {type: table, title: Table to sort, slots: {columns: ["Sales[Country]", "Sales[Region]", "[Total Amount]"]}}
"""

# The literals probe 23 verified on the column chart, written here onto a bar and a line.
CANDIDATES = {"bar": [("labels", "show", "true"), ("legend", "position", "'Right'")],
              "line": [("labels", "show", "true"), ("legend", "position", "'Top'")]}

STEPS = """\
# Probe 31: labels and legend on bar and line, and an explicit sort

Blueprint built **Options And Sort**, then wrote probe 23's option shapes onto the **bar** and the
**line** by hand (candidates: no contract ships them yet). Claude reloads through the bridge and
captures the page, so step 1 is only about Desktop keeping them through a save.

| # | In Power BI Desktop | Then run |
|---|---|---|
| 1 | Click **Refresh now** on the banner (or **Home → Refresh**), then **Ctrl+S**. Change nothing else. | `bash snap.sh "01 refresh and save"` |
| 2 | On **Column to sort**: the visual's **...** menu → **Sort axis** → **Total Amount**, then **...** → **Sort axis** → **Sort descending**. **Ctrl+S**. | `bash snap.sh "02 column sorted by measure desc"` |
| 3 | On **Table to sort**: click the **Country** column header once (ascending). **Ctrl+S**. | `bash snap.sh "03 table sorted by column asc"` |
| 4 | On **Column to sort**: **...** → **Sort axis** → **Country**, then **Sort ascending** — back to what Desktop would have chosen itself. **Ctrl+S**. | `bash snap.sh "04 column sorted back to category asc"` |

Then close Desktop and tell Claude "probe 31 done", with:
- whether the **bar** showed data labels and a legend on the right, and the **line** data labels
  and a legend on top (or what it did instead);
- anything Desktop refused or moved on its own.

What the diff settles:
- whether Desktop keeps `objects.labels`/`objects.legend` on a clustered bar and a line as written;
- what an explicit sort writes in `query.sortDefinition`, and what happens to `isDefaultSort`;
- whether sorting back to the default restores `isDefaultSort: true` or leaves an explicit sort.
"""

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    dest = Path(sys.argv[1])
    make_probe(ROOT / "fixtures" / "02-card-and-chart", dest, STEPS, snap=True)

    # the measure probe 20 added, so a chart can carry two measures and show a legend
    tmdl = dest / "Fixture.SemanticModel" / "definition" / "tables" / "Sales.tmdl"
    measure = ("\tmeasure 'Target Amount' = 600\r\n\t\tformatString: 0\r\n"
               "\t\tlineageTag: 9ab090f9-bd7f-43c4-82be-86470a46784b\r\n\r\n")
    text = tmdl.read_bytes().decode()
    tmdl.write_bytes(text.replace("\tcolumn Country", measure + "\tcolumn Country", 1).encode())
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "model: add measure Target Amount (as Desktop wrote it in probe 20)")

    spec = dest / "options-and-sort.yaml"
    spec.write_text(SPEC, encoding="utf-8")
    if bp(["apply", str(spec), "--report", str(dest),
           "--guidelines", str(ROOT / "guidelines" / "example.yaml")]) != 0:
        sys.exit(1)
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "blueprint: apply options-and-sort.yaml")

    # candidate option shapes on the two types no probe has covered
    patched = []
    for path in sorted((dest / "Fixture.Report" / "definition" / "pages").rglob("visual.json")):
        doc = jsonfmt.load(path)
        vtype = doc.get("visual", {}).get("visualType")
        kind = {"clusteredBarChart": "bar", "lineChart": "line"}.get(vtype)
        if kind is None:
            continue
        for obj, prop, literal in CANDIDATES[kind]:
            doc = render.with_option(doc, obj, prop, literal)
        path.write_bytes(jsonfmt.dump_bytes(doc))
        patched.append(kind)
    assert sorted(patched) == ["bar", "line"], patched
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "probe: candidate labels/legend options on the bar and the line")
    print(f"Probe ready: {dest}")
