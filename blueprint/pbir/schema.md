# PBIR format notes

Living record of what is **verified** about the on-disk format. Each entry says how it was
established. Anything not listed here is unverified: don't write code that depends on it.

Sources:
- **[sample]**: `samples/retail-analysis` (Microsoft "Retail Analysis Sample", saved as PBIP
  by Power BI Desktop **2.159.1231.0 64-bit (October 2026)**, 2026-11-08). Local only, not committed.
- **[learn]**: Microsoft Learn, "Power BI Desktop project report folder" (ms.date 2026-09-23).
- **[schema]**: vendored JSON schemas under `schemas/` (microsoft/json-schemas, MIT).

## File encoding

**Verified [sample], all 31 JSON files under the `.Report` folder:**

- UTF-8, no BOM. CRLF line endings throughout. No newline after the final `}`.
- Two-space indent, `"key": value`. Empty containers are written inline: `[]`, `{}`.
- Non-ASCII is written raw, not `\u`-escaped. No `\/` escaping.
- Floats are not Python-`repr` compatible. `9.7990430622009566` (17 significant digits)
  appears next to `643.9103869653768` (shortest round-trip). `jsonfmt` therefore keeps the raw text of every
  number it parses.
- `jsonfmt.load` → `jsonfmt.dumps` reproduces all 31 files byte-for-byte
  (`tests/test_jsonfmt.py`).

**Verified 2026-11-09, Desktop 2.159.1231.0 (by hand):** after `bp fmt` rewrote 17 `visual.json`
files with integer coordinates, the report opened in Desktop without errors. Saving
produced **no diff**: Desktop doesn't re-serialise unchanged files (README Q13), and it keeps
our integers (`"x": 640`) as written. This also confirms the writer's output is accepted
on load.

## What Desktop changes on its own when saving

**Verified 2026-11-09, Desktop 2.159.1231.0 (by hand):** the untouched sample was copied into a
git repo, opened, browsed, and saved. Desktop modified exactly two files:

- `definition/pages/pages.json`: `activePageName` became the page on screen at save time
  (`ReportSection` → `ReportSection3`). This is UI state: any save can change it. **Blueprint
  must never treat `activePageName` as owned**, and golden tests must not depend on it.
- `definition/report.json`: appended `"settings": {"useEnhancedTooltips": false}`. Desktop
  adds a default setting that was missing from the older file. Expect similar one-off
  upgrades the first time Desktop saves an older report.

Probe 02's first save (no edits) rewrote, by mtime, every report- and model-level file
(`.pbip`, `.platform`, `definition.pbir`, `report.json`, `pages.json`, all TMDL,
`.pbi/*`), but **no `page.json` or `visual.json`**. Only `pages.json` and `report.json`
changed in content. So Desktop rewrites per-page and per-visual files only when they change.

Both rewritten files still use CRLF line endings with no trailing newline. `jsonfmt`
round-trips both byte for byte, and both validate. **New keys go in Desktop's own
order, not at the end:** in probe 01, `settings` was inserted *before* an existing
`annotations` key. So anything Blueprint adds to a document that Desktop also writes may
move on Desktop's next save. That's churn but not breakage, since Desktop never drops the key.
Git prints `^M` only on *added* lines, which is a display artefact; `git config
core.whitespace cr-at-eol` hides it.

## Report folder

**Verified [sample]:**

```
<Name>.pbip                       {"version":"1.0","artifacts":[{"report":{"path":"<Name>.Report"}}],"settings":{...}}
<Name>.Report/
  .pbi/localSettings.json         per-user, gitignored (contains a securityBindingsSignature)
  .platform                       $schema gitIntegration/platformProperties/2.0.0; config.logicalId is a GUID
  definition.pbir                 {"version":"4.0","datasetReference":{"byPath":{"path":"../<Name>.SemanticModel"}}}
  StaticResources/RegisteredResources/<files>
  definition/
    version.json                  versionMetadata/1.0.0, "version": "2.0.0"
    report.json                   report/3.3.0: theme, resourcePackages, report-level objects
    pages/pages.json              pagesMetadata/1.1.0: pageOrder[], activePageName
    pages/<page>/page.json        page/2.1.0
    pages/<page>/visuals/<visual>/visual.json   visualContainer/2.14.0
<Name>.SemanticModel/             TMDL under definition/; .pbi/cache.abf (9.7 MB, gitignored)
```

- The sample's `definition.pbir` has **no `$schema`** key. The [learn] example has one.
- PBIR-Legacy (`definition.pbir` version `"1.0"`, or no `definition/` folder) is refused by
  the reader.

## Names and IDs

- **[learn]:** names must be word characters or hyphens. Desktop silently ignores files or folders
  whose names don't comply. New objects get 20-character hex IDs (`90c2e07d8e84e7d5c026`).
- **[schema]:** page `name` and visual `name` have `maxLength: 50`.
- **[sample]:** reports converted from older files keep legacy names: pages
  `ReportSection`, `ReportSection2`; visuals `VisualContainer`, `VisualContainer1`, …
  Folder name == `name` property in every case. Readers must not assume hex IDs.

**Open (README Q4):** does Desktop accept any compliant name for a *new* object, or must
it be 20 hex characters?

## Pages

**Verified [sample] + [schema]:**

- `page.json` required keys: `$schema`, `name`, `displayName`, `displayOption`.
- `width`/`height` are required unless `displayOption` is `DeprecatedDynamic`.
  `ReportSection2` in the sample is `DeprecatedDynamic` and has no size.
