# Asking Power BI practitioners what to build next

Blueprint's rule is to survey before proposing a feature. There are two kinds
of survey, and this file is the second one:

1. **Counting what real reports contain** — `queryState` roles and `objects`
   keys per visual type, counts only, never field names or data. That is how
   the features in probe 32 were ranked, and it is good evidence about shapes.
2. **Asking the people who build them** — this file. Counting PBIR tells us
   what ended up in a file. It cannot tell us what somebody fixed by hand
   forty times, gave up on, or does outside Desktop entirely.

The questions below are deliberately about **their work**, not about
Blueprint. Nothing here asks "would you use X", because hypothetical yes is
free and worth nothing.

---

## How to ask

- **Ask before you demo.** Once someone has seen the tool, their answers are
  about the tool. Five minutes cold is worth an hour afterwards.
- **Prefer counts and last-time-you questions** over opinions. "How many
  slicers on the page you shipped last week" beats "do you like slicers".
- **Record what they said, not what you hoped.** Verbatim for the open ones.
- **Don't collect field names, measure names or data**, the same rule the
  report survey follows. Shape and counts only.
- **Q1 is a gatekeeper.** If the answer is .pbix, the rest is interesting but
  not actionable: Blueprint reads PBIP projects with PBIR and a TMDL model,
  and refuses the legacy format. Ask it first and know which conversation
  you are in.

---

## Part A — the two-minute set

Five questions, one-line answers. This is the version to put in a chat
message or ask over a desk.

**A1. What do you hand over at the end — a `.pbix` file, or a PBIP project
folder in source control?** If PBIP: is the model TMDL (a folder of `.tmdl`
files) or a single `model.bim`?

**A2. When you start a new report page, where does the layout come from?**
Copy an existing page / a template `.pbix` someone maintains / from scratch /
a design handed to you in Figma or a slide.

**A3. After a report is "done", what do you still fix by hand most often?**
One answer, the thing you are sick of.

**A4. The last report you shipped: roughly how many pages, and how many
visuals on the busiest page?**

**A5. Is there a written standard you're meant to follow — colours, fonts,
spacing, page size?** If yes: is it checked anywhere, or by eye in review?

---

## Part B — if they have ten minutes

**B1. Which of these took you more than half an hour in the last month?**
(tick any)
- nudging visuals into alignment or matching their sizes
- matching colours or fonts to a standard
- rebuilding a page that already exists in another report
- repointing visuals after a field or measure was renamed
- checking a report against a standard before review

**B2. On a typical page, which of these do you set by hand on nearly every
visual?** (tick any)
- background, border or corner radius
- data labels on/off
- legend position, or hiding the legend
- axis titles
- conditional formatting (colour by value, data bars)
- totals or subtotals on a table or matrix
- sort order
- tooltips

**B3. Where do slicers go on your pages, and how many?** A row across the
top, a panel down one side, scattered, or in a popout?

**B4. How often do you use tooltip pages, drillthrough pages, or
bookmarks and buttons?** Every report / sometimes / never.

**B5. If a tool could guarantee only one thing about a page — that it
matches the standard, or that it was quicker to build — which do you take?**

**B6. What would make you refuse to let a tool edit your report files?**
Ask this one even if the answer seems obvious. It is the adoption question.

---

## Part C — only for the PBIP/source-control people

**C1. Do you already edit report JSON by hand, or with scripts?** What for?

**C2. Has a Desktop save ever undone something you changed outside it?**

---

## What each answer would change

For your own use, not for the people answering. It is also a check on the
questions: one that decides nothing shouldn't be asked.

| Answer | What it decides |
|---|---|
| A1 .pbix only | Blueprint can't touch their work today. The finding is the audience, not a feature. |
| A1 `model.bim` | No TMDL, so bindings can't resolve. Same conclusion as .pbix. |
| A2 "copy an existing page" | The pitch is consistency, not speed; named layouts compete with copy-paste, which is already fast. |
| A2 "from scratch" or "a design handed over" | Named layouts are the product. Prioritise layout breadth. |
| A3 alignment, spacing, page size | Already built (`bp fmt`, `bp check`). Say so and move on. |
| A3 colours or fonts | Already built (`bp check`, `bp theme`). |
| A3 anything else | A gap. Write down the exact words. |
| A4 page and visual counts | Whether the six shipped layouts cover real pages, and whether `page.max_visuals` defaults are sane. |
| A5 "no written standard" | `bp check` has no input. Guidelines would have to be *drafted* by the tool, which is a different product. |
| B1 counts | Ranks the four things Blueprint claims to be for. A low count on all four is the most useful bad news available. |
| B2 "background, border, corner radius" | The biggest known gap: Blueprint writes no container styling at all. Several ticks here makes it the next feature, and it needs a Desktop probe first. |
| B2 axis titles / conditional formatting | Both were left out because a two-report survey found zero uses. Human answers can overturn that. |
| B2 totals / sort / labels / legend | Already built. Confirms the ranking that put them in. |
| B3 slicer placement | Slicers currently default to the `main` region, so one takes a full chart-sized slot, and no shipped layout has a slicer region. If the answer is "a row across the top" or "a side panel", that's a region role plus a layout. |
| B4 tooltip or drillthrough pages | Blueprint has one canvas size per layout and no page type. Frequent use means the page model is incomplete. |
| B4 bookmarks and buttons | No contract covers buttons, images or shapes — Blueprint tolerates them in a report but never creates them. Frequent use means spec-built pages can't be whole pages. |
| B5 "matches the standard" | Keep refusing rather than guessing, even when it's inconvenient. |
| B5 "quicker to build" | The refusals are friction, and some would need to become warnings. |
| B6 any answer | Directly about trust. Note that a re-apply already restores position, header text and spec-set options without asking — if that is what they fear, it's a real objection, not a misunderstanding. |
| C1 hand-edited JSON | They are the audience. What they script is the feature list. |
| C2 "yes" | Shared ground: it's the problem the `blueprint.bindings` fingerprint exists for. |

---

## What this deliberately doesn't ask

- **To rank Blueprint's backlog.** They don't know the codebase, and a list
  of features invites polite agreement.
- **Hypotheticals** ("would you use…", "how useful would…"). Free to say
  yes, no evidence either way.
- **For a demo reaction.** Worth having, but it is a different session and it
  contaminates everything above.
- **Anything a probe should settle.** Whether Desktop keeps a shape is not a
  matter of opinion. What people *need* is the question here; what Desktop
  *writes* is always a probe.
