"""Replay every Desktop probe built on fixture 02 (05-15) and test Blueprint against what Desktop
actually wrote, from several angles.

Each evidence file (docs/probes/NN-*.diff, written by scripts/probe_evidence.py) holds one
`######## <step>` section per commit after the probe's baseline. Applying the sections in order
to a copy of fixtures/02-card-and-chart rebuilds the report exactly as it stood after each step:
Desktop's own saves ("01 open and save", …) and the Blueprint runs between them ("blueprint: …").

Angles, each over every probe or step it applies to:

- format: every JSON file round-trips through jsonfmt byte for byte, and `bp check` finds no
  format errors;
- reading: no reader warnings, and every field projection Desktop wrote is read (none dropped);
- model: every bound field resolves against the probe's own semantic model;
- rendering: for each Desktop-made visual of a type Blueprint ships, rendering the same bindings
  gives Desktop's queryState (drill `active` state aside), in Desktop's role order;
- what the user saw: fonts, theme defaults and well contents the user reported;
- Desktop saves: Blueprint's annotations survive every one, and re-applying the specs afterwards
  changes nothing;
- fmt: idempotent on every probe, moves only positions, and `check` passes its grid;
- theme: `bp theme` reproduces the theme file Desktop accepted, byte for byte.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

from blueprint import guidelines, manifest
from blueprint.cli import main
from blueprint.commands import check as check_cmd
from blueprint.model import Rect
from blueprint.pbir import formatting, jsonfmt, render, semantic
from blueprint.pbir.reader import read_report
from blueprint.slots import contracts
from blueprint.validate import check_report, effective_theme, theme_font

ROOT = Path(__file__).resolve().parent.parent
PROBES = ROOT / "docs" / "probes"
FIXTURE = ROOT / "fixtures" / "02-card-and-chart"
GUIDE = ROOT / "guidelines" / "example.yaml"
# Probes 11 and 20-24, 27-28 built pie, donut, slicer, matrix, area and the stacked charts, which
# are archived out of the core seven. The replays are Desktop's evidence for those shapes, so they
# opt the archive back in exactly as a client would (`--visuals`, or
# extensions.custom_visuals.search_path in guidelines).
ARCHIVE = ROOT / "blueprint" / "visuals" / "archive"
VISUALS = ("--visuals", str(ARCHIVE))


def _rules(path=GUIDE):
    """``path`` loaded with the archived visual types opted in."""
    return guidelines.load(path, visuals=[ARCHIVE])
REPLAYED = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 26, 27, 28, 29, 30, 31, 32, 33]
# Probes whose report Blueprint built and Desktop then opened and saved.
ACCEPTANCE = [5, 6, 9, 14, 17, 19, 21, 22, 23, 24, 26, 27, 28, 30, 31, 32, 33]

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git to apply the evidence")


@dataclass(frozen=True)
class Step:
    probe: int
    index: int
    name: str
    root: Path  # the project folder (Fixture.pbip, Fixture.Report, Fixture.SemanticModel, …)

    @property
    def by_desktop(self) -> bool:
        return self.name[:2].isdigit()

    @property
    def report(self) -> Path:
        return self.root / "Fixture.Report"

    def __str__(self) -> str:
        return f"{self.probe:02d}/{self.name}"


def _evidence(probe: int) -> Path:
    [path] = PROBES.glob(f"{probe:02d}-*.diff")
    return path


def _sections(path: Path) -> list[tuple[str, bytes]]:
    parts = re.split(rb"^######## (.*)$", path.read_bytes(), flags=re.MULTILINE)
    return [(parts[i].decode().strip(), parts[i + 1]) for i in range(1, len(parts), 2)]


@pytest.fixture(scope="session")
def replays(tmp_path_factory) -> dict[int, list[Step]]:
    """Every probe, rebuilt step by step; each step's state in its own folder."""
    out: dict[int, list[Step]] = {}
    for probe in REPLAYED:
        work = tmp_path_factory.mktemp(f"probe{probe:02d}") / "work"
        shutil.copytree(FIXTURE, work)
        subprocess.run(["git", "init", "-q", str(work)], check=True)
        steps = []
        for i, (name, patch) in enumerate(_sections(_evidence(probe))):
            if patch.strip(b"\r\n"):
                done = subprocess.run(["git", "-C", str(work), "apply", "--whitespace=nowarn", "-"],
                                      input=patch, capture_output=True, check=False)
                assert done.returncode == 0, f"probe {probe} step {name!r}: {done.stderr.decode()}"
            snap = work.parent / f"{i:02d}"
            shutil.copytree(work, snap, ignore=shutil.ignore_patterns(".git"))
            steps.append(Step(probe, i, name, snap))
        out[probe] = steps
    return out


def _last(replays, probe: int) -> Step:
    return replays[probe][-1]


def _all_steps(replays) -> list[Step]:
    return [s for probe in REPLAYED for s in replays[probe]]


def _visual_docs(report: Path) -> list[dict]:
    return [jsonfmt.load(f) for f in sorted(report.glob("definition/pages/*/visuals/*/visual.json"))]


def _copy(step: Step, tmp_path: Path) -> Path:
    dest = tmp_path / "proj"
    shutil.copytree(step.root, dest)
    return dest


def test_every_probe_replays(replays):
    for probe in REPLAYED:
        steps = replays[probe]
        assert steps, f"probe {probe}: no steps in {_evidence(probe).name}"
        assert any(s.by_desktop for s in steps), f"probe {probe}: no Desktop save recorded"


