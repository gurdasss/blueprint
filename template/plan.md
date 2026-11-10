# Template Plan

> Client-perspective-first redesign of Blueprint's input files.
> Everything here is a draft. Refine before building.

---

## Goal

Strip the guidelines spec to its **absolute essence** — the 20% of keys that
cover 80% of real client work — and make that core bulletproof. Advanced
features ship later through an **extension system** that clients opt into,
so the base file stays small and learnable.

This branch (`claude/amazing-sagan-ejiuec`) refactors the main-branch code
toward these templates. Reusable code from main is kept; the schema and
validation layer are rewritten.

---

## Scope: the three client inputs

A client (human or LLM agent) provides:

1. **Guidelines** — the organisation-wide design contract (this file).
2. **Layout** — the region geometry for a page shape (referenced by name).
3. **Page spec** — which visuals go on a page, with their bindings.

We design them **in this order**, because each one constrains the next.

---

## Phase 1: Guidelines template (current focus)

### Design principles for the core

1. **One obvious key per concern.** No ambiguity about where a rule lives.
2. **No inheritance, no implicit defaults inside the file.** Every value a
   client sees is one they wrote. Built-in defaults live in code, not in the
   client's file.
3. **Flat where possible.** Nesting is justified only when the group has a
   clear name that a sentence would use ("the page margin", "the brand
   colours").
4. **Nothing the tool can't enforce today.** A key that the tool ignores
   teaches the client to distrust the file. Ship it when the check ships.
5. **Extension-ready.** The core file has a reserved top-level key
   (`extensions:`) for future opt-in sections. The core validator ignores it;
   extension validators read it.

### The core keys (v1 — proposal)

These are the keys every client needs, from a one-page KPI dashboard to a
fifty-page analytical report. Nothing else belongs in the core.

```yaml
version: 1
name: "<Client> Reporting Standard"

canvas:
  width: 1280
  height: 720

spacing:
  grid: 8
  margin: 16          # uniform for v1 (four-sided is an extension)
  gutter: 16          # uniform for v1 (two-axis is an extension)

page:
  max_visuals: 8
  density_policy: data
  require_title: true

palette:
  categorical: ["#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F"]
  background: "#FFFFFF"
  text: "#333333"
  enforce: strict

typography:
  page_title:    { font: Segoe UI Semibold, size: 18 }
  visual_title:  { font: Segoe UI, size: 12 }
  body:          { font: Segoe UI, size: 10 }

layouts:
  search_path: ["layouts"]
  default: standard-4-up
```

### What's in and why

| Key | Why it's core |
|-----|---------------|
| `version`, `name` | Identity. The manifest and `check` report them. |
| `canvas.width/height` | Every client has a fixed page size. Without it, nothing aligns. |
| `spacing.grid` | The grid is what makes `fmt` and `check` deterministic. |
| `spacing.margin` | The safe zone inside the page edge. |
| `spacing.gutter` | The minimum gap between visuals. |
| `page.max_visuals` | The density guard. Prevents visual overload. |
| `page.density_policy` | How visuals are counted (`all`, `visible`, `data`). |
| `page.require_title` | Whether every spec page needs a header. |
| `palette.categorical` | The ordered chart colours. |
| `palette.background/text` | Surface and text colours. |
| `palette.enforce` | `strict` / `warn` / `off`. |
| `typography` (3 roles) | The three roles that cover every visible text element a client cares about in the first pass: page title, visual title, body text. |
| `layouts` | Where to find layout files and which is the default. |

### What's deferred to extensions

| Concern | Why not core |
|---------|-------------|
| Four-sided margins | Most clients use uniform margins. |
| Two-axis gutters | Most clients use a single gutter. |
| Canvas background colour | Cosmetic; not a layout constraint. |
| Brand / semantic / neutral colour groups | Useful but not enforced by any check rule today. |
| `approved_visual_types` allowlist | New concept; needs a new check rule. |
| `approved_layouts` allowlist | New concept; needs a new check rule. |
| `visual_containers` styling | New concept (border, shadow, corner radius). |
| `kpi_value`, `data_label` typography roles | Useful but not essential for the first pass. |
| Per-role `color` in typography | Couples colour to typography; keep colours in `palette`. |
| Per-role `weight` in typography | Power BI encodes weight in the font face name. |
| Validation severity overrides | Power users only. Defaults should be right for most clients. |
| `check.decorative_types` | Edge case for background images/shapes. |

### Open questions

1. **`spacing` vs keeping `grid` + `canvas`?**
   The original has `grid.size` and `canvas.margin/gutter`. Your template
   groups them under `spacing`. The grouping reads well, but it moves
   `margin` and `gutter` away from `canvas` where the code currently expects
   them. Decision: go with `spacing` (cleaner client mental model) and
   update the code.

2. **Typography role names.**
   Current code: `title`, `subtitle`, `callout`, `card_label`, `header`,
   `textbox`. Your template: `page_title`, `visual_title`, `kpi_value`,
   `body`, `data_label`. The core needs only three. Proposed core roles:
   - `page_title` — the big page header text (currently `header`)
   - `visual_title` — chart/card/table titles (currently `title`)
   - `body` — everything else: labels, textboxes, data labels (currently
     spread across `subtitle`, `textbox`, `callout`)

   This collapses six roles to three. Extensions can add `kpi_value`,
   `data_label`, `subtitle`, `card_label` later.

3. **`font` vs `font_family`?**
   `font` is shorter and what the current code uses. `font_family` is more
   explicit. Since the value is a face name (includes weight), `font` might
   mislead. Proposal: keep `font` — it's already established and the YAML
   comment explains it.

4. **Should `page.title_region` be in core?**
   It constrains *where* the header goes. If `require_title` is core,
   `title_region` arguably is too. But it requires knowing layout region
   names. Proposal: leave it out of core v1 — `require_title: true` is
   enough; the region constraint is an extension.

5. **Default validation severities.**
   If severity overrides are deferred, the core needs sensible defaults
   baked into code. Proposal:
   - `error`: format, bounds, grid, typography, title
   - `warning`: margin, gutter, overlap, page-size, density

---

## Phase 2: Layout template

After guidelines settle. A layout is already data (`guidelines/layouts/*.yaml`).
Questions to resolve:
- Should layouts live in the guidelines folder or a separate `layouts/` root?
- Should a layout declare which guideline constraints it was designed for
  (grid, margin, gutter) so `apply` can validate compatibility?
- Can a client define a layout inline in the guidelines file for simple cases?

## Phase 3: Page spec template

After layouts settle. The spec is the per-page input. Questions:
- Is the current spec shape (`page`, `layout`, `visuals[]`) right from a
  client's perspective?
- Should `region:` overrides be in core or an extension?
- How does a client discover what they can write? (`bp describe` exists.)

---

## Migration from main

Reusable code from main branch (keep as-is or adapt):
- `pbir/` — the entire format layer (reader, writer, schemas, formatting)
- `model.py` — Report/Page/Visual dataclasses
- `spec.py` — page spec parsing (role names may change)
- `layouts.py` — layout loading and placement
- `slots.py` + `blueprint/visuals/*.yaml` — slot contracts
- `pbir/render.py`, `pbir/semantic.py`, `pbir/ids.py` — generation path
- `validate.py` — rule functions (signatures stay, rule ids may rename)
- `policies.py` — density policies
- `manifest.py` — manifest generation

Rewrite:
- `guidelines.py` — new schema, new dataclasses, new validation
- `defaults.yaml` — new shape
- `example.yaml` — new shape
- `commands/*.py` — adapt to new guideline field paths
- All tests that touch guidelines

---

## Status

- [x] Read the codebase and map current vs. proposed
- [ ] Finalise guidelines core keys (this document)
- [ ] Write `template/guidelines.template.yaml` (the reference file)
- [ ] Write `template/guidelines.core-spec.md` (the key-by-key spec)
- [ ] Phase 2: layout template
- [ ] Phase 3: page spec template
- [ ] Begin code refactor