- Page order comes from `pages.json` `pageOrder`, which lists folder names.

**Open (Q2/Q3/Q5):** does a page folder that is missing from `pageOrder` still appear in
Desktop?

## Visuals

**Verified [sample] + [schema] (visualContainer 2.13.0):**

- Required: `$schema`, `name`, `position`. `additionalProperties: false`, so unknown
  top-level keys are schema errors.
- `position`: `x`, `y`, `z`, `width`, `height` (+ optional `tabOrder`). Unit is page pixels.
  Values may be non-integral.
- Optional top-level: `visual`, `visualGroup`, `parentGroupName`, `filterConfig`,
  `isHidden`, `annotations`, `howCreated`.
- `visual.visualType` is the type string. Seen in the sample: `areaChart`, `card`, `clusteredColumnChart`,
  `columnChart`, `image`, `lineChart`, `map`, `pieChart`, `scatterChart`, `slicer`, `textbox`.
- Title: `visual.visualContainerObjects.title[0].properties.text.expr.Literal.Value`, a
  single-quoted literal, e.g. `"'Total Sales Variance by …'"`.
- `annotations`: `[{"name": str, "value": str}]`, no other keys. Blueprint uses
  `blueprint.ignore` = `"true"` for the escape hatch.

**Verified 2026-11-09, Desktop 2.159.1231.0, probe 01** (`scripts/probe_annotations.py`; evidence
`docs/probes/01-annotations-desktop-save.diff`). This answers README Q14:

- Annotations survive a Desktop save at **report, page and visual level**, including on
  a visual Desktop *rewrote* because the user moved it. Values and order are unchanged.
- Desktop rewrites only the visual that was edited. The other 16 files Blueprint wrote were left
  byte-identical, so integer coordinates stay integers until a human drags that visual.
- Dragging a visual in Desktop rewrites **all four** of x/y/width/height with
  sub-pixel floats (`912` → `911.63049495393955`), even though only the position was
  meant to change. This is the drift `bp fmt` exists to undo; a dry run snaps it back to the
  exact pre-drag values.
- Desktop keeps files it doesn't know in the `.Report` folder (`.blueprint.yaml` survived).

**Open:** does copy/paste of a visual keep its annotations, and what name does the copy
get? (Probe 01 step 4 was not done.) Are grouped visuals' positions relative to the
group or to the page?

## Colours, fonts and theme

**Verified [sample]:** colour and font values come in at least two encodings:

- **Textbox text runs**: plain strings in
  `visual.objects.general[0].properties.paragraphs[i].textRuns[j].textStyle`, e.g.
  `{"fontFamily": "Segoe UI Light", "fontSize": "28pt", "fontStyle": "normal",
  "fontWeight": "normal"}` and `{"fontSize": "15pt", "color": "#2da2bf"}`. Font size is a
  string with a `pt` unit. Hex can be lowercase. `"fontFamily": "Heading"` appears too and is
  presumably a theme font token (unverified).
- **Formatting objects** (`objects` / `visualContainerObjects`): expression literals, e.g.
  title colour `fontColor = {"solid": {"color": {"expr": {"Literal": {"Value": "'#000000'"}}}}}`
  and the same shape for `visualContainerObjects.background[0].properties.color`. The hex is
  inside a single-quoted literal.
- **Theme:** `report.json` `themeCollection.customTheme = {"name": "Concourse", "type":
  "RegisteredResources", …}`, but **no theme file exists** in `StaticResources` and none
  is listed in `resourcePackages`. Desktop opens the report anyway, so a referenced theme
  can be missing. A palette check can't assume the theme's colours are readable.

**Open (probe 02, `scripts/probe_formatting.py`):** how data colours, theme-colour
references (and shades), per-category selectors, title and card font sizes and bold,
and page background are stored, and where a theme lives when it's switched.

## Field bindings

**Verified [sample]** (`ReportSection3/visuals/VisualContainer4`):

```json
"query": {"queryState": {
  "Category": {"projections": [{"field": {"Column": {"Expression": {"SourceRef": {"Entity": "Time"}},
                                                     "Property": "FiscalMonth"}},
                                "queryRef": "Time.FiscalMonth", "active": true}]},
  "Y": {"projections": [{"field": {"Measure": {"Expression": {"SourceRef": {"Entity": "Sales"}},
                                               "Property": "Total Sales Variance"}},
                         "queryRef": "Sales.Total Sales Variance"}]}}}
```

- Some sample visuals use `"queryRef": "select"`, `"select1"`, … instead of
  `Table.Column` (older report). Readers must not parse meaning out of `queryRef`.
- Measures and columns are both bound with their **home table** (`Entity`). So a spec
  that says `"[Total Sales]"` needs the semantic model to find that table.
- The semantic model is TMDL: `tables/<Table>.tmdl` with `measure <Name> = …` lines.

## Schema versions

- Desktop wrote `visualContainer/2.14.0`, but microsoft/json-schemas only publishes up to
  2.13.0 (changelog: monthly minor bumps, mostly `visualConfiguration` formatting).
- Each schema pins `$schema` with `const`, so validating against a different minor version means
  substituting the URL. `schemas.resolve()` picks the nearest vendored version with the same
  major version. All 31 sample files validate this way.
- Policy: same major version, newer minor: read and write, report it as "validated as X".
  Unknown major version: refused for writing unless `--force-schema`.