# --- format --------------------------------------------------------------------------------


@pytest.mark.parametrize("probe", REPLAYED)
def test_every_json_file_round_trips_byte_for_byte(replays, probe):
    for step in replays[probe]:
        for f in sorted(step.report.rglob("*.json")):
            if f.name == manifest.FILE:
                continue  # Blueprint's own file, not PBIR
            data = f.read_bytes()
            assert jsonfmt.dump_bytes(jsonfmt.loads_bytes(data)) == data, f"{step}: {f.relative_to(step.root)}"


@pytest.mark.parametrize("probe", REPLAYED)
def test_no_format_errors(replays, probe):
    for step in replays[probe]:
        args = argparse.Namespace(report=step.report, grid=None, guidelines=GUIDE)
        _, _, result = check_cmd.run_check(args)
        errors = [f.message for f in result.findings if f.rule == "format" and f.severity == "error"]
        assert errors == [], str(step)


# --- reading -------------------------------------------------------------------------------


def _projection_count(doc: dict) -> dict[str, int]:
    state = ((doc.get("visual") or {}).get("query") or {}).get("queryState") or {}
    return {role: len(entry.get("projections") or []) for role, entry in state.items()}


@pytest.mark.parametrize("probe", REPLAYED)
def test_every_projection_is_read(replays, probe):
    for step in replays[probe]:
        report = read_report(step.report)
        assert report.warnings == [], str(step)
        for page in report.pages:
            for v in page.visuals:
                read = {role: len(fs) for role, fs in v.fields.items()}
                assert read == _projection_count(v.source.data), f"{step}: {v.visual_type} {v.name}"


# --- model ---------------------------------------------------------------------------------


@pytest.mark.parametrize("probe", REPLAYED)
def test_bound_fields_resolve_against_the_probes_model(replays, probe):
    for step in replays[probe]:
        report = read_report(step.report)
        pbir = report.source.documents[Path("definition.pbir")].data
        model = semantic.load(semantic.model_dir_for(report.root, pbir))
        for page in report.pages:
            for v in page.visuals:
                for fields in v.fields.values():
                    for f in fields:
                        if f.kind == "measure":
                            assert model.measure_table(f.name) == f.table, f"{step}: {f}"
                        elif f.kind == "hierarchy_level":
                            model.check_hierarchy_level(f.table, f.name, f.level)
                        else:  # column, aggregation, date_level: all over a model column
                            model.check_column(f.table, f.name)


# --- rendering -----------------------------------------------------------------------------


def _without_active(state: dict) -> dict:
    """``state`` with each ``active`` value blanked: its value is drill view state (probes 11, 12),
    but whether a projection carries it at all is Desktop's convention (Category roles only)."""
    return {role: {**entry, "projections": [{k: (None if k == "active" else v) for k, v in p.items()}
                                            for p in entry["projections"]]}
            for role, entry in state.items()}


def _desktop_visuals(replays):
    """(step, visual) for every visual Desktop itself created or changed, of a type Blueprint ships,
    bound only to fields a spec can express."""
    shipped = {c.visual_type: c for c in contracts((ARCHIVE,)).values()}
    seen = set()
    for step in _all_steps(replays):
        if not step.by_desktop:
            continue
        for page in read_report(step.report).pages:
            for v in page.visuals:
                doc = v.source.data
                if v.visual_type not in shipped or v.spec_id is not None or not v.fields:
                    continue
                if any(f.kind not in ("measure", "column", "hierarchy_level") for fs in v.fields.values() for f in fs):
                    continue
                key = (v.visual_type, jsonfmt.dumps(doc["visual"]["query"]["queryState"]))
                if key not in seen:
                    seen.add(key)
                    yield step, v, shipped[v.visual_type]


def test_rendering_desktops_bindings_gives_desktops_query(replays):
    checked = 0
    for step, v, contract in _desktop_visuals(replays):
        desktop = v.source.data["visual"]["query"]["queryState"]
        assert list(desktop) == sorted(desktop), f"{step}: Desktop's roles not alphabetical"
        roles = {s.role for s in contract.slots.values()}
        assert set(desktop) <= roles, f"{step}: {v.visual_type} role(s) {set(desktop) - roles} have no slot"
        # reversed: a spec may list slots in any order, and Desktop's order must still come out
        bindings = {role: [render.Binding(f.kind, f.table, f.name, f.level) for f in fs]
                    for role, fs in reversed(list(v.fields.items()))}
        ours = render.visual("x", v.visual_type, Rect(0, 0, 10, 10), 0, 0, "s", "r",
                             bindings=bindings)["visual"]["query"]["queryState"]
        assert list(ours) == list(desktop), str(step)
        assert _without_active(ours) == _without_active(desktop), f"{step}: {v.visual_type}"
        checked += 1
    # card + column (fixture), pie/table/kpi (08), kpi with target (10), pie drill + details (11),
    # line, line + legend, bar drill (12), column/table/bar/pie/line on a hierarchy (16, 18),
    assert checked >= 26  # + slicer, matrix, column/bar/line with two measures (20)


# --- what the user saw ---------------------------------------------------------------------


def _slots(step: Step, visual_type: str) -> list[dict]:
    m = manifest.build(read_report(step.report), _rules(), "2026-01-01T00:00:00Z")
    return [v["slots"] for p in m["pages"] for v in p["visuals"]
            if v["visual_type"] == visual_type and not v["managed"]]


