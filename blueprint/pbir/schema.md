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
- The typography role `card_label` covers `objects.label`. Its theme default is read from
  `visualStyles.cardVisual["*"].label[0]` over `textClasses.label`.
- **Verified, probe 15** (`scripts/probe_card_theme.py`; evidence `docs/probes/15-card-theme.diff`):
  a custom theme entry `visualStyles.cardVisual["*"].label = [{"$id": "default", "fontSize": 14,
  "fontFamily": "'Arial', helvetica, arial, sans-serif"}]` made Desktop show the Category label in
  Arial 14. The entry **merges with the base one key by key**: the label stayed above the value, in grey
  (#616161), and the card kept its rounded border, all from the base theme. Other visuals were
  unaffected (the column chart's axis labels stayed Segoe UI). Desktop's open and save changed no file,
  the theme included. **Open:** the label's `bold` in a theme, and the legacy `card`'s category label.
- **A custom theme's `textClasses.callout` reaches the card's value (probe 15).** `bp theme` with
  `callout: {font: Segoe UI Light, size: 32}` made Desktop show the value in Segoe UI Light 32.
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
  - **Pie Legend drill-down and Details (probe 11,** `scripts/probe_pie_legend.py`; evidence
    `docs/probes/11-pie-legend.diff`). Desktop accepts **several Legend columns as an ordered
    drill-down**, stored as an ordered list of `Category` projections (Country, then Region), the same
    as the column chart (probe 04). The **Details** well is role **`Series`**. Its column projection
    has no `active` key, and roles stay alphabetical (`Category`, `Series`, `Y`). With Region in
    Details, each country's slice is split by region ("UK:North").
  - **`active` is drill view state:** right after adding the second Legend field it was Country `false`,
    Region `true`; drilling into a slice set Country to `true`. Desktop's own column chart (fixture 02)
    and Blueprint's output (probe 05) have every level `true`, which Desktop accepts as written.
  - **Drilling writes a filter holding a data value** into the visual: `filterConfig.filters[]` with
    `"howCreated": "Drill"`, `"type": "Categorical"` and an `In` condition on the drilled value
    (`'UK'`). Drilling back up and changing the wells removed it. `apply` ignores `filterConfig`,
    and evidence files must redact these values for real reports.
  - **KPI Target (probe 10,** `scripts/probe_kpi_target.py`; evidence `docs/probes/10-kpi-target.diff`):
    the Target well is role **`Goal`**, holding a measure projection of the usual shape. The KPI shows
    the Value at the **last trend-axis point** (300, not the 500 total) against the goal (600, "-50%",
    red). A new measure is written to TMDL as `measure 'Target Amount' = 600` with `formatString: 0`
    and a `lineageTag`.
  - **Target also accepts a column**, which Desktop stores as an implicit aggregation: `{"field":
    {"Aggregation": {"Expression": {"Column": {"Expression": {"SourceRef": {"Entity": "Sales"}},
    "Property": "Amount"}}, "Function": 0}}, "queryRef": "Sum(Sales.Amount)", "nativeQueryRef":
    "Sum of Amount"}` (Desktop shows "Sum of Amount"; `Function` 0 is Sum, and probe 13 adds 1 for
    Average and 5 for Count). Specs have no syntax for this, so the `target` slot accepts measures only. The
    reader reads it as an `aggregation` field, shown as `Sum(Sales[Amount])` in the manifest.
  - **`queryState` roles are written in alphabetical order**, not well order: `Goal`, `Indicator`,
    `TrendLine` (the wells read Value, Trend axis, Target). That matches every type seen so far
    (`Category`/`Y`, `Values`, `Data`), so `render` sorts roles.
  - **Desktop accepts Blueprint's line, bar and drill-down pie as written (probe 14,**
    `scripts/probe_apply_charts.py`; evidence `docs/probes/14-apply-charts.diff`). Two specs were
    applied to fixture 02 plus a calculated date column added straight to `Sales.tmdl` (the DAX from
    probe 13, without the automatic date tables). Then the user opened, saved, inspected and
    drilled:
    - Every chart was drawn with its title. The bar and pie drill-downs worked down and back up.
    - **A date column bound as a plain `Column` works:** the line chart drew it, and Desktop kept the
      binding. Desktop **did not create the automatic date tables** for a column added outside it
      (no TMDL changed). So `Order Date` had no Date Hierarchy, and the chart couldn't drill by year.
    - On save Desktop changed only UI state on Blueprint's visuals. It added the automatic `filterConfig` filters to three
      of the four, raised their `$schema` to 2.14.0, and flipped drill `active` flags. Re-running
      `bp apply` with both specs then reported **no changes**, and `bp check` found nothing on either
      page.
  - **Line and clustered bar charts (probe 12,** `scripts/probe_line_bar.py`; evidence
    `docs/probes/12-line-bar.diff`). Desktop's names are Line chart and Clustered bar chart.

    | Wells | `visualType` | `queryState` roles | Added by Desktop |
    |---|---|---|---|
    | Line chart: X-axis, Y-axis, Legend | `lineChart` | `Category` (column, `"active": true`), `Y` (measure), `Series` (Legend, no `active`) | `sortDefinition` descending on the measure |
    | Clustered bar chart: Y-axis, X-axis | `clusteredBarChart` | `Category` = the **Y-axis** (categories, an ordered drill-down: Country then Region), `Y` = the **X-axis** (measure) | `sortDefinition` ascending on each category level, as for the column chart |

    - **A bar chart is stored like the column chart:** the roles are named by meaning, not by screen
      axis, so the categories are `Category` even though they're drawn on the Y-axis.
    - Drilling back up set Region's `active` to `false` (drill state, probe 11). Both charts also got
      the automatic `filterConfig` filters, which is filter-pane state (probe 05). The plain open and save
      changed nothing this time.
    - A drill-down of plain columns on the line chart's X-axis, and a second Legend column: settled
      by probe 27 (below).
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

**Verified 2026-11-09, probe 13** (`scripts/probe_field_shapes.py`; evidence
`docs/probes/13-field-shapes.diff`, fixture 02 with automatic date/time on, all content invented):

- **A calculated date column** (`Order Date = DATE(…)`, added in Desktop) is written to TMDL as
  `column 'Order Date' = DATE(…)` with a `variation Variation` block (`isDefault`, a `relationship`,
  `defaultHierarchy: LocalDateTable_<guid>.'Date Hierarchy'`). Desktop also added two hidden tables,
  `DateTableTemplate_<guid>` and `LocalDateTable_<guid>`, plus their `ref table` lines in
  `model.tmdl` and a `relationships.tmdl`. `semantic.py` reads this model and resolves
  `Sales[Order Date]`.
- **Dragging the date column into an axis binds its date hierarchy, one projection per level**:
  `{"field": {"HierarchyLevel": {"Expression": {"Hierarchy": {"Expression":
  {"PropertyVariationSource": {"Expression": {"SourceRef": {"Entity": "Sales"}}, "Name":
  "Variation", "Property": "Order Date"}}, "Hierarchy": "Date Hierarchy"}}, "Level": "Year"}},
  "queryRef": "Sales.Order Date.Variation.Date Hierarchy.Year", "nativeQueryRef": "Order Date
  Year"}`, then Quarter, Month and Day. Only Year was `active` at first. Choosing *Order Date* in the
  well's menu set every level `active` (expand) and **did not switch to the plain column**.
  Probe 14 settled how Blueprint binds a date: `Table[Column]` as a plain `Column`, which Desktop draws
  and keeps as written.

**Verified 2026-11-11, probe 40** (`scripts/probe_accept_options_hierarchy.py`; evidence
`docs/probes/40-accept-options-hierarchy.diff`). The acceptance half for probes 37-39: five pages
where **every visual, every option and both hierarchies came from a spec** through the shipped
contracts, with nothing patched onto the files. A candidate probe says Desktop takes a shape;
this says Desktop takes what Blueprint writes. All seven predictions held.

- **Every legend value drew on all four types** — `top`, `bottom`, `left`, `right` and `off` on
  `pie`, `donut`, `scatterChart` and `map`. That includes the cells no earlier probe had seen:
  `'Bottom'` and `'Left'` on pie and donut, `'Left'` on scatter and map. The contracts declare
  the four positions from one property's literals, and this is the probe that tested them.
- **`labels: "on"`/`"off"` showed and removed the detail labels on pie and donut**, the pair
  probe 37 licensed, now written by `bp apply` rather than patched.
- **A matrix with `rows: Sales[Geography]` and a slicer with `field: Sales[Geography]`, both from
  a spec, drew as Desktop's own did** in probe 39: the matrix expandable from Country to Region
  (FR 200 -> East 150, West 50; total 500), the slicer showing `Country, Region` with expanders.
  `render` wrote the matrix's Rows first-level-active with an explicit `false` below, and the
  slicer's Field with every level active (`active_levels: all`).
- **The save changed no option object and no projection Blueprint wrote.** Only Desktop's own
  additions appeared: `"active": true` on each scatter's `X` (probes 34, 36, 38), the matrix's
  `Region` flipped active with `expansionStates` where the user expanded it, the `$schema` bump
  on the files it rewrote, and `pages.json` `activePageName`.
- **A hierarchy slicer draws expanded with nothing saved for it.** The user expanded the matrix
  here and **not** the slicer, yet the slicer rendered `FR` and `UK` open to their regions and
  the file carries no `expansionStates` — so what Blueprint writes (`active_levels: all`) is
  already the expanded state, and the expanders in probe 39's capture of the candidate slicer
  need no saved state behind them either. A matrix is the opposite: its deeper level stays
  `false` until someone expands it, which is then recorded.
- **`bp check` reports no `format` findings**, and **re-applying the same specs over Desktop's
  save changed nothing at all** — not even the manifest, so the bindings fingerprint survives
  Desktop's flags and expansion state.


**Verified 2026-11-11, probe 39** (`scripts/probe_hierarchy_matrix_slicer.py`; evidence
`docs/probes/39-hierarchy-matrix-slicer.diff`). Binding a hierarchy built in the model has been
core since probes 16-19, but `matrix` and `slicer` refused one for lack of a probe, and both
contracts said so. This probe made both claims at once: the user built Desktop's own matrix and
slicer on `Geography` by hand (the authority on the shape), and `bp apply`'s matrix and slicer
carried candidate projections copied from Blueprint's own column chart. The user's three steps
landed in one save, so the evidence has one Desktop step. Predictions P1-P7 are in the script.

- **Dragging the hierarchy into either well shows `Geography` as a root with `Country` and
  `Region` under it** — one field in the UI, levels underneath, as on a chart's axis.
- **Desktop's own matrix** writes one `HierarchyLevel` projection per level in `queryState.Rows`,
  in level order, exactly the shape probe 16 recorded (`queryRef` `Sales.Geography.Country`,
  `nativeQueryRef` `Geography Country`). P1 held.
- **Only the first level is active in a matrix's Rows, and the deeper one carries an explicit
  `"active": false`** — not an omitted flag. P2 held in substance (I was least sure of it, since
  a matrix expands rather than drills), and the explicit `false` is the part worth having.
- **Desktop's own slicer** writes both levels in `queryState.Values` with **`"active": true` on
  each**, as probe 20 recorded for two plain columns in a slicer. P3 held.
- **Desktop accepts the candidates unchanged, and they are its own shape exactly.** Compared
  projection by projection, the candidates as written equal Desktop's own — same keys, same
  order, same flags — in the matrix's `Rows` and the slicer's `Values` alike. The save did not
  rewrite the candidate slicer at all, and changed the candidate matrix only by flipping `Region`
  to `"active": true`, which the user's expand explains (Desktop's own matrix, left unexpanded,
  kept `false`), plus `expansionStates`. P4 held.
