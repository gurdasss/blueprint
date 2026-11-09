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

**README Q4:** Desktop gives new objects 20 hex characters, and accepts Blueprint's derived 20-hex
names (probe 05, below).

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

**Verified 2026-11-09, Desktop 2.159.1231.0, probe 02 phase 1** (`scripts/probe_formatting.py`;
evidence `docs/probes/02-formatting-phase1.diff`, redacted). One step per visual. Each
step rewrote only its own file:

| Step | Where it landed | Encoding |
|---|---|---|
| Custom hex data colour (single-series column chart) | `visual.objects.dataPoint[0].properties.fill` | `{"solid":{"color":{"expr":{"Literal":{"Value":"'#E15759'"}}}}}`, no `selector`, so it applies to the whole series |
| Theme colour on ONE pie slice | `visual.objects.dataPoint[0]` | `fill.solid.color.expr = {"ThemeDataColor":{"ColorId":2,"Percent":0.4}}` plus `selector.data[0].scopeId.Comparison` (`Left`: column ref, `Right`: `Literal` **category value from the data**) |
| Title font size, bold, colour | `visual.visualContainerObjects.title[0].properties` | `fontSize = Literal "18D"`, `bold = Literal "true"`, `fontColor` = hex literal as above |
| Card callout size + theme colour | `visual.objects.labels[0].properties` | `fontSize = Literal "28D"`, `color.solid.color.expr = {"ThemeDataColor":{"ColorId":0,"Percent":-0.1}}` |
| Page canvas background | `page.json objects.background[0].properties.color` | hex literal. `transparency` 0% was **not** written (default values are omitted) |
| Theme colour on textbox text | `…paragraphs[0].textRuns[0].textStyle` | **resolved to plain hex** `"color": "#f7c1a4"`; the theme reference is lost. Desktop also **dropped** `fontStyle`/`fontWeight: "normal"` from the run |

What follows for a palette or typography check:

- **Three colour forms:** a hex `Literal` inside `…solid.color.expr`; a theme reference
  `ThemeDataColor {ColorId, Percent}` (a shade, where `Percent` is lighter > 0 and darker < 0);
  and a plain hex string in textbox `textStyle.color`. Textbox colours chosen from the theme
  are stored as their resolved hex, which may be a *shade* that isn't in any palette list.
- Colours are found by **shape** (`solid.color.expr`), under many property names (`fill`,
  `color`, `fontColor`, `background.color`). A walker shouldn't hard-code property names.
- Formatting-object numbers are typed literals: `"18D"` (pt, double). Textbox sizes are
  `"28pt"` strings. Booleans are `"true"`/`"false"`. Strings are `"'…'"`.
- The title font family (set to Segoe UI) was **not written**, presumably because it
  equals the default. Default-valued properties are omitted, so a missing key means "theme or
  default", not "unset".
- **Per-category formatting puts data values in report files** (`'<value>'` in the
  selector). This confirms Learn's warning. Fixtures and committed evidence must be redacted.
- Mapping picker grid positions to `ColorId`/`Percent` is **not established**:
  "1st column, 1st row" gave `ColorId 0, Percent -0.1`. Don't infer grid positions from it.
- Map visuals were unavailable in this Desktop (step 7 skipped). Desktop didn't rewrite
  or convert the existing map `visual.json` files.