def test_07_card_fonts_as_the_user_set_them(replays):
    card = next(d for d in _visual_docs(_last(replays, 7).report) if d["visual"]["visualType"] == "cardVisual")
    fonts = {(f.role, f.family, f.size, f.bold) for f in formatting.fonts_in(card["visual"])}
    assert fonts == {("title", None, 16.0, None), ("callout", "Arial", 28.0, True), ("card_label", None, 14.0, None)}
    # step 01: Desktop showed Segoe UI Semibold 21 and Segoe UI 12 from the base theme
    [base] = read_report(replays[7][0].report).themes
    assert theme_font(base, "callout") == formatting.TextClass("Segoe UI Semibold", 21.0)
    assert theme_font(base, "card_label") == formatting.TextClass("Segoe UI", 12.0)


def test_wells_as_the_user_saw_them(replays):
    # 08: KPI Value/Trend axis, pie Legend/Values, table Columns after the reorder
    assert _slots(_last(replays, 8), "kpi") == [{"Indicator": "[Total Amount]", "TrendLine": "Sales[Country]"}]
    assert _slots(_last(replays, 8), "tableEx") == [{"Values": ["Sales[Country]", "Sales[Region]", "[Total Amount]"]}]
    # 10: the target swapped for a column became "Sum of Amount"
    assert _slots(_last(replays, 10), "kpi") == [{"Goal": "Sum(Sales[Amount])", "Indicator": "[Total Amount]",
                                                   "TrendLine": "Sales[Country]"}]
    # 11: Region moved from the Legend drill-down into Details
    assert _slots(_last(replays, 11), "pieChart") == [{"Category": "Sales[Country]", "Series": "Sales[Region]",
                                                        "Y": "[Total Amount]"}]
    # 13: the date hierarchy's four levels, and Average/Count
    assert _slots(_last(replays, 13), "lineChart") == [{"Category": [f"Sales[Order Date].{lv}" for lv in
                                                                     ("Year", "Quarter", "Month", "Day")],
                                                        "Y": "[Total Amount]"}]
    assert _slots(_last(replays, 13), "tableEx") == [{"Values": ["Sales[Country]", "Average(Sales[Amount])",
                                                                 "Count(Sales[Region])"]}]
    # 16: the Geography hierarchy on a column chart (drill-down), and both its levels in a table
    # although only Region was dragged
    geography = ["Sales[Geography].Country", "Sales[Geography].Region"]
    column = [s for s in _slots(_last(replays, 16), "clusteredColumnChart") if "Sales[Country]" not in str(s)]
    assert column == [{"Category": geography, "Y": "[Total Amount]"}]
    assert _slots(_last(replays, 16), "tableEx") == [{"Values": [*geography, "[Total Amount]"]}]


def test_15_theme_defaults_as_the_user_saw_them(replays):
    theme = effective_theme(read_report(_last(replays, 15).report).themes)
    assert theme_font(theme, "callout") == formatting.TextClass("Segoe UI Light", 32.0)
    assert theme_font(theme, "card_label") == formatting.TextClass("Arial", 14.0)


# --- Desktop saves of Blueprint's output ---------------------------------------------------


def _managed(step: Step) -> set[tuple[str, str]]:
    return {(p.name, v.name) for p in read_report(step.report).pages for v in p.visuals if v.spec_id}


@pytest.mark.parametrize("probe", ACCEPTANCE)
def test_blueprint_annotations_survive_every_desktop_save(replays, probe):
    built: set[tuple[str, str]] = set()
    for step in replays[probe]:
        now = _managed(step)
        if step.by_desktop:
            assert built <= now, f"{step}: lost {built - now}"
        built |= now
    assert built, f"probe {probe}: Blueprint built nothing"


def _pinned_guide(tmp_path: Path) -> Path:
    """GUIDE with tests/pinned-layouts ahead of the shipped layouts on the search path."""
    text = GUIDE.read_text(encoding="utf-8")
    shipped = 'search_path: ["layouts"]'
    assert shipped in text
    dirs = [Path(__file__).parent / "pinned-layouts", GUIDE.parent / "layouts"]
    out = tmp_path / "pinned-guidelines.yaml"
    out.write_text(text.replace(shipped, f"search_path: {[str(d) for d in dirs]}"), encoding="utf-8")
    return out


@pytest.mark.parametrize(("probe", "specs"), [
    # the spec probe 9 was built from, pinned: the shipped example moved off the archived
    # pie type (tests/pinned-specs/README.md)
    (9, [Path(__file__).resolve().parent / "pinned-specs" / "sales-mix.yaml"]),
    (14, ["specs/dates-and-bars.yaml", "specs/pies-and-lines.yaml"]),
    (17, ["specs/geography.yaml"]),
    (19, ["specs/geo-bar-pie.yaml", "specs/geo-line.yaml"]),
    (21, ["specs/slicer-matrix.yaml"]),
    (24, ["specs/saved-variants-1.yaml", "specs/saved-variants-2.yaml"]),
    (26, ["specs/slicer-matrix.yaml"]),
    (33, ["specs/legend-binding.yaml", "specs/legend-show.yaml", "specs/table-totals.yaml"]),
])
def test_reapply_after_desktop_saved_changes_nothing(replays, probe, specs, tmp_path, capsys):
    """Nothing but the manifest: Desktop's save can raise files' $schema versions, which the
    manifest records (probe 17 raised every Blueprint visual from 2.13.0 to 2.14.0). Layouts that
    changed after a probe are pinned to what that probe built (tests/pinned-layouts)."""
    proj = _copy(_last(replays, probe), tmp_path)
    guide = _pinned_guide(tmp_path)
    for spec in specs:
        path = spec if isinstance(spec, Path) else proj / spec
        capsys.readouterr()
        assert main(["apply", str(path), "--report", str(proj), "--guidelines", str(guide), *VISUALS]) == 0
        written = [ln[2:] for ln in capsys.readouterr().out.splitlines() if ln[:2] in ("A ", "M ")]
        assert set(written) <= {manifest.FILE}, f"{probe}: {spec} rewrote {written}"
    names = {name for _, name in _managed(_last(replays, probe))}
    found = check_report(read_report(proj / "Fixture.Report"), _rules(guide)).findings
    assert [f for f in found if f.visual in names] == []