- **But only the matrix's flags are `render`'s today.** The candidate matrix's projections are
  `render`'s column-chart output moved across (first level active, the rest an explicit `false`),
  and that is what Desktop writes for a matrix. The candidate **slicer**'s every-level-active was
  set by the probe on purpose, because probe 20 suggested it — so what this settles is that
  Desktop writes and accepts that shape, **not** that `render` emits it. Letting `slicer.field`
  take a hierarchy therefore needs a `render` change as well as an `accepts:` entry.
- **`expansionStates` is written at `visual.expansionStates`, not under `query`.** Desktop's own
  slicer gained one when the user expanded a node (P3's second half held); its own matrix, never
  expanded, has none and kept `Region` inactive; the candidate matrix gained one when expanded.
  The candidate slicer has none — probe 40 then showed why: a hierarchy slicer Blueprint writes
  draws **expanded** with nothing saved for it.
- **Both drew.** The matrix shows `FR`/`UK` with expanders (FR -> East 150, West 50; total 500);
  the slicer shows `Country, Region` with `FR` and `UK` expanding to their regions.
- Otherwise only what any save changes: `$schema` 2.13.0 -> 2.14.0 on the files it rewrote and
  the condition-less auto `filterConfig` on the control column chart (P7).


**Verified 2026-11-11, probe 38** (`scripts/probe_scatter_map_options.py`; evidence
`docs/probes/38-scatter-map-options.diff`). `scatter` and `map` came into the core with probes 34
and 36 carrying **no options at all**, while the other seven chart types take `labels` and
`legend`. The bindings were written by `bp apply` from the shipped contracts; only the option
objects were candidates, and a control with no `objects` on each page settles the default.
Predictions P1-P8 are in the script.

- **`objects.legend[0].properties.position` moves the legend on `scatterChart` _and_ on `map`**
  (`'Right'`, `'Top'`), and **`show = false` leaves no legend** on either. The map was P4, the
  least sure prediction of the three probes: it renders through a different control, so it might
  have had its own property names or no formatting object at all. It takes the same one.
- **`objects.labels` is not an object these two types have, and Desktop _deletes_ it.** It
  changed nothing visible on either, and the save removed the object from all four visuals that
  carried it — on the active scatter page and on the map page alike, the latter otherwise
  untouched. P3 (data labels on a scatter) **failed**; P5 (a no-op on the map) held and is
  stronger than predicted: writing `labels` there is not ignored, it is undone. So neither
  contract gets `labels`. Which object *does* carry a scatter's point labels is open: the script
  named `categoryLabels` as its candidate, and nothing here probed it.
- **Both default to a legend at the bottom and no labels.** Pie and donut default to a legend at
  the **right** (probe 37), so the default legend position is per type, not one theme-wide value.
- **Desktop re-added `"active": true` to each scatter's `X` projection**, as probes 34 and 36
  found; Blueprint still leaves that flag to Desktop.
- **What a save rewrites is still open.** Here Desktop rewrote all six visuals on the active
  scatter page and, on the map page, only the two carrying the rejected object; the three map
  legend visuals it left alone, so their objects are on disk byte for byte. That does *not*
  settle a rule: all six scatters also had a change Desktop had to make (the `active` flag), so
  "the active page" and "only what must change" both fit this probe. Probe 37's save rewrote **no
  visual at all** although `activePageName` moved to a candidate page, which rules the first one
  out; probe 35 rewrote two visuals whose only change was the `$schema` bump and an auto
  `filterConfig`, which the second doesn't explain. No `filterConfig` appeared here. Treat each
  probe's observation as a fact and the rule as unsettled.


**Verified 2026-11-11, probe 37** (`scripts/probe_pie_donut_options.py`; evidence
`docs/probes/37-pie-donut-options.diff`). `pie` and `donut` were the last two core chart types
with no options at all: they were promoted (probes 08, 11, 22-24) for their *bindings*, and the
parity pass probe 35 made before promoting the area and stacked charts never covered them. The
bindings were written by `bp apply` from the shipped contracts, so only the option objects were
candidates; a control with no `objects` on each page settles the type's default. Predictions
P1-P8 are in the script.

- **`objects.labels[0].properties.show` controls the detail labels on `pieChart` and
  `donutChart`**, the same object name the cartesian charts use. P5 (that these types might keep
  them under another object, since Desktop's pane calls them "Detail labels") **failed**, which
  was the point of writing it.
- **Their default is labels _on_**, unlike every charted type probed before: the control showed
  `200 (40%)` / `300 (60%)` on its slices, `show = false` removed them, and `show = true` was
  indistinguishable from the control. So a `labels` option on these two types needs **both**
  values (`"on": "true"` and `"off": "false"`), where `column` ships only `"on"` (probe 23).
- **`objects.legend[0].properties.position = 'Top'` moves the legend above both types**, and
  **`show = false` leaves no legend**, as on the core's other seven chart types (probes 23, 32,
  35).
- **Their default legend sits at the _right_**, not at the theme's bottom that probe 35's area
  control showed. So `position = 'Right'` is indistinguishable from the default on these two, and
  the default position is per type, not a single theme-wide one.
- **`pieChart` and `donutChart` behaved identically in every cell**, as probe 22 found for their
  bindings: the two differ only in `visualType`.
- **The save rewrote no `visual.json` at all.** Every candidate is still on disk byte for byte,
  without the `$schema` 2.13.0 -> 2.14.0 bump or the condition-less auto `filterConfig` that
  probe 35 saw on its active page; only `pages.json` `activePageName` changed. P7 predicted that
  bump and filter and was wrong in this direction: what Desktop rewrites on a save is narrower
  than "the active page", so neither is owed on a save that touches nothing.

**Verified 2026-11-11, probe 36** (`scripts/probe_apply_scatter_card_map.py`; evidence
`docs/probes/36-apply-scatter-card-map.diff`). The acceptance probe for probe 34's three types:
every visual built by `bp apply` from a spec, nothing patched. All four predictions held.

- **Desktop draws and keeps Blueprint's own `scatterChart`, `multiRowCard` and `map`.** The save
  rewrote only the three scatters; the two cards and the two maps it did not touch.
- **Desktop adds `"active": true` to a scatter's `X` projection itself**, on all three, and
  changed nothing else. Blueprint leaves it out on purpose (`active` marks a column's drill
  state and `X` takes a measure), so the flag is Desktop's, like a Category list's drill state.
- **Re-applying the same specs on the saved report changed nothing at all** — not even the
  manifest — so the `active` Desktop added is not fought over.
- `bp check` reports no `format` findings on the result.
- The maps drew without the security setting being touched again, so it had stuck across a
  Desktop restart (probe 34 saw the message return after a refresh).

**Verified 2026-11-11, probe 35** (`scripts/probe_even_chart_options.py`; evidence
`docs/probes/35-even-chart-options.diff`). `labels` and `legend` were verified unevenly across the
charts still in the archive, by which probe happened to cover which type — area had no options at
all, `stacked-column` had no verified legend position, and none of the four had `legend: off`
(probe 32 wrote that only on the core's clustered column, clustered bar and line). This probe
closed the seven missing cells so they could be promoted without carrying the gap in. The
bindings were written by `bp apply` from the archived contracts, so they are acceptance-verified
too; only the option objects were candidates.

- **`objects.labels[0].properties.show = true` shows data labels on an `areaChart`** — on both
  series (600/600 and 200/300). It was the open one: probe 23 only ever put that object on the
  column and the three stacked charts.
- **`objects.legend[0].properties.position = 'Right'`** moved the legend on the `areaChart` and on
  the stacked column (`columnChart`), the two the earlier probes missed.
- **`objects.legend[0].properties.show = false` hides the legend** on `areaChart`, `columnChart`,
  `hundredPercentStackedColumnChart` and `barChart`, as it does on the core's three (probe 32). A
  control with no `legend` object kept its legend at the theme's default (bottom), so the hidden
  ones are genuinely changed.
- **The save rewrote only the two visuals on the active page**, keeping their objects exactly and
  adding Desktop's usual `$schema` bump and condition-less auto `filterConfig`; the other six
  files it did not touch at all, so what was written is still on disk byte for byte. (Probes 33
  and 34 showed the same: Desktop rewrites some visuals on a save and leaves others alone.)

**Verified 2026-11-11, probe 34** (`scripts/probe_map_scatter_card.py`; evidence
`docs/probes/34-map-scatter-card.diff`). The three types real reports use that no contract covers,
written as candidates and drawn by Desktop, then kept through a refresh and save. A survey of the
three sample reports (counts only) is what picked them: `multiRowCard` 6, `map` 4, `scatterChart`
3. Predictions P1-P7 are in the script.

- **`multiRowCard`**: role `Values`, no `active`, no objects. One measure draws one value; **two
  measures draw both, side by side in one row**; a **column beside a measure draws one row per
  value** (FR 200, UK 300) — grouping, which is what the type is for. The samples only ever
  showed one field, so all three were open.
- **`scatterChart`**: `Category` (column, `"active": true`, and a drill list works), `Series`
  (column, no `active`), `Size` (measure), `X` (measure), `Y` (measure). Roles alphabetical.
- **Desktop adds `"active": true` to the scatter chart's `X` projection.** It was written without
  one and the save added it to all three scatters — and both sample files carry it, so it is
  Desktop's convention for that well, not drill view state. A `scatter` contract therefore needs
  `active: true` on **both** `category` and `x` (`slots.Slot.active`).
- **`map`**: `Category` (column, `"active": true`), `Series` (column), `Size` (measure). Desktop
  geocoded `FR`/`UK` from the **column name alone** — the fixture's `Country` has no
  `dataCategory` in TMDL — and drew a bubble per country sized by the measure, the `Series`
  variant splitting each bubble into segments with a legend.
- **Map visuals are off by default in Desktop** ("Map and filled map visuals are disabled. To
  enable them, go to File > Options and settings > Options > Global > Security"). Until that is
  switched on, Desktop never reads the shape, and after a data refresh the message came back
  although the setting was still on (it appears to need a restart). So a map Blueprint writes
  draws only where that setting is on: the contract has to say so, and a probe on a map needs it
  enabled first.
- The save also wrote `settings.customMemoryLimit`, `customTimeoutLimit` and `queryLimitOption`
  into `report.json` — from opening the Options dialog, not from anything Blueprint wrote. The
  writer patches documents in place, so properties like these survive untouched.

**Verified 2026-11-11, probe 33** (`scripts/probe_apply_legend_totals.py`; evidence
`docs/probes/33-apply-legend-totals.diff`, the demo's model on fixture 02). The acceptance probe
for probe 32's shapes: **everything was written by `bp apply`**, nothing patched by hand, then
drawn, refreshed and saved by Desktop (predictions A1-A4 are in the script).

- **Desktop draws and keeps what Blueprint wrote.** A Legend `Series` on a clustered column and bar
  (alone, beside a drill-down, with `legend: bottom`/`right`), `legend: off` (`show: false`) on a
  column, a bar and a line, `legend: top`, and a table's `totals: "off"`/`"on"` all drew as in probe
  32, with no error. The save changed no `Series`, `objects.legend` or `objects.total`
  (`tests/test_probe_replay.py::test_33_desktop_keeps_the_legend_column_legend_off_and_totals`).
- **What the save did change:** 11 of the 15 data visuals had `$schema` raised 2.13.0 -> 2.14.0 and
  gained condition-less auto `filterConfig` entries (Categorical for a column, Advanced for a
  measure); 4 were untouched (`lb-col`, `lb-bar`, `tt-off`, `tt-on`; the reason is not known).
  On the bar drill-down it flipped the second Category level `active` true -> false: that is drill
  view state (probe 11), and the reader ignores it.
- **Re-applying the same specs on the saved report changed nothing**, not even the manifest.
- **`legend: off` -> `legend: top` on re-apply** rewrote only that visual (`show: false` removed,
  `position: 'Top'` written) and Desktop, reloaded through the bridge, drew its legend on top. A
  capture taken right after a reload can be blank (a mid-reload frame); the next one drew every chart.

**Verified 2026-11-11, probe 32** (`scripts/probe_legend_totals.py`; evidence
`docs/probes/32-legend-totals.diff`, the demo's model on fixture 02). Candidates written by hand
after `bp apply` built verified shapes, drawn by Desktop, then kept through a real refresh and save
(which changed nothing but `pages.json` `activePageName`). Predictions P1-P6 are in the script.

- **A Legend column on a clustered column and a clustered bar** is `queryState.Series.projections =
  [<Column>]`, no `active`, roles alphabetical (`Category`, `Series`, `Y`), `visualType` unchanged
  (`clusteredColumnChart`, `clusteredBarChart`). Desktop draws one colour per Legend value, side by
  side, with the legend below the chart. Both types behave alike, so `bar` can keep inheriting
  `column`.
- **A drill-down `Category` (Country, Region, both `active`) together with a Legend (Order Date)**
  draws on both: the axis expanded, one colour per Legend value, as on the stacked charts (probe 28).
- **Several measures together with a Legend column are refused** on the clustered charts too: the
  tile shows only "There's too many columns in the Legend bucket. Please remove some.". So are
  **two Legend columns** (probe 27 showed this on line). The contract needs `list_excludes:
  [legend]` on `value` and a single-column `legend` slot, as `line` has.
- **`objects.legend[0].properties.show = Literal false` hides the legend** on a clustered column, a
  clustered bar and a line chart (each with two measures, so a legend of measure names would show),
  alone and beside `position: 'Right'`. Written `show: true` beside `position: 'Top'` it shows at
  the top; with no `legend` object the legend shows at the theme's default (bottom here). All kept
  as written through the save.
- **`objects.total[0].properties.totals = Literal false` removes a table's Total row**; `true`
  and no `total` object both show it (Desktop's default is on), so only the `false` needs
  writing. Kept as written through the save.

**Verified 2026-11-10, probe 31** (`scripts/probe_bar_line_sort.py`; evidence
`docs/probes/31-bar-line-sort.diff`, fixture 02 plus probe 20's `Target Amount`).

- **`labels` and `legend` work on the clustered bar and the line.** Probe 23 verified
  `objects.labels[0].properties.show = true` and `objects.legend[0].properties.position` on the
  column and stacked charts only. Written here onto a `clusteredBarChart` (legend `'Right'`) and a
  `lineChart` (legend `'Top'`) as candidates, Desktop drew both — data labels and the legend where
  asked — and its save changed nothing but `pages.json` `activePageName`. So the shapes are the
  same across the core chart types.
- **An explicit sort writes no `isDefaultSort`.** `query.sortDefinition` is
  `{"sort": [{"field": <field>, "direction": "Ascending"|"Descending"}]}`, and the
  `"isDefaultSort": true` seen until now marks only the sort **Desktop** adds by itself. The
  user's own "Sort axis" choice (step 02, a measure descending; step 03, a table column
  ascending) wrote the key without it.
- **Sorting back to Desktop's own default does not restore it** (step 04: back to Country
  ascending changed only `field` and `direction`). So the flag says who chose the sort, not what
  the sort is — in the same saved report, the two visuals the user sorted have no `isDefaultSort`
  while the untouched card and chart still carry `isDefaultSort: true`.
- A sort Blueprint writes from a spec is therefore an explicit one: the key without
  `isDefaultSort`.

**Verified 2026-11-13, Desktop 2.159.1231.0, probe 41** (by hand; evidence
`docs/probes/41-sort-by-aggregate.diff`, a financial PBIP built by `bp apply`, not fixture 02, so
it is not replayed). The user set a table's sort to its `Sum of Profit` column, descending, and
saved.

- **A sort on an aggregated column is an `Aggregation` field**, not the bare column:
  `sortDefinition.sort[0].field = {"Aggregation": {"Expression": {"Column": …}, "Function": 0}}`,
  the same `Function` code as the projection it sorts on (here Sum = 0), and no `isDefaultSort`
  (as probe 31). Before this, a spec `sort.by` on an aggregated column wrote the bare `Column`,
  which no Desktop save produced.
- **Every aggregate follows the same rule.** Four more steps on the same table, each changing the
  aggregate of the Profit column and sorting on it: Count (5), Average (1), Max (4) and Count
  (Distinct) (2). In each, the sort's `Aggregation.Function` equals the projection's. Min (3) was
  not run; it uses the same rule and probe 29's code.

**Verified 2026-11-10, probe 29** (`scripts/probe_aggregate_format.py`; evidence
`docs/probes/29-aggregate-format.diff`, fixture 02, all content invented). Each aggregation was
chosen on a **fresh** field, because an aggregation changed in place keeps the field's old
`queryRef` (probe 13, and seen again here in step 08).

- **Every `Function` code**, from Desktop's own output. The codes do **not** follow the menu
  order, and the two counts are the trap: the UI's "Count" is 5 and "Count (Distinct)" is 2.

  | Desktop's menu | `Function` | `queryRef` | `nativeQueryRef` |
  |---|---|---|---|
  | Sum | 0 | `Sum(Sales.Amount)` | `Sum of Amount` |
  | Average | 1 | `Avg(Sales.Amount)` | `Average of Amount` |
  | Count (Distinct) | 2 | `Count(Sales.Amount)` | `Count of Amount` |
  | Minimum | 3 | `Min(Sales.Amount)` | `Min of Amount` |
  | Maximum | 4 | `Max(Sales.Amount)` | `Max of Amount` |
  | Count | 5 | `CountNonNull(Sales.Amount)` | `Count of Amount` |

- **`nativeQueryRef` is a display name, unique within the visual.** Count and distinct count of
  one column are both "Count of <Column>" (the user saw "Count of Country" for both in the
  wells), so when the second one collided Desktop wrote `Count of Amount1`. A spec binding both
  of the same column in one visual is refused rather than guessing that suffix rule.
- **Changing an aggregation in place leaves a stale `queryRef`:** step 08's distinct count of
  `Country` still said `"queryRef": "Sales.Country"`. Never copy a shape from a changed field.
- **A per-visual data format is a projection key**, exactly where the vendored schema
  (visualConfiguration 2.8.0) describes it: `"format"`, a format string "scoped to the visual",
  beside `queryRef`/`nativeQueryRef`. Desktop wrote a three-part positive;negative;zero string
  carrying the **locale's** currency symbol:
  `"format": "\"₹\" #,0.###############;\"₹\" -#,0.###############;\"₹\" #,0.###############"`.
  So a format is a string the client gives, not a name Blueprint maps: a `currency` alias would
  have to invent a symbol that the probe shows is the user's choice.
- **A measure's format is a different thing:** setting Format on the ribbon (Measure tools)
  changed TMDL only — `formatString: \$#,0.###############;(\$#,0.###############);…` — and left
  the report untouched. The model is read-only to Blueprint, so `format:` is the report-side one.
- **No "Display units" on the new card** in this build: that part of the probe (step 10) was
  skipped, so display units stay unverified.

**Verified 2026-11-10, probe 30** (`scripts/probe_apply_aggregate.py`; evidence
`docs/probes/30-apply-aggregate.diff`). Probe 29 recorded Desktop's own shapes; this one is the
other claim, that **Desktop accepts them from Blueprint**. `bp apply` built two pages on fixture
02 — all six aggregations across cards and column charts, and four format strings across cards, a
column chart and a table mixing an aggregated column with a measure — and the user refreshed and
saved.

- **Desktop drew every one** (bridge captures, `_screenshots/30-apply-aggregate/`): Sum 500,
  Average 125.00, distinct count 4, Min FR 50 / UK 100, Max FR 150 / UK 200, Count 2 / 2, and the
  formats as `500`, `500.00`, `$ 500.00`, a percent axis, and `$200.00`/`$300.00` on the
  aggregated table column beside an unformatted measure. Desktop wrote its own subtitles from the
  bindings ("Min of Amount by Country"), so it read them as its own.
- **The save changed nothing Blueprint wrote.** No `queryRef`, `nativeQueryRef`, `format`,
  `Aggregation` or `Function` differs. Desktop only raised each changed file's `$schema`
  2.13.0 -> 2.14.0, added its usual condition-less auto `filterConfig` (here an `Advanced` filter
  on the aggregated field) and rewrote `pages.json` `activePageName`, all of which it does to any
  visual it touches.

- **Aggregation codes:** "Average of Amount" is `Function: 1` and "Count of Region" (a text column) is
  `Function: 5`. Desktop kept the field's old `queryRef` (`Sum(Sales.Amount)` on the Average,
  `Sales.Region` on the Count), so a `queryRef` says nothing reliable about the aggregation.
- The reader reads these as `date_level` fields (`Sales[Order Date].Year` in the manifest) and
  `aggregation` fields (`Average(Sales[Amount])`).

**Verified 2026-11-09, probe 16** (`scripts/probe_user_hierarchy.py`; evidence
`docs/probes/16-user-hierarchy.diff`, fixture 02, all content invented). A hierarchy built in the
Data pane (Create hierarchy on Country, renamed Geography, then Region added):

- **TMDL:** a table member `hierarchy Geography` (one tab, with a `lineageTag`) holding `level
  Country` and `level Region` (two tabs), each with `lineageTag` and `column: <column>`, in level
  order. `semantic.py` reads it as `hierarchies[("Sales", "Geography")] = ("Country", "Region")`.
- **In a visual each level is its own projection**, the same `HierarchyLevel` as a date hierarchy
  but on the table directly: `{"HierarchyLevel": {"Expression": {"Hierarchy": {"Expression":
  {"SourceRef": {"Entity": "Sales"}}, "Hierarchy": "Geography"}}, "Level": "Country"}}`,
  `"queryRef": "Sales.Geography.Country"`, `"nativeQueryRef": "Geography Country"`. On a column
  chart's X-axis the levels are a drill-down (Country `active`, Region not). `sortDefinition` sorts by
  the same `HierarchyLevel` fields.
- **Dragging one level into a table added the whole hierarchy** (Country and Region, no `active`).
- The reader reads these as `hierarchy_level` fields, shown as `Sales[Geography].Country`. A spec
  binds one by writing it like a column (`Sales[Geography]`). `apply` expands it to these level
  projections, matching Desktop's step 03 and 04 queries exactly (first level `active` in `Category`,
  no `active` in a table's `Values`). It's allowed in the column chart's category and the table's
  columns, and (probe 18) in the bar, pie and line charts' categories; elsewhere it's refused as unverified.
- **Desktop accepts these as written (probe 17,** `scripts/probe_apply_hierarchy.py`; evidence
  `docs/probes/17-apply-hierarchy.diff`). Probe 16's hierarchy was added to fixture 02's TMDL, then
  `bp apply` ran with a column chart and a table on `Sales[Geography]`. Both were drawn: the column
  chart showed UK and FR and drilled to regions, and the table showed Country, Region and Total Amount.
  The X-axis well showed Geography. On save Desktop kept the queries apart from the drill `active` flags,
  kept the annotations, and added only the automatic `filterConfig` filters. It also raised both visuals'
  `$schema` from 2.13.0 to 2.14.0, so a re-apply rewrites **only the manifest**, which records schema
  versions and is now stale.
- **Bar, pie and line charts bind it the same way (probe 18,** `scripts/probe_bar_pie_hierarchy.py`;
  evidence `docs/probes/18-bar-pie-hierarchy.diff`). With Geography dragged onto a clustered bar
  chart's Y-axis, a pie's Legend and a line chart's X-axis, each got `Category` = the two
  `HierarchyLevel` projections (Country `active`, Region not) plus `Y` = the measure, the same as the
  column chart in probe 16. All three drilled from Country to Region. On the line chart this verified a
  drill-down *through a hierarchy*; a list of plain columns came with probe 27.
- **Desktop accepts Blueprint's bar, pie and line charts on a hierarchy (probe 19,**
  `scripts/probe_apply_hierarchy_charts.py`; evidence `docs/probes/19-apply-hierarchy-charts.diff`).
  All three were drawn with their titles, showed UK and FR, and drilled to regions and back. On save
  Desktop kept their queries apart from the drill `active` flags, kept the annotations, and added only
  the automatic `filterConfig` filters.
- **Slicer, matrix, and charts with two measures (probe 20,** `scripts/probe_slicer_matrix_measures.py`;
  evidence `docs/probes/20-slicer-matrix-measures.diff`). Built in Desktop on fixture 02 after
  adding `Target Amount = 600` (TMDL as in probe 10). The user saved without snapping between
  steps, so the evidence is one section, the final state; what plain open-and-save rewrites isn't
  re-recorded here (probe 12 did).

  | Desktop (wells) | `visualType` | `queryState` | Desktop adds |
  |---|---|---|---|
  | Slicer (plain): Field = Country, Region | `slicer` | `Values`: both columns, in well order, **each `"active": true`** | `expansionStates` (an expanded node, view state), `filterConfig`, `drillFilterOtherVisuals` (no sort) |
  | Matrix: Rows, Columns, Values | `pivotTable` | `Columns` (Region, `active`), `Rows` (Country, `active`), `Values` (Total Amount, Target Amount in well order, no `active`); roles alphabetical | `filterConfig` (Categorical for columns, Advanced for measures), `drillFilterOtherVisuals` (no sort) |
  | Clustered column / bar, line: two measures on the value axis | unchanged | `Category` as before; `Y`: **one projection per measure**, no `active` | `sortDefinition` descending on the first `Y` measure (`isDefaultSort`), `filterConfig` |

  - Slicer style **Dropdown** is `visual.objects.data[0].properties.mode = Literal "'Dropdown'"`.
    Blueprint doesn't write it (Desktop's default style applies).
  - Each chart showed two series with a legend (user). The charts' `Y` lists Target Amount first
    and the matrix Total Amount first: that's the order the fields were dropped in. **Desktop
    doesn't reorder `Y`** (probe 21: Blueprint wrote Total first, and Desktop's save kept it).
  - Not probed, so not accepted by the contracts: a model hierarchy in a slicer or matrix, and a
    line chart with a Legend and more than one measure (Desktop allows one `Y` value then).
  - Blueprint renders all five exactly as Desktop wrote them, `active` included
    (`tests/test_probe_replay.py::test_20_spec_writes_desktops_queries`). `active` depends on the
    visual type: chart `Category`, slicer `Values`, matrix `Rows`/`Columns` (`render.ACTIVE_BY_TYPE`).
- **Desktop accepts Blueprint's slicer, matrix and two-measure charts (probe 21,**
  `scripts/probe_apply_slicer_matrix.py`; evidence `docs/probes/21-apply-slicer-matrix.diff`). The
  first probe driven through the Desktop Bridge CLI (`scripts/desktop.sh`): opened, inspected with
  two page captures, then the user refreshed the data and saved. All five visuals drew with their
  titles; the slicer as a list (FR > East, West; UK > North, South), the matrix with Region across
  and both values under each, each chart two series with the legend Total Amount, Target Amount.
  On save Desktop changed no query (`test_21_desktop_kept_every_query_blueprint_wrote`), kept the
  annotations, and only added `filterConfig` and raised `$schema` to 2.14.0 on the bar and line
  charts (as in probes 17, 19); the slicer, matrix and column chart files weren't rewritten.