**Verified 2026-11-09, Desktop 2.159.1231.0, probe 02 phase 2** (evidence
`docs/probes/02-formatting-phase2-theme.diff`). Switching to the built-in "Dark" theme
("Classic" isn't offered in this version):

- Only `report.json` changed. **No `visual.json` was rewritten.** Theme references
  (`ThemeDataColor`) stay as they are and resolve against the new theme, while hex literals
  (and textbox hex) stay fixed.
- `themeCollection` has two layers: `baseTheme` (`Fluent2-CY26SU10`, type
  `SharedResources`) and `customTheme` (`ReportThemeDark`, type `SharedResources`, which
  replaced `Concourse`/`RegisteredResources`). Both gain `reportVersionAtImport`
  `{"visual":"2.14.0","report":"3.4.0","page":"2.3.1"}`. Note that `report` 3.4.0 is
  newer than the file's own `$schema` (3.3.0).
- Desktop **copies the theme files into the report**:
  `StaticResources/SharedResources/BaseThemes/Fluent2-CY26SU10.json` and
  `…/BuiltInThemes/ReportThemeDark.json`. It registers them in `resourcePackages` as package
  `SharedResources` with items `{name, path, type: "BaseTheme" | "CustomTheme"}`. A theme
  file's location is `StaticResources/<package name>/<item path>`.
- Theme files are standard Power BI theme JSON with no `$schema`: `dataColors` (32 in the base
  theme, 31 in Dark), `foreground`, `background`, `tableAccent`, `good`/`bad`/`neutral`,
  `textClasses` (`callout`, `title`, `header`, `label` with `fontSize`, `fontFace`, `color`)
  and `visualStyles`. The custom theme overrides the base theme: Dark's `textClasses` set
  only `color`. They're written in Desktop's JSON format, so `jsonfmt` round-trips them byte for
  byte, which means they could be patched like any other file.
- Earlier finding still stands: the sample's original `Concourse` theme had no file. A theme
  reference whose file is missing must be reported, not assumed.

**Open:** what `ThemeDataColor.ColorId` indexes. The commonly cited mapping (0 =
background, 1 = foreground, n ≥ 2 = `dataColors[n-2]`) is **unverified**, and so is the
shade formula for `Percent`. A check that only needs "is this a theme reference" doesn't
depend on either.

## Typography

**Verified 2026-11-09, Desktop 2.159.1231.0, probe 03 phase 1** (`scripts/probe_typography.py`;
evidence `docs/probes/03-typography-phase1.diff`). One visual per step. Each step rewrote only
its own file:

| Step | Stored as |
|---|---|
| Title font **Segoe UI Semibold**, size 14 | `title.fontFamily = Literal "'''Segoe UI Semibold'', wf_segoe-ui_semibold, helvetica, arial, sans-serif'"`, `fontSize = Literal "14D"` |
| Title font **Arial**, size untouched | `title.fontFamily = Literal "'Arial'"`, **no `fontSize` written** |
| Subtitle on, "Probe subtitle", size 12 | `visualContainerObjects.subTitle[0].properties` = `show "true"`, `text "'Probe subtitle'"`, `fontSize "12D"` |
| Title on, "Probe title", **Segoe UI**, size 12 | `title.text` and `fontSize "12D"` only: **no `fontFamily`, no `show`** |
| Textbox **Arial 20 Bold Italic** | `textStyle = {"fontWeight": "bold", "fontFamily": "Arial", "fontStyle": "italic", "fontSize": "20pt"}` |
| Textbox **Segoe UI** (no theme font was offered) | `textStyle = {"fontFamily": "Segoe UI", "fontSize": "28pt"}` |

What follows for a typography check:

- **A weight is a font face, not a property.** "Semibold" is the family name `Segoe UI
  Semibold`. `bold` is a separate on/off (`Literal "true"`, seen in probe 02) and textbox
  `fontWeight: "bold"`.
- **Formatting-object `fontFamily` is a CSS font stack inside a single-quoted literal**, with
  `''` escaping quotes inside it. The first family in the stack is the face. Plain names
  can be bare: `'Arial'`.
- **Textbox `fontFamily` is a plain name** (`"Arial"`, `"Segoe UI"`), and sizes are `"20pt"`
  strings. Formatting-object sizes are `"14D"` literals (pt).
- **Default values are omitted.** Choosing Segoe UI for a title wrote no `fontFamily`.
  Turning a title on wrote no `show`. A size the user *sets* is written even if it might equal
  the default. A missing key means "theme or default", not a violation.
- Desktop **drops `fontStyle`/`fontWeight: "normal"`** and **reorders keys** in a textbox
  run it rewrites.
- **Theme font tokens:** this Desktop offered none in the textbox font list. The sample's older
  `"fontFamily": "Heading"` stays unexplained; treat unknown families as unresolved, not as
  violations.
**Verified 2026-11-09, probe 03 phase 2** (evidence `docs/probes/03-typography-phase2.diff`):

- Card callout font (step 4 redone; DIN wasn't offered, so Arial was used) is
  `visual.objects.labels[0].properties.fontFamily = Literal "'Arial'"`, the same literal form as titles.
- Desktop's **theme "Update" prompt** (shown under *Customize current theme* as new theme defaults
  being available) added `themeCollection.baseTheme = {"name": "Fluent2-CY26SU10", "type":
  "SharedResources", …}` to `report.json` **without copying the theme file or adding a
  `resourcePackages` entry**. When switching to the built-in Dark theme (probe 02), Desktop did copy both. So
  a built-in (`SharedResources`) theme can be referenced with no file in the report, and Desktop
  resolves it from its own install. "Theme file missing" is therefore normal for built-in themes. It is not
  corruption.
- *Customize current theme* → Text changes (General Segoe UI 11, Title Segoe UI Semibold 16)
  **did not persist** on a report whose custom theme (`Concourse`) has no file. Where a
  customised theme's text classes are saved was answered in phase 3 below.

**Verified 2026-11-09, probe 03 phase 3** (evidence `docs/probes/03-typography-phase3.diff`).
Switching to the built-in **Bloom** theme and then *Customize current theme* → Text (General
Segoe UI 11, Title Segoe UI Semibold 16):

- A **customised theme is saved as a new custom theme file**:
  `StaticResources/RegisteredResources/Bloom03249907182487033.json` (base name plus a generated
  number). `report.json` sets `customTheme = {"name": "Bloom03249907182487033.json", "type":
  "RegisteredResources"}` (the *name* includes `.json`) and adds a `RegisteredResources` item
  `{name, path, type: "CustomTheme"}`. The **base theme file was embedded this time**
  (`SharedResources/BaseThemes/Fluent2-CY26SU10.json`) with its `resourcePackages` entry.
- The file stores **only the overrides on top of the base theme**: `name: "Bloom"`, `dataColors` (480
  entries), `tableAccent`, `maximum`/`center`/`minimum`, `visualStyles`, and `textClasses`
  `{"label": {"fontSize": 11}, "title": {"fontFace": "'Segoe UI Semibold', wf_segoe-ui_semibold,
  helvetica, arial, sans-serif", "fontSize": 16}}`. This confirms the layering: custom fields override
  base fields. Values equal to the base (label font Segoe UI) are omitted.
- **"General" in the UI is `textClasses.label`**, and "Title" is `textClasses.title`.
- **Theme `fontFace` comes in two forms:** a plain name in the base theme (`"Segoe UI Semibold"`,
  `"DIN"`) and a CSS font stack in the customised theme. Neither is wrapped in quote characters the
  way formatting-object literals are. The first family in the stack is the face.
- The file is 3.2 MB in Desktop's JSON format and round-trips through `jsonfmt`.

### The new card (`cardVisual`)

**Verified 2026-11-09, Desktop 2.159.1231.0, probe 07** (`scripts/probe_card_fonts.py`; evidence
`docs/probes/07-card-fonts.diff`, fixture 02's card "Total", all content invented). Desktop's
sections are *Callout value* and *Category label*.

| Change in Desktop | Written to `visual.json` (`visual.objects`, unless noted) |
|---|---|
| Nothing (defaults shown: value Segoe UI Semibold 21 #242424, label Segoe UI 12 #616161) | nothing in the card |
| Callout value **Arial, 28, Bold, #E15759** | `value = [{"properties": {"fontFamily": Literal "'Arial'", "fontSize": Literal "28D", "bold": Literal "true", "fontColor": {"solid": {"color": hex literal}}}, "selector": {"id": "default"}}]` |
| Category label size **14** | `label = [{"properties": {"fontSize": Literal "14D"}, "selector": {"id": "default"}}]` |
| Title size **16** | `visual.visualContainerObjects.title[0].properties.fontSize = Literal "16D"`, as on every other visual |

What follows:

- **The callout value is `objects.value`** (not `labels`, as on the legacy `card`), with the same
  literal forms as titles. Bold is a separate `bold` property, as it is for titles. It doesn't change the face.
- **Each entry has a `selector` of `{"id": "default"}`**. The theme writes the same tag as
  `"$id": "default"`. Other selectors (presumably per measure) were not observed.
- **Defaults come from the theme:** the base theme's `visualStyles.cardVisual["*"].value` is
  `[{"$id": "default", "textClass": "callout"}]`, and the shown value matches `textClasses.callout`
  exactly (21, Segoe UI Semibold, #242424). `visualStyles.cardVisual["*"].label` sets `fontSize: 12`,
  `textClass: "label"`, `fontColor: foregroundNeutralSecondary` (#616161). That outranks
  `textClasses.label` (10.5), which is the same layering as titles in probe 06.
- Colours are found by shape (`fontColor.solid.color.expr`), so the palette rule already covers them.
- **Open:** whether a custom theme's `textClasses.callout` reaches the card's value. By the probe 06
  layering it should, because the base sets only `textClass` at the `visualStyles` level, but no probe has applied one.
- Step 1, an open and save with no changes, also rewrote unrelated state. A slicer projection's
  `active` went from `true` to `false`, and `report.json` gained `objects.outspacePane[0].expanded =
  false`, recording the collapsed Filters pane. That's view state Desktop persists on save.

## Creating pages and visuals

**Verified 2026-11-09, Desktop 2.159.1231.0, probe 04** (`scripts/probe_apply.py`; evidence
`docs/probes/04-apply-from-scratch.diff`, one commit per step, all content invented). This answers
README Q1–Q3 and Q5–Q11. Every file Desktop wrote validates and round-trips through `jsonfmt`.

### A new report (Q1)

- Files: `Fixture.pbip`, `.gitignore` (Desktop writes one that ignores only
  `**/.pbi/localSettings.json` and `**/.pbi/cache.abf`), `Fixture.Report/{.platform,
  definition.pbir, definition/{version.json, report.json, pages/pages.json,
  pages/<id>/page.json}, StaticResources/SharedResources/BaseThemes/Fluent2-CY26SU10.json}`, and
  `Fixture.SemanticModel/{.platform, definition.pbism, diagramLayout.json, .pbi/editorSettings.json,
  definition/{database,model}.tmdl, definition/cultures/<locale>.tmdl}`. The culture file is
  named after the Desktop locale (`en-IN` here).
- **The default canvas is 1920×1080** (`displayOption: FitToPage`), not 1280×720.
- `report.json` embeds the base theme file and its `resourcePackages` entry, sets
  `objects.section.verticalAlignment = 'Top'`, and has `settings` `{useStylableVisualContainerHeader,
  exportDataMode: "AllowSummarized", defaultDrillFilterOtherVisuals, allowChangeFilterTypes,
  useEnhancedTooltips, useDefaultAggregateDisplayName}` (all `true` except `exportDataMode`).
- `definition.pbir` has no `$schema`, even in a new report.

### IDs (Q4, partly)

- Pages, visuals and **filters** (`filterConfig.filters[].name`) all get **20 lowercase hex
  characters** (`6a692d13619c1d4c0146`). They look random. A pasted visual gets a new ID, and
  so does each of its filters.
- Desktop **accepts Blueprint-generated names** (deterministic, still 20 hex) for new objects:
  see probe 05 below.

### Pages (Q2, Q3, Q5)

- **Add:** a new folder `pages/<id>/page.json` with exactly `$schema`, `name` (= the folder),
  `displayName` (`"Page 2"`), `displayOption`, `height`, `width`. **`pages.json` is updated** too:
  the ID is appended to `pageOrder` and `activePageName` is set to the new page. A page folder
  on its own is therefore not enough: `bp apply` must update the registry.
- **Rename:** `displayName` only. The ID and folder stay the same.
- **Reorder:** `pageOrder` only. Folder names never imply order.
- **Delete:** the page folder is removed and its ID is removed from `pageOrder`. `activePageName`
  was left alone (another page was active).

### Visuals (Q6–Q11)

- **Add:** a new folder `visuals/<id>/visual.json`. No other file changes, except
  `activePageName` following the page on screen.
- **Defaults:** a new card is placed at `x 10, y 0`, size `280×280`; a column chart is `696×329`.
  `z` and `tabOrder` are the next integer on the page (0, 1, 2, …).
- **The card type is `cardVisual`** (the newer card), with its field in role **`Data`**. Older
  reports use `card` with role `Values`. The typography `callout` role covers `card` `labels`
  and `cardVisual` `value` (probe 07).
- Desktop adds the following to every bound visual: `query.sortDefinition` (`isDefaultSort: true`;
  descending on the measure for the card, ascending on each category level for the chart),
  `visual.drillFilterOtherVisuals: true`, and **`filterConfig.filters`**, one per bound field
  (`type: "Advanced"` for a measure, `"Categorical"` for a column), each with its own 20-hex
  `name`.
- **Bindings (Q9):** `{"field": {"Measure"|"Column": {"Expression": {"SourceRef": {"Entity":
  "<table>"}}, "Property": "<name>"}}, "queryRef": "<table>.<name>", "nativeQueryRef": "<name>"}`.
  Category columns also have `"active": true`.
- **Drill-down (Q11):** an **ordered list of projections in one role** (`Category`: Country,
  then Region). The order is the hierarchy. `sortDefinition` has one entry per level.
- **Field wells (Q10):** column chart roles are `Category` and `Y`; the card's is `Data`.
- **Title (Q8):** `visualContainerObjects.title[0].properties` = `show "true"` + `text
  "'Total'"`.
- **Pie, table and KPI (probe 08):** verified 2026-11-09, Desktop 2.159.1231.0
  (`scripts/probe_pie_table_kpi.py`; evidence `docs/probes/08-pie-table-kpi.diff`, fixture 02,
  all content invented). Each type was added on a new page with no other changes:

  | Desktop name: wells | `visualType` | `queryState` roles | Added by Desktop |
  |---|---|---|---|
  | Pie chart: Legend, Values | `pieChart` | `Category` (column, `"active": true`), `Y` (measure) | `sortDefinition` descending on the measure, `drillFilterOtherVisuals` |
  | Table: Columns | `tableEx` | `Values`: columns and measures mixed in one role, in well order, **no `active`** | `drillFilterOtherVisuals` only (no sort) |
  | KPI: Value, Trend axis, Target | `kpi` | `Indicator` (measure), `TrendLine` (column, **no `active`**) | `drillFilterOtherVisuals` only (no sort) |

  - **`"active": true` belongs to `Category` projections only** (column chart, probe 04, and pie).
    A table's or KPI's column projections don't carry it.
  - **Reordering the table's Columns well only reorders the `Values` projections.** Nothing else
    changes, so projection order is column order.
  - New visuals default to `280×280` at `x 10`, stacked downwards with a 10px gap (`y` 0, 290,
    580). `z`/`tabOrder` are the next integer, as in probe 04.
  - No `filterConfig` was written, because the filter pane stayed collapsed (probe 05).
  - **Open:** more than one Legend column on a pie.
  - **KPI Target (probe 10,** `scripts/probe_kpi_target.py`; evidence `docs/probes/10-kpi-target.diff`):
    the Target well is role **`Goal`**, holding a measure projection of the usual shape. The KPI shows
    the Value at the **last trend-axis point** (300, not the 500 total) against the goal (600, "-50%",
    red). A new measure is written to TMDL as `measure 'Target Amount' = 600` with `formatString: 0`
    and a `lineageTag`.
  - **Target also accepts a column**, which Desktop stores as an implicit aggregation: `{"field":
    {"Aggregation": {"Expression": {"Column": {"Expression": {"SourceRef": {"Entity": "Sales"}},
    "Property": "Amount"}}, "Function": 0}}, "queryRef": "Sum(Sales.Amount)", "nativeQueryRef":
    "Sum of Amount"}` (Desktop shows "Sum of Amount"; `Function` 0 is Sum, and other functions
    weren't observed). Specs have no syntax for this, so the `target` slot accepts measures only, and the
    reader skips `Aggregation` fields.
  - **`queryState` roles are written in alphabetical order**, not well order: `Goal`, `Indicator`,
    `TrendLine` (the wells read Value, Trend axis, Target). That matches every type seen so far
    (`Category`/`Y`, `Values`, `Data`), so `render` sorts roles.
  - **Desktop accepts Blueprint's pie, table and KPI as written (probe 09,** `scripts/probe_apply_types.py`;
    evidence `docs/probes/09-apply-types.diff`). `bp apply examples/sales-mix.yaml` on fixture 02,
    then open and save: **no visual or page file changed**. Only `activePageName` and
    `outspacePane.expanded` changed, which is UI state as in probe 07. The wells showed each
    field where the spec put it: KPI Value/Trend axis, pie Legend/Values, and the table's
    Columns in spec order.
- **Move/resize (Q7):** only `position` changes, as sub-pixel floats.
- **Paste:** an identical file apart from `name`, filter `name`s, `position`, and the next
  `z`/`tabOrder`. (Whether annotations are copied is untested.)
- **Delete:** the visual's folder is removed. Nothing else changes.

### Blueprint-created pages and visuals in Desktop (probe 05)

**Verified 2026-11-09, Desktop 2.159.1231.0** (`scripts/probe_apply_output.py`; evidence
`docs/probes/05-apply-output.diff`). `bp apply` added a page (1280×720) with a header textbox, a
card and a column chart with a drill-down to fixture 02. The user opened it, saved without
changes, then dragged the card and saved:

- **Desktop accepts Blueprint's derived 20-hex names** for new pages and visuals (README Q4).
  Folder names and `name` values were kept, and nothing was renamed or dropped.
- **Annotations survived** on the page and all three visuals (`blueprint.page`/`blueprint.visual`).
- **Desktop added nothing to the minimal visuals:** no `sortDefinition`, no `filterConfig`, no
  `drillFilterOtherVisuals`. The textbox with a bare `{"value": …}` text run and the page.json
  were left byte-identical. So the minimal shapes in `pbir/render.py` are sufficient.
- On the same save, Desktop **removed the auto-created `filterConfig.filters`** from the
  hand-made fixture visuals. That matches Learn: visual automatic filters persist only after the
  filter pane has been expanded. They are pane state, not something a generator must write.
- **Desktop renumbers `z` and `tabOrder` in steps of 1000** on save (0, 1, 2 became
  0, 1000, 2000 on both pages). Blueprint now writes 1000-steps, so this rewrite doesn't happen.
- Files Desktop rewrote got their `$schema` raised from vendored `visualContainer/2.13.0` to
  `2.14.0`. Untouched files kept 2.13.0. An older minor version is accepted as written.
- A drag changed only the card's `position` (sub-pixel floats). **Re-running `bp apply` restored
  the layout position exactly** and changed nothing else. A third run reported no changes.

### A Blueprint-written theme in Desktop (probe 06)

**Verified 2026-11-09, Desktop 2.159.1231.0, phase 1** (`scripts/probe_theme.py`; evidence
`docs/probes/06-theme-phase1.diff`). `bp apply` + `fmt` + `theme` (example guidelines) on fixture 02:

- **Desktop accepted the theme file as written.** It didn't rewrite `blueprint-theme.json` or the
  `customTheme`/`RegisteredResources` entries. The user saw the theme name in *Customize current
  theme* over base "Fluent 2", with data colours in order (#4E79A7, #F28E2B, #E15759, …), and
  titles in the theme's `textClasses.title.fontFace` (Segoe UI Semibold).
- **But titles were 15pt, not 18.** The base theme sets `visualStyles["*"]["*"].title =
  {"show": true, "fontSize": 15}` (and `subTitle` `fontSize: 12`), which **outranks
  `textClasses.title.fontSize`**. The font face came through because the base doesn't set one at that
  level. So `bp theme` must also write sizes at `visualStyles["*"]["*"].title/subTitle`, and the
  check must read that level: it had reported 0 errors (a false pass) while titles were 15pt.
- Desktop added `filterConfig.filters` to Blueprint's visuals on this save (the filter pane had
  been opened: `report.json` gained `objects.outspacePane.expanded = false`), and a drill-down
  changed a category projection's `"active"` to `false`. Both are UI state. `apply` compares
  only which fields are bound, so neither affects a re-run.

**Verified, probe 06 phase 2:** with `visualStyles["*"]["*"].title = [{"fontSize": 18}]` (and
`subTitle` 12) added to Blueprint's theme, titles show at **18pt** in Segoe UI Semibold. They're
still shown on charts and the card and still hidden on the textbox, so the custom theme overrides
only the keys it sets and the base theme's `show` survives. Opening and saving then produced
**no diff at all**: Desktop re-serialised `blueprint-theme.json` (new mtime) to byte-identical
content, so Blueprint's theme file matches Desktop's format exactly.

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
- A file with a newer, unvendored minor version can legitimately fail the older schema (new
  properties). So the writer blocks only on errors **its own change introduces**, compared with
  the file as read from disk. `check` reports such files as a single **warning** per file,
  pointing to `scripts/vendor_schemas.py`, not as errors. Errors on an exactly vendored version
  stay errors.