# --- fmt -----------------------------------------------------------------------------------


def _without_positions(report: Path) -> dict[str, object]:
    out = {}
    for f in sorted(report.rglob("*.json")):
        if f.name == manifest.FILE:
            continue
        doc = jsonfmt.load(f)
        if isinstance(doc, dict) and "position" in doc:
            doc = {k: v for k, v in doc.items() if k != "position"}
        out[f.relative_to(report).as_posix()] = doc
    return out


@pytest.mark.parametrize("probe", REPLAYED)
def test_fmt_only_moves_is_idempotent_and_passes_check(replays, probe, tmp_path, capsys):
    proj = _copy(_last(replays, probe), tmp_path)
    report = proj / "Fixture.Report"
    before = _without_positions(report)
    assert main(["fmt", "--report", str(proj), "--guidelines", str(GUIDE)]) == 0
    assert _without_positions(report) == before, "fmt changed something other than position"
    capsys.readouterr()
    assert main(["fmt", "--report", str(proj), "--guidelines", str(GUIDE), "--dry-run"]) == 0
    assert capsys.readouterr().out.startswith("No changes."), "fmt is not idempotent"
    found = check_report(read_report(report), _rules()).findings
    assert [f.message for f in found if f.rule == "grid"] == []


# --- theme ---------------------------------------------------------------------------------

THEME = Path("StaticResources") / "RegisteredResources" / "blueprint-theme.json"


def test_15_bp_theme_reproduces_the_accepted_theme(replays, tmp_path):
    last = _last(replays, 15)
    proj = shutil.copytree(FIXTURE, tmp_path / "proj")
    guide = tmp_path / "g.yaml"
    # the probe's own guidelines (callout/card_label are extension roles in the current schema),
    # plus the label entry the probe added by hand, which bp theme now writes
    probe = yaml.safe_load((last.root / "probe-guidelines.yaml").read_text())
    roles = dict(probe.pop("typography"))
    roles["card_label"] = {"font": "Arial", "size": 14}
    guide.write_text(yaml.safe_dump({**probe, "extensions": {"typography": roles}}))
    assert main(["theme", "--report", str(proj), "--guidelines", str(guide)]) == 0
    assert (proj / "Fixture.Report" / THEME).read_bytes() == (last.report / THEME).read_bytes()


# --- specs binding a hierarchy (probe 16) -------------------------------------------------

HIERARCHY_SPEC = """\
page: Geo
layout: standard-4-up
visuals:
  - type: column
    title: By Geography
    slots: {category: "Sales[Geography]", value: "[Total Amount]"}
  - type: table
    title: Detail
    slots: {columns: ["Sales[Geography]", "[Total Amount]"]}
"""


def _query(report: Path, visual_type: str, managed: bool) -> dict:
    [doc] = [d for d in _visual_docs(report) if d["visual"]["visualType"] == visual_type
             and any(a.get("name") == "blueprint.visual" for a in d.get("annotations", [])) == managed
             and "Sales.Country" not in jsonfmt.dumps(d)]
    return doc["visual"]["query"]["queryState"]


def test_spec_hierarchy_binds_what_desktop_bound(replays, tmp_path, capsys):
    steps = {s.name: s for s in replays[16]}
    proj = _copy(steps["02 create hierarchy Geography"], tmp_path)  # the model has Geography now
    spec = tmp_path / "geo.yaml"
    spec.write_text(HIERARCHY_SPEC)
    args = ["apply", str(spec), "--report", str(proj), "--guidelines", str(GUIDE), *VISUALS]
    assert main(args) == 0
    report = proj / "Fixture.Report"
    # exactly Desktop's queries: the column chart as created in step 03 (first level active, the
    # rest not), the table from step 04 (no "active" at all)
    assert _query(report, "clusteredColumnChart", True) == \
        _query(steps["03 column by Geography"].report, "clusteredColumnChart", False)
    assert _query(report, "tableEx", True) == _query(steps["04 table by one level"].report, "tableEx", False)
    capsys.readouterr()
    assert main(args) == 0  # the levels compare equal on a re-run
    assert capsys.readouterr().out.startswith("No changes.")