- **Chart variants and the Dropdown slicer, as candidate shapes (probe 22,**
  `scripts/probe_chart_variants.py`; evidence `docs/probes/22-chart-variants.diff`). Blueprint wrote
  each candidate as a verified sibling's query under another `visualType`, and Desktop opened them:

  | Spec type | `visualType` | `queryState` (as written and drawn) |
  |---|---|---|
  | `stacked-column` | `columnChart` | `Category` (column, `active`), `Series` (Legend column, no `active`), `Y` |
  | `stacked-column-100` | `hundredPercentStackedColumnChart` | as `columnChart` |
  | `stacked-bar` | `barChart` | as `columnChart` |
  | `donut` | `donutChart` | `Category` (Legend, `active`), `Y`, as the pie |
  | `area` | `areaChart` | `Category` (`active`), `Series` (Legend), `Y`, as the line chart |
  | slicer `options: {style: dropdown}` | `slicer` | `objects.data[0].properties.mode = 'Dropdown'` (probe 20's literal) |

  One page capture showed each drawn correctly with data and no error (the stacks by Region, the
  donut's shares, the slicer as a dropdown; the area chart as one point per region, because each
  region belongs to one country in the fixture). Desktop reported no unsaved changes, and a Ctrl+S
  wrote nothing: **an untouched open isn't dirty, so it doesn't save** (probe 21's first save
  attempt was the same). So the evidence is "drawn as written, nothing to change", not a save
  diff. Verified only as probed: one category column, one measure, the donut without Details.
- **Drill-downs, measure lists, Details, data labels and legend position on candidates (probe 23,**
  `scripts/probe_chart_options.py`; evidence `docs/probes/23-chart-options.diff`). Opened through
  the bridge, then changed on disk and **reloaded** (`file.reload`) four times, one page capture per
  round; every candidate drew as written, with no error and nothing dirty.

  | Verified | On | How Desktop drew it |
  |---|---|---|
  | `Category` drill list (Country, Region, both `active`) | `columnChart`, `hundredPercentStackedColumnChart`, `barChart`, `donutChart` | expanded to Country > Region |
  | `Y` with two measures | `barChart`, `columnChart`, `hundredPercentStackedColumnChart`, `areaChart` | the measures stacked (100%: as percentages), or two areas |
  | Details `Series` = Region | `donutChart` | Region segments within each country |
  | `objects.labels[0].properties.show = Literal "true"` | `clusteredColumnChart`, `columnChart`, `hundredPercentStackedColumnChart`, `barChart` | data labels on the bars |
  | `objects.legend[0].properties.position = Literal "'Right'"`, `"'Top'"`, `"'Left'"` | Right and Top on `clusteredColumnChart`, Top on `hundredPercentStackedColumnChart`, Left on `barChart` | the legend moved there |

  - `'Bottom'` drew like every other chart because the theme's default is bottom, so it was
    settled by probe 28 (below). The positions are treated as verified on the chart types that
    offer the option (the property is the same object on each).
  - Several measures together with a Legend on the stacked and area charts: refused by Desktop
    (probe 28).
- **Desktop saves bp apply's chart variants and options unchanged (probe 24,**
  `scripts/probe_apply_variants.py`; evidence `docs/probes/24-apply-variants.diff`). Probes 22 and
  23 had no save diff (nothing dirty). Here `bp apply` built every shape they verified from the
  shipped contracts (14 visuals on two pages, no data cache); the user clicked Refresh now and
  saved. The save landed (the model, base theme and cache were rewritten, byte-identical), and **no
  page or visual file was rewritten**: no `filterConfig` added, no `$schema` raised
  (`test_24_desktops_save_kept_every_blueprint_file`). Re-applying the specs afterwards changes
  nothing. This completes probes 22 and 23's evidence with a real save.
