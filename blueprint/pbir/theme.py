"""Generate a custom theme from guidelines, and register it in report.json.

Shapes come from what Desktop wrote (schema.md "Colours, fonts and theme" and "Typography"):

- probe 03 phase 3: a customised theme is a file in ``StaticResources/RegisteredResources/``
  holding **only overrides** on top of the base theme. ``report.json`` points to it with
  ``themeCollection.customTheme = {"name": <file name>, "reportVersionAtImport": …, "type":
  "RegisteredResources"}`` and lists it in the ``RegisteredResources`` package as ``{"name",
  "path", "type": "CustomTheme"}``. Desktop's dialog "General" is ``textClasses.label`` and
  "Title" is ``textClasses.title``.
- probe 02/03: theme files are standard Power BI theme JSON (``dataColors``, ``foreground``,
  ``background``, ``textClasses.{callout,title,header,label}.{fontFace,fontSize,color}``) in
  Desktop's JSON format; base themes use plain face names (``"Segoe UI Semibold"``).

- probe 06: Desktop accepted a Blueprint-written theme file as written (name, colours and title
  face applied), but titles came out at 15pt, not 18: the base theme's
  ``visualStyles["*"]["*"].title.fontSize`` outranks ``textClasses``. So sizes are also written
  there. Probe 06 phase 2 confirmed it: titles at 18pt, still shown on charts and the card,
  still hidden on the textbox. Desktop's save then left every file byte-identical (it rewrote
  the theme file to the same bytes).
- probe 15: ``textClasses.callout`` reaches the new card's value, and a
  ``visualStyles.cardVisual["*"].label`` entry sets its Category label, merged key by key with the
  base theme's entry.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from blueprint.guidelines import ROLE_KEY, Guidelines

FILE_NAME = "blueprint-theme.json"
PACKAGE = "RegisteredResources"
REL_PATH = Path("StaticResources") / PACKAGE / FILE_NAME
# Theme text classes seen in Desktop's base theme (probe 02); all get palette.text as colour.
TEXT_CLASSES = ("callout", "title", "header", "label")
# Guideline typography role -> theme text class (probe 03; subtitle/textbox have none).
ROLE_TO_CLASS = {"title": "title", "callout": "callout"}
# Guideline role -> visualStyles["*"]["*"] card. Probe 06: the base theme sets title fontSize 15
# there, which outranks textClasses.title, so a guideline size must also be written here. Only
# fontSize is set at this level: it's the only key observed there (base theme, probe 06).
ROLE_TO_VISUAL_CARD = {"title": "title", "subtitle": "subTitle"}
# typography.card_label -> visualStyles.cardVisual["*"].label (probe 15): Desktop showed the new
# card's Category label in the entry's font and size, merging it key by key with the base theme's
# entry (position, colour, the card's outline kept). The font is written as the CSS stack Desktop
# accepted there.
CARD_LABEL_STACK = "'{}', helvetica, arial, sans-serif"


class ThemeError(Exception):
    pass


def build(rules: Guidelines) -> tuple[dict[str, Any], list[str]]:
    """(theme document, notes about guideline settings a theme can't express)."""
    pal, notes = rules.palette, []
    theme: dict[str, Any] = {"name": rules.name or "Blueprint"}
    if pal.categorical:
        theme["dataColors"] = list(pal.categorical)
    if pal.text:
        theme["foreground"] = pal.text
    if pal.background:
        theme["background"] = pal.background
    theme.update(pal.sentiment)  # good / neutral / bad: the theme's own key names (probe 42)
    theme.update(pal.divergent)  # minimum / center / maximum: likewise (probe 44)

    classes: dict[str, dict[str, Any]] = {}
    visual_cards: dict[str, dict[str, Any]] = {}
    card_label: dict[str, Any] | None = None
    for role, rule in rules.typography.items():
        if role == "header":
            continue  # written onto Blueprint's header textboxes by bp apply, not via the theme
        if role == "card_label":
            card_label = _card_label(rule, notes)
            continue
        card = ROLE_TO_VISUAL_CARD.get(role)
        if card is not None and rule.sizes:
            size = rule.sizes[0]
            visual_cards[card] = {"fontSize": int(size) if size.is_integer() else size}
        cls = ROLE_TO_CLASS.get(role)
        if cls is None:
            if card is None or rule.fonts:
                what = "font" if card is not None else "font or size"
                notes.append(f"{ROLE_KEY[role]}: the theme can't set its {what} (unverified); "
                             "visuals are still checked")
            continue
        entry: dict[str, Any] = {}
        if rule.fonts:
            entry["fontFace"] = rule.fonts[0]
            if len(rule.fonts) > 1:
                notes.append(f"{ROLE_KEY[role]}: theme uses the first allowed font, {rule.fonts[0]!r}")
        if rule.sizes:
            entry["fontSize"] = int(rule.sizes[0]) if rule.sizes[0].is_integer() else rule.sizes[0]
            if len(rule.sizes) > 1:
                notes.append(f"{ROLE_KEY[role]}: theme uses the first allowed size, {rule.sizes[0]:g}pt")
        if entry:
            classes[cls] = entry
    if pal.text:
        for cls in TEXT_CLASSES:
            classes.setdefault(cls, {})["color"] = pal.text
    if classes:
        theme["textClasses"] = {k: classes[k] for k in TEXT_CLASSES if k in classes}
    styles: dict[str, Any] = {}
    if visual_cards:
        styles["*"] = {"*": {card: [visual_cards[card]] for card in ("title", "subTitle") if card in visual_cards}}
    if card_label is not None:
        styles["cardVisual"] = {"*": {"label": [card_label]}}  # after "*", as in Desktop's base theme
    if styles:
        theme["visualStyles"] = styles

    if len(theme) == 1:
        raise ThemeError("guidelines set no palette or theme typography; nothing to put in a theme")
    return theme, notes


def _card_label(rule, notes: list[str]) -> dict[str, Any] | None:
    """The cardVisual label entry for typography.card_label (probe 15), or None if it sets nothing."""
    entry: dict[str, Any] = {"$id": "default"}
    if rule.sizes:
        size = rule.sizes[0]
        entry["fontSize"] = int(size) if size.is_integer() else size
        if len(rule.sizes) > 1:
            notes.append(f"{ROLE_KEY['card_label']}: theme uses the first allowed size, {size:g}pt")
    if rule.fonts:
        font = rule.fonts[0]
        if "'" in font or "," in font:
            notes.append(f"{ROLE_KEY['card_label']}: font {font!r} can't be written as a font stack; "
                         "visuals are still checked")
        else:
            entry["fontFamily"] = CARD_LABEL_STACK.format(font)
            if len(rule.fonts) > 1:
                notes.append(f"{ROLE_KEY['card_label']}: theme uses the first allowed font, {font!r}")
    return entry if len(entry) > 1 else None


def with_theme(report_doc: dict, *, replace: bool) -> dict:
    """``report.json`` with the Blueprint theme as its custom theme, registered as a resource."""
    collection = dict(report_doc.get("themeCollection") or {})
    current = collection.get("customTheme")
    if isinstance(current, dict) and current.get("name") != FILE_NAME and not replace:
        raise ThemeError(
            f"the report already uses custom theme {current.get('name')!r}; pass --replace-theme to "
            "switch it to the guidelines theme (its file is kept, only the reference changes)")
    entry: dict[str, Any] = {"name": FILE_NAME}
    # Desktop gave both layers the same reportVersionAtImport (probe 02 phase 2, probe 03), and
    # the schema requires it on customTheme. A report with no base theme (Microsoft's Retail
    # sample) has it only on the custom theme being replaced.
    for layer in (collection.get("baseTheme"), current):
        if isinstance(layer, dict) and isinstance(layer.get("reportVersionAtImport"), dict):
            entry["reportVersionAtImport"] = dict(layer["reportVersionAtImport"])
            break
    entry["type"] = PACKAGE
    collection["customTheme"] = entry

    packages = [dict(p) if isinstance(p, dict) else p for p in report_doc.get("resourcePackages") or []]
    pkg = next((p for p in packages if isinstance(p, dict) and p.get("name") == PACKAGE), None)
    if pkg is None:
        pkg = {"name": PACKAGE, "type": PACKAGE, "items": []}
        packages.insert(0, pkg)
    items = [i for i in pkg.get("items") or [] if not (isinstance(i, dict) and i.get("name") == FILE_NAME)]
    items.append({"name": FILE_NAME, "path": FILE_NAME, "type": "CustomTheme"})
    # Desktop listed the new theme before the existing image item (probe 03): sorted by name.
    pkg["items"] = sorted(items, key=lambda i: str(i.get("name", "")).casefold() if isinstance(i, dict) else "")
    out = {**report_doc, "themeCollection": collection}
    if "resourcePackages" in out:
        out["resourcePackages"] = packages
        return out
    # Desktop's key order is themeCollection, objects, resourcePackages, settings (probe 04).
    ordered: dict[str, Any] = {}
    for key, value in out.items():
        if key == "settings":
            ordered["resourcePackages"] = packages
        ordered[key] = value
    ordered.setdefault("resourcePackages", packages)
    return ordered