@pytest.mark.parametrize(("slot", "match"), [
    ('{type: kpi, slots: {value: "[Total Amount]", trend: "Sales[Geography]"}}',
     "Sales\\[Geography\\] is a hierarchy, but kpi's trend doesn't take one"),
    ('{type: line, slots: {category: "Sales[Country]", value: "[Total Amount]", legend: "Sales[Geography]"}}',
     "Sales\\[Geography\\] is a hierarchy, but line's legend doesn't take one"),
])
def test_spec_hierarchy_refused_where_unverified(replays, tmp_path, capsys, slot, match):
    proj = _copy(replays[16][1], tmp_path)
    spec = tmp_path / "bad.yaml"
    spec.write_text(f"page: Bad\nlayout: standard-4-up\nvisuals:\n  - {slot}\n")
    before = {p: p.read_bytes() for p in proj.rglob("*") if p.is_file()}
    assert main(["apply", str(spec), "--report", str(proj), "--guidelines", str(GUIDE), *VISUALS]) != 0
    assert re.search(match, capsys.readouterr().err)
    assert {p: p.read_bytes() for p in proj.rglob("*") if p.is_file()} == before  # nothing written


@pytest.mark.parametrize(("spec_type", "visual_type", "slots"), [
    ("bar", "clusteredBarChart", '{category: "Sales[Geography]", value: "[Total Amount]"}'),
    ("pie", "pieChart", '{category: "Sales[Geography]", value: "[Total Amount]"}'),
    ("line", "lineChart", '{category: "Sales[Geography]", value: "[Total Amount]"}'),
])
def test_spec_hierarchy_on_bar_pie_line_matches_probe_18(replays, tmp_path, spec_type, visual_type, slots):
    proj = _copy(replays[18][0], tmp_path)  # fixture 02 plus the Geography hierarchy
    spec = tmp_path / f"{spec_type}.yaml"
    spec.write_text(f"page: P\nlayout: standard-4-up\nvisuals:\n  - type: {spec_type}\n    slots: {slots}\n")
    assert main(["apply", str(spec), "--report", str(proj), "--guidelines", str(GUIDE), *VISUALS]) == 0
    # exactly what Desktop wrote when Geography was dragged onto that chart, active flags included
    assert _query(proj / "Fixture.Report", visual_type, True) == _query(_last(replays, 18).report, visual_type, False)


# Probe 20, as a spec. The charts list Target Amount first because Desktop's file does (the user
# reported adding Total first; the acceptance probe settles whether Desktop reorders).
PROBE_20_SPEC = """\
page: P
layout: grid-2x3
visuals:
  - {type: header, title: Probe 20}
  - {type: slicer, slots: {field: ["Sales[Country]", "Sales[Region]"]}}
  - {type: matrix, slots: {rows: "Sales[Country]", columns: "Sales[Region]", values: ["[Total Amount]", "[Target Amount]"]}}
  - {type: column, slots: {category: "Sales[Country]", value: ["[Target Amount]", "[Total Amount]"]}}
  - {type: bar, slots: {category: "Sales[Country]", value: ["[Target Amount]", "[Total Amount]"]}}
  - {type: line, slots: {category: "Sales[Country]", value: ["[Target Amount]", "[Total Amount]"]}}
"""


@pytest.mark.parametrize("visual_type", ["slicer", "pivotTable", "clusteredColumnChart",
                                         "clusteredBarChart", "lineChart"])
def test_20_spec_writes_desktops_queries(replays, tmp_path, visual_type):
    proj = _copy(_last(replays, 20), tmp_path)  # has Target Amount
    spec = tmp_path / "p20.yaml"
    spec.write_text(PROBE_20_SPEC)
    assert main(["apply", str(spec), "--report", str(proj), "--guidelines", str(GUIDE), *VISUALS]) == 0
    fixture_visuals = {d["name"] for d in _visual_docs(FIXTURE / "Fixture.Report")}

    def query(report: Path, managed: bool) -> dict:
        [doc] = [d for d in _visual_docs(report) if d["visual"]["visualType"] == visual_type
                 and any(a.get("name") == "blueprint.visual" for a in d.get("annotations", [])) == managed
                 and d["name"] not in fixture_visuals]
        return doc["visual"]["query"]["queryState"]

    # exactly Desktop's queries, active flags included
    assert query(proj / "Fixture.Report", True) == query(_last(replays, 20).report, False)


def test_20_line_with_a_legend_takes_one_measure(replays, tmp_path, capsys):
    proj = _copy(_last(replays, 20), tmp_path)
    spec = tmp_path / "bad.yaml"
    spec.write_text("page: Bad\nvisuals:\n  - {type: line, slots: {category: \"Sales[Country]\", "
                    "legend: \"Sales[Region]\", value: [\"[Total Amount]\", \"[Target Amount]\"]}}\n")
    assert main(["apply", str(spec), "--report", str(proj), "--guidelines", str(GUIDE), *VISUALS]) == 2
    assert "visuals[0].slots.value: takes one field when legend is set" in capsys.readouterr().err


def test_21_desktop_kept_every_query_blueprint_wrote(replays):
    """Desktop's save (after a data refresh) left each Blueprint query as written, so it doesn't
    reorder Y: the charts keep Total Amount before Target Amount, the order the legend showed."""
    steps = {s.name: s for s in replays[21]}

    def queries(step: Step) -> dict[str, dict]:
        return {d["name"]: d["visual"]["query"]["queryState"] for d in _visual_docs(step.report)
                if any(a.get("name") == "blueprint.visual" for a in d.get("annotations", []))
                and "query" in d["visual"]}

    built = queries(steps["blueprint: apply specs/slicer-matrix.yaml"])
    assert len(built) == 5
    assert queries(steps["01 refresh and save"]) == built
    charts = [q["Y"] for q in built.values() if "Category" in q]
    assert [[p["nativeQueryRef"] for p in y["projections"]] for y in charts] == [["Total Amount", "Target Amount"]] * 3