- **Desktop takes Blueprint visuals rebound in place (probe 26,** evidence
  `docs/probes/26-rebind.diff`; built on a copy of probe 21's final state, so its sections replay
  21 first). A re-applied spec rebound three charts (Country with two measures → Region with one),
  swapped a matrix's rows and columns, and cut a slicer to one field. `render.with_bindings`
  rewrote each query as for a new visual and dropped Desktop's own condition-less `filterConfig`
  filters on fields no longer bound (the bar and line charts had them from probe 21's save), the
  sort if it named a gone field, and stale `expansionStates`; formatting, title and position were
  kept. Opened through the bridge: every visual drew with its new fields (one page capture), with
  Desktop's automatic subtitles following the new bindings. Nothing dirty, so no save.
- **A drill-down of plain columns on line and area charts; one Legend column only (probe 27,**
  `scripts/probe_line_drill_legend.py`; evidence `docs/probes/27-line-drill-legend.diff`). Candidates
  on fixture 02 plus probe 14's Order Date, opened through the bridge; the user clicked Refresh now
  and saved, and one page capture followed.

  | Candidate | `visualType` | How Desktop drew it |
  |---|---|---|
  | `Category` drill list (Country, Region, both `active`), the column chart's shape | `lineChart`, `areaChart` | expanded: East, West under FR; North, South under UK |
  | `Series` = Country, Region (two Legend columns, no `active`) | `lineChart`, `areaChart` | no chart, only the error "There's too many columns in the Legend bucket. Please remove some." |

  - The save landed (the data cache was rewritten) and **changed no report or model file**, the
    erroring visuals included (`test_27_desktops_save_kept_every_file`).
  - So `line` and `area` take a list on `category` (a drill-down), rendered exactly as drawn
    (`test_27_drill_down_specs_write_what_desktop_drew`), and the Legend stays one column: a list is
    refused before anything is written. A drill-down together with a Legend: drawn (probe 28).
- **Legend combinations and the 'Bottom' position (probe 28,** `scripts/probe_legend_combos.py`;
  evidence `docs/probes/28-legend-combos.diff`). Candidates on the demo's model with its refreshed
  data cache, opened through the bridge, one capture per page; nothing dirty, so no save. The
  guidelines theme (`bp theme`) had its default legend position set to Top.

  | Candidate | `visualType` | How Desktop drew it |
  |---|---|---|
  | `Category` drill list (Country, Region, both `active`) + `Series` = Order Date | `lineChart`, `areaChart`, `columnChart`, `hundredPercentStackedColumnChart`, `barChart` | expanded Country > Region, one colour per order date |
  | `Y` = two measures + `Series` = Region | `columnChart`, `hundredPercentStackedColumnChart`, `barChart`, `areaChart` | no chart, only "There's too many columns in the Legend bucket. Please remove some." |
  | `objects.legend[0].properties.position = Literal "'Bottom'"`, theme default Top | `clusteredColumnChart` | legend below the chart (the same chart without it: on top) |

  - So a drill-down may go with a Legend on line, area and the stacked charts, several measures
    with a Legend stay refused (now Desktop's own error; on the line chart Desktop's UI allows one
    `Y` value with a Legend, probe 20), and `legend: bottom` is offered with top, left and right.
  - A theme's `visualStyles["*"]["*"].legend = [{"position": "Top"}]` set every chart's default
    legend position (seen on the control chart); Blueprint doesn't write it.

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
