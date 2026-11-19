"""A finding about the report's theme file says to run `bp theme`, and that advice is true.

An agent fixing `check` errors by editing specs can't fix a theme from a spec, so without the
pointer it loops. The pointer is only worth having if `bp theme` really clears what it points at.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from blueprint import guidelines
from blueprint.cli import main
from blueprint.pbir.reader import read_report
from blueprint.validate import THEME_FIX, check_report

ROOT = Path(__file__).resolve().parent.parent
# The fullest guidelines the repository ships (every palette family), plus the three typography
# roles a theme also carries, so every kind of theme finding is raised.
GUIDE = ROOT / "template" / "guidelines.template.yaml"
EXTRA = ["extensions.typography.subtitle={font: Arial, size: 11}",
         "extensions.typography.callout={font: Arial, size: 28}",
         "extensions.typography.card_label={font: Arial, size: 10}"]


def _theme_findings(report: Path):
    rules = guidelines.load(GUIDE, overrides=guidelines.overrides_from(EXTRA))
    found = check_report(read_report(report), rules).findings
    return [f for f in found if f.rule in ("palette", "typography") and f.visual is None
            and f.message.startswith("theme ")]


def test_every_theme_finding_names_bp_theme_and_bp_theme_clears_them(card_chart_fixture, tmp_path):
    report = tmp_path / "proj"
    shutil.copytree(card_chart_fixture.parent, report)
    before = _theme_findings(report)
    kinds = {f.message.split(" is ")[0].split(" text:")[0].split(" differ")[0] for f in before}
    assert len(before) >= 10 and any("sentiment" in k for k in kinds) and any("structural" in k for k in kinds)
    assert all(f.message.endswith(THEME_FIX) for f in before), [f.message for f in before]

    sets = [a for s in EXTRA for a in ("--set", s)]
    assert main(["theme", "--report", str(report), "--guidelines", str(GUIDE), *sets]) == 0
    assert _theme_findings(report) == []


def test_a_finding_on_a_visual_does_not_point_at_bp_theme(card_chart_fixture, tmp_path):
    """A colour or font set on one visual isn't the theme's: `bp theme` wouldn't fix it."""
    report = tmp_path / "proj"
    shutil.copytree(card_chart_fixture.parent, report)
    rules = guidelines.load(ROOT / "guidelines" / "example.yaml",
                            overrides=guidelines.overrides_from(["palette.categorical=['#000001']"]))
    on_visuals = [f for f in check_report(read_report(report), rules).findings if f.visual is not None]
    assert on_visuals, "the fixture's hand-built page should give at least one visual-level finding"
    assert not any(THEME_FIX in f.message for f in on_visuals)


def test_with_a_custom_theme_of_its_own_the_hint_names_replace_theme_and_that_works(card_chart_fixture,
                                                                                     tmp_path):
    """`bp theme` refuses to switch away from a custom theme that isn't Blueprint's unless told
    to, so the hint says `--replace-theme` up front, and following it clears the findings."""
    from blueprint.validate import THEME_FIX_REPLACE
    from tests.builders import add_theme
    report = tmp_path / "proj"
    shutil.copytree(card_chart_fixture.parent, report)
    add_theme(next(report.glob("*.Report")), "custom", "Corporate", {"foreground": "#010101"})
    before = _theme_findings(report)
    assert before and all(f.message.endswith(THEME_FIX_REPLACE) for f in before)
    sets = [a for s in EXTRA for a in ("--set", s)]
    assert main(["theme", "--report", str(report), "--guidelines", str(GUIDE), *sets]) == 2  # refused
    assert main(["theme", "--report", str(report), "--guidelines", str(GUIDE), *sets,
                 "--replace-theme"]) == 0
    assert _theme_findings(report) == []