# Probe 22's candidates, as a spec of the types they became (the slicer's Dropdown isn't a spec
# option yet, so it's left out).
PROBE_22_SPEC = """\
page: V
layout: grid-2x3
visuals:
  - {type: header, title: V}
  - {type: stacked-column, slots: {category: "Sales[Country]", value: "[Total Amount]", legend: "Sales[Region]"}}
  - {type: stacked-column-100, slots: {category: "Sales[Country]", value: "[Total Amount]", legend: "Sales[Region]"}}
  - {type: stacked-bar, slots: {category: "Sales[Country]", value: "[Total Amount]", legend: "Sales[Region]"}}
  - {type: donut, slots: {category: "Sales[Region]", value: "[Total Amount]"}}
  - {type: area, slots: {category: "Sales[Country]", value: "[Total Amount]", legend: "Sales[Region]"}}
"""


def test_22_new_types_write_what_desktop_drew(replays, tmp_path):
    accepted = _last(replays, 22)
    assert accepted.name.startswith("01 opened, all drawn")
    fixture_visuals = {d["name"] for d in _visual_docs(FIXTURE / "Fixture.Report")}
    desktop = {d["visual"]["visualType"]: d["visual"]["query"]["queryState"]
               for d in _visual_docs(accepted.report) if "query" in d["visual"]
               and d["name"] not in fixture_visuals and d["visual"]["visualType"] != "slicer"}
    proj = _copy(accepted, tmp_path)
    spec = tmp_path / "v.yaml"
    spec.write_text(PROBE_22_SPEC)
    assert main(["apply", str(spec), "--report", str(proj), "--guidelines", str(GUIDE), *VISUALS]) == 0
    [page] = [p for p in read_report(proj / "Fixture.Report").pages if p.display_name == "V"]
    ours = {v.visual_type: v.source.data["visual"]["query"]["queryState"] for v in page.visuals
            if v.visual_type != "textbox"}
    assert set(ours) == set(desktop) == {"columnChart", "hundredPercentStackedColumnChart", "barChart",
                                         "donutChart", "areaChart"}
    assert ours == desktop  # active flags included


def test_22_dropdown_option_writes_what_desktop_drew(replays, tmp_path):
    accepted = _last(replays, 22)
    [desktop] = [d for d in _visual_docs(accepted.report) if d["visual"]["visualType"] == "slicer"]
    proj = _copy(accepted, tmp_path)
    spec = tmp_path / "d.yaml"
    spec.write_text("page: D\nlayout: standard-4-up\nvisuals:\n  - {type: header, title: D}\n"
                    "  - {type: slicer, slots: {field: 'Sales[Country]'}, options: {style: dropdown}}\n")
    assert main(["apply", str(spec), "--report", str(proj), "--guidelines", str(GUIDE), *VISUALS]) == 0
    [page] = [p for p in read_report(proj / "Fixture.Report").pages if p.display_name == "D"]
    [ours] = [v.source.data for v in page.visuals if v.visual_type == "slicer"]
    assert ours["visual"]["objects"] == desktop["visual"]["objects"]
    assert ours["visual"]["query"] == desktop["visual"]["query"]


# Probe 23: what Desktop drew in each round, as spec visuals. Key: (round step, the probe's visual
# id); value: the spec visual that must write exactly that visual (query and objects).
P23_ROUND1 = "probe: change visuals to the candidates"
P23_FINAL = "probe: data labels on the stacked bar and stacked column"
PROBE_23 = {
    (P23_ROUND1, "stacked-drill"):
        '{type: stacked-column, slots: {category: ["Sales[Country]", "Sales[Region]"], value: "[Total Amount]"}}',
    (P23_ROUND1, "donut-drill"):
        '{type: donut, slots: {category: ["Sales[Country]", "Sales[Region]"], value: "[Total Amount]"}}',
    (P23_ROUND1, "area-measures"):
        '{type: area, slots: {category: "Sales[Country]", value: ["[Total Amount]", "[Target Amount]"]}}',
    (P23_FINAL, "donut-details"):
        '{type: donut, slots: {category: "Sales[Country]", value: "[Total Amount]", details: "Sales[Region]"}}',
    (P23_FINAL, "stacked-drill"):
        '{type: stacked-column-100, slots: {category: ["Sales[Country]", "Sales[Region]"], value: "[Total Amount]"}}',
    (P23_FINAL, "donut-drill"):
        '{type: stacked-bar, slots: {category: ["Sales[Country]", "Sales[Region]"], value: "[Total Amount]"}}',
    (P23_FINAL, "stacked-bar-measures"):
        '{type: stacked-bar, options: {legend: left, labels: on}, '
        'slots: {category: "Sales[Country]", value: ["[Total Amount]", "[Target Amount]"]}}',
    (P23_FINAL, "area-measures"):
        '{type: stacked-column, options: {labels: on}, '
        'slots: {category: "Sales[Country]", value: ["[Total Amount]", "[Target Amount]"]}}',
    (P23_FINAL, "labels-legend"):
        '{type: stacked-column-100, options: {labels: on, legend: top}, '
        'slots: {category: "Sales[Country]", value: ["[Total Amount]", "[Target Amount]"]}}',
}


def _by_spec_id(report: Path) -> dict[str, dict]:
    return {a["value"]: d for d in _visual_docs(report) for a in d.get("annotations", [])
            if a.get("name") == "blueprint.visual"}


@pytest.mark.parametrize(("step_name", "sid"), list(PROBE_23))
def test_23_specs_write_what_desktop_drew(replays, tmp_path, step_name, sid):
    steps = {s.name: s for s in replays[23]}
    drawn = _by_spec_id(steps[step_name].report)[sid]["visual"]
    proj = _copy(_last(replays, 23), tmp_path)
    spec = tmp_path / "x.yaml"
    spec.write_text(f"page: X\nlayout: standard-4-up\nvisuals:\n  - {{type: header, title: X}}\n"
                    f"  - {{id: x, {PROBE_23[(step_name, sid)][1:]}\n")
    assert main(["apply", str(spec), "--report", str(proj), "--guidelines", str(GUIDE), *VISUALS]) == 0
    [page] = [p for p in read_report(proj / "Fixture.Report").pages if p.display_name == "X"]
    [ours] = [v.source.data["visual"] for v in page.visuals if v.spec_id == "x"]
    assert ours["visualType"] == drawn["visualType"]
    assert ours["query"] == drawn["query"]
    assert ours.get("objects") == drawn.get("objects")


def test_24_desktops_save_kept_every_blueprint_file(replays):
    """Probe 24: after Refresh now and Ctrl+S, Desktop rewrote no page or visual file (the save
    landed: the model and theme were rewritten byte-identical), so nothing in the report changed."""
    built, saved = replays[24][-2], replays[24][-1]
    assert saved.name.startswith("01 refresh and save")

    def report_files(step: Step) -> dict[str, bytes]:
        return {p.relative_to(step.report).as_posix(): p.read_bytes()
                for p in step.report.rglob("*") if p.is_file()}

    assert report_files(saved) == report_files(built)
    assert len(_managed(saved)) == 14  # 12 charts and slicers, 2 headers


# Probe 27: the candidates Desktop drew after Refresh now and a save, as spec visuals.
PROBE_27 = {
    "line-drill": '{type: line, slots: {category: ["Sales[Country]", "Sales[Region]"], value: "[Total Amount]"}}',
    "area-drill": '{type: area, slots: {category: ["Sales[Country]", "Sales[Region]"], value: "[Total Amount]"}}',
}


@pytest.mark.parametrize("sid", list(PROBE_27))
def test_27_drill_down_specs_write_what_desktop_drew(replays, tmp_path, sid):
    saved = _last(replays, 27)
    drawn = _by_spec_id(saved.report)[sid]["visual"]
    proj = _copy(saved, tmp_path)
    spec = tmp_path / "x.yaml"
    spec.write_text(f"page: X\nlayout: one-up\nvisuals:\n  - {{type: header, title: X}}\n"
                    f"  - {{id: x, {PROBE_27[sid][1:]}\n")
    assert main(["apply", str(spec), "--report", str(proj), "--guidelines", str(GUIDE), *VISUALS]) == 0
    [page] = [p for p in read_report(proj / "Fixture.Report").pages if p.display_name == "X"]
    [ours] = [v.source.data["visual"] for v in page.visuals if v.spec_id == "x"]
    assert ours["visualType"] == drawn["visualType"]
    assert ours["query"] == drawn["query"]


def test_27_desktops_save_kept_every_file(replays):
    """After Refresh now and Ctrl+S (the data cache was rewritten), no report file changed: the
    candidates that errored (two Legend columns) were kept as written too."""
    built, saved = replays[27][-2], replays[27][-1]
    assert saved.name.startswith("01 refresh now and save")

    def report_files(step: Step) -> dict[str, bytes]:
        return {p.relative_to(step.report).as_posix(): p.read_bytes()
                for p in step.report.rglob("*") if p.is_file()}

    assert report_files(saved) == report_files(built)


@pytest.mark.parametrize("vtype", ["line", "area"])
def test_27_two_legend_columns_are_refused(replays, tmp_path, capsys, vtype):
    """Desktop drew "There's too many columns in the Legend bucket" for Series = Country, Region."""
    proj = _copy(_last(replays, 27), tmp_path)
    spec = tmp_path / "bad.yaml"
    spec.write_text(f"page: Bad\nlayout: one-up\nvisuals:\n  - {{type: header, title: B}}\n"
                    f"  - {{type: {vtype}, slots: {{category: 'Sales[Order Date]', value: '[Total Amount]', "
                    "legend: ['Sales[Country]', 'Sales[Region]']}}\n")
    assert main(["apply", str(spec), "--report", str(proj), "--guidelines", str(GUIDE), *VISUALS]) == 2
    assert "visuals[1].slots.legend: takes a single field, not a list" in capsys.readouterr().err


# Probe 28: candidates Desktop drew, as spec visuals.
_DRILL_LEGEND = ('slots: {category: ["Sales[Country]", "Sales[Region]"], value: "[Total Amount]", '
                 'legend: "Sales[Order Date]"}}')
PROBE_28 = {
    "dl-line": "{type: line, " + _DRILL_LEGEND,
    "dl-area": "{type: area, " + _DRILL_LEGEND,
    "dl-stacked": "{type: stacked-column, " + _DRILL_LEGEND,
    "dl-stacked-100": "{type: stacked-column-100, " + _DRILL_LEGEND,
    "dl-stacked-bar": "{type: stacked-bar, " + _DRILL_LEGEND,
    "legend-bottom": '{type: column, options: {legend: bottom}, '
                     'slots: {category: "Sales[Country]", value: ["[Total Amount]", "[Target Amount]"]}}',
}


@pytest.mark.parametrize("sid", list(PROBE_28))
def test_28_specs_write_what_desktop_drew(replays, tmp_path, sid):
    drawn = _by_spec_id(_last(replays, 28).report)[sid]["visual"]
    proj = _copy(_last(replays, 28), tmp_path)
    spec = tmp_path / "x.yaml"
    spec.write_text(f"page: X\nlayout: one-up\nvisuals:\n  - {{type: header, title: X}}\n"
                    f"  - {{id: x, {PROBE_28[sid][1:]}\n")
    assert main(["apply", str(spec), "--report", str(proj), "--guidelines", str(GUIDE), *VISUALS]) == 0
    [page] = [p for p in read_report(proj / "Fixture.Report").pages if p.display_name == "X"]
    [ours] = [v.source.data["visual"] for v in page.visuals if v.spec_id == "x"]
    assert ours["visualType"] == drawn["visualType"]
    assert ours["query"] == drawn["query"]
    assert ours.get("objects") == drawn.get("objects")


@pytest.mark.parametrize("vtype", ["line", "area", "stacked-column", "stacked-column-100", "stacked-bar"])
def test_28_several_measures_with_a_legend_are_refused(replays, tmp_path, capsys, vtype):
    """Desktop drew "There's too many columns in the Legend bucket" for Y = two measures with
    Series = Region on the stacked and area charts (and allows one Y value with a Legend on line)."""
    proj = _copy(_last(replays, 28), tmp_path)
    spec = tmp_path / "bad.yaml"
    spec.write_text(f"page: Bad\nlayout: one-up\nvisuals:\n  - {{type: header, title: B}}\n"
                    f"  - {{type: {vtype}, slots: {{category: 'Sales[Country]', legend: 'Sales[Region]', "
                    "value: ['[Total Amount]', '[Target Amount]']}}\n")
    assert main(["apply", str(spec), "--report", str(proj), "--guidelines", str(GUIDE), *VISUALS]) == 2
    err = capsys.readouterr().err
    assert "visuals[1].slots.value: takes one field when legend is set" in err
    assert "Desktop doesn't draw a value list together with a legend" in err


def test_21_rebinding_after_desktops_save(replays, tmp_path, capsys):
    """Probe 21's charts carry the filterConfig Desktop added on save. Rebinding them in place
    drops Desktop's filters on the fields that went, keeps the rest, and leaves a valid file."""
    proj = _copy(_last(replays, 21), tmp_path)
    spec = proj / "specs" / "slicer-matrix.yaml"
    text = spec.read_text()
    spec.write_text(text.replace('slots: {category: "Sales[Country]", value: ["[Total Amount]", "[Target Amount]"]}',
                                 'slots: {category: "Sales[Region]", value: "[Total Amount]"}'))
    args = ["apply", str(spec), "--report", str(proj), "--guidelines", str(GUIDE), *VISUALS]
    capsys.readouterr()
    assert main(args) == 0
    assert capsys.readouterr().out.count("rebind Category [Country]; Y [Total Amount, Target Amount] -> "
                                         "Category [Region]; Y [Total Amount]") == 3
    report = read_report(proj / "Fixture.Report")
    for d in _visual_docs(proj / "Fixture.Report"):
        if d["visual"]["visualType"] in ("clusteredBarChart", "lineChart"):  # Desktop saved these two
            assert [f["field"] for f in d["filterConfig"]["filters"]] == [
                {"Measure": {"Expression": {"SourceRef": {"Entity": "Sales"}}, "Property": "Total Amount"}}]
    found = check_report(report, _rules()).findings
    assert [f for f in found if f.rule == "format"] == []
    capsys.readouterr()
    assert main(args) == 0 and capsys.readouterr().out.startswith("No changes.")


# --- probe 33: Desktop keeps the legend column, legend off and totals bp apply wrote ------------


def _data_visuals_by_spec_id(step: Step) -> dict[str, dict]:
    out = {}
    for doc in _visual_docs(step.report):
        sid = next((a["value"] for a in doc.get("annotations", []) if a.get("name") == "blueprint.visual"), None)
        if sid and doc.get("visual", {}).get("query"):  # the data visuals (headers repeat "header-1")
            out[sid] = doc
    return out


def _series(visual: dict) -> dict | None:
    return visual.get("query", {}).get("queryState", {}).get("Series")


def test_33_desktop_keeps_the_legend_column_legend_off_and_totals(replays):
    """probe 33: Desktop's save changed no Series, `legend` or `total` of what Blueprint wrote. (It
    flips a drill-down's second level to `active: false`, which is view state, and raises $schema
    and adds auto filters, so those are compared away.)"""
    built, saved = (_data_visuals_by_spec_id(replays[33][i]) for i in (1, 2))  # after apply, after Desktop's save
    assert set(built) == set(saved) and len(built) == 15
    for sid, doc in built.items():
        before, after = doc["visual"], saved[sid]["visual"]
        assert after.get("objects") == before.get("objects"), sid
        assert _series(after) == _series(before), sid
    # the pieces that matter, as Blueprint wrote them and Desktop kept them
    assert "Series" in saved["lb-col"]["visual"]["query"]["queryState"]
    assert "active" not in saved["lb-col"]["visual"]["query"]["queryState"]["Series"]["projections"][0]
    assert set(saved["ls-col-off"]["visual"]["objects"]["legend"][0]["properties"]) == {"show"}
    assert saved["tt-off"]["visual"]["objects"]["total"][0]["properties"]["totals"]["expr"]["Literal"]["Value"] == "false"
