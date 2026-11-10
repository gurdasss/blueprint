"""`bp check --github` and the composite action (action.yml, scripts/ci_check.sh)."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from blueprint.cli import main
from blueprint.commands.check import _escape

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "guidelines" / "example.yaml"
BP = Path(sys.executable).parent / "bp"


def _github(capsys, report: Path, *extra: str) -> tuple[int, list[str]]:
    code = main(["check", "--report", str(report), "--guidelines", str(GUIDE), "--github", *extra])
    return code, capsys.readouterr().out.splitlines()


def test_findings_are_annotated_on_their_files(card_chart_fixture, tmp_path, capsys, monkeypatch):
    shutil.copytree(card_chart_fixture.parent, tmp_path / "proj")
    monkeypatch.setenv("GITHUB_WORKSPACE", str(tmp_path))
    code, out = _github(capsys, tmp_path / "proj")
    assert code == 1  # same exit code as plain output
    commands = [ln for ln in out if ln.startswith("::")]
    grid = [ln for ln in commands if "bp check%3A grid" in ln]
    assert grid and all(ln.startswith("::error file=proj/Fixture.Report/definition/pages/") for ln in grid)
    assert all(ln.split(",")[0].endswith("/visual.json") for ln in grid)
    [size] = [ln for ln in commands if "page-size" in ln]
    assert size.startswith("::warning file=proj/") and ",title=" in size
    assert size.split(",")[0].endswith("/page.json") and size.endswith(
        "::Overview: page is 1920x1080, guidelines say 1280x720")
    theme = [ln for ln in commands if "bp check%3A palette" in ln]
    assert theme and all(ln.startswith("::error title=") for ln in theme)  # report-level: no file
    assert any(ln.startswith("::notice title=bp check::") for ln in commands)
    assert "5 error(s), 2 warning(s) across 1 page(s)" in out  # the text report follows


def test_files_outside_the_workspace_are_left_off(card_chart_fixture, tmp_path, capsys, monkeypatch):
    shutil.copytree(card_chart_fixture.parent, tmp_path / "proj")
    monkeypatch.setenv("GITHUB_WORKSPACE", str(tmp_path / "elsewhere"))
    _, out = _github(capsys, tmp_path / "proj")
    commands = [ln for ln in out if ln.startswith("::")]
    assert commands and not any("file=" in ln for ln in commands)


def test_json_and_github_are_alternatives(card_chart_fixture, capsys):
    with pytest.raises(SystemExit):
        main(["check", "--report", str(card_chart_fixture), "--json", "--github"])
    capsys.readouterr()


def test_workflow_command_escaping():
    assert _escape("50% done\r\nnext") == "50%25 done%0D%0Anext"
    assert _escape("a: b, c", prop=True) == "a%3A b%2C c"
    assert _escape("a: b, c") == "a: b, c"  # messages keep : and ,


# --- the composite action ------------------------------------------------------------------


def _ci(tmp_path: Path, reports: str, **env: str) -> tuple[int, str, Path, Path]:
    summary, output = tmp_path / "summary.md", tmp_path / "output.txt"
    full = {**os.environ, "BP": str(BP), "REPORTS": reports, "GUIDELINES": str(GUIDE),
            "GITHUB_STEP_SUMMARY": str(summary), "GITHUB_OUTPUT": str(output),
            "GITHUB_WORKSPACE": str(tmp_path), **env}
    done = subprocess.run(["bash", str(ROOT / "scripts" / "ci_check.sh")], cwd=tmp_path, env=full,
                          capture_output=True, text=True, check=False)
    return done.returncode, done.stdout, summary, output


@pytest.mark.skipif(not BP.exists(), reason="needs the bp entry point (pip install -e .)")
def test_action_script_checks_every_report_and_exits_with_the_worst(card_chart_fixture, tmp_path):
    shutil.copytree(card_chart_fixture.parent, tmp_path / "proj")
    code, out, summary, output = _ci(tmp_path, "  proj  \n\nmissing/Nope.Report\n")
    assert code == 2 and output.read_text() == "exit-code=2\n"
    assert "::group::bp check proj (exit 1)" in out
    assert "::error title=bp check::missing/Nope.Report could not be checked (exit 2)" in out
    text = summary.read_text()
    assert "### `proj`: exit 1" in text and "### `missing/Nope.Report`: exit 2" in text
    assert "::" not in text.replace("### ", "")  # annotations stay out of the summary


@pytest.mark.skipif(not BP.exists(), reason="needs the bp entry point (pip install -e .)")
def test_action_script_strict_and_empty_input(card_chart_fixture, tmp_path):
    lax = tmp_path / "lax.yaml"
    lax.write_text("check:\n  severity: {grid: warning, typography: warning}\n"
                   "palette:\n  enforce: warn\n")
    shutil.copytree(card_chart_fixture.parent, tmp_path / "proj")
    assert _ci(tmp_path, "proj", GUIDELINES=str(lax))[0] == 0
    assert _ci(tmp_path, "proj", GUIDELINES=str(lax), STRICT="true")[0] == 1
    assert _ci(tmp_path, "proj", STRICT="yes")[0] == 2
    code, out, _, _ = _ci(tmp_path, "\n  \n")
    assert code == 2 and "no reports given" in out


def test_action_metadata_matches_the_script():
    action = yaml.safe_load((ROOT / "action.yml").read_text())
    assert set(action["inputs"]) == {"reports", "guidelines", "strict", "python-version"}
    assert action["inputs"]["reports"]["required"] is True
    [check] = [s for s in action["runs"]["steps"] if s.get("id") == "check"]
    assert check["env"] == {"REPORTS": "${{ inputs.reports }}", "GUIDELINES": "${{ inputs.guidelines }}",
                            "STRICT": "${{ inputs.strict }}"}
    assert "scripts/ci_check.sh" in check["run"]
    script = (ROOT / "scripts" / "ci_check.sh").read_text()
    assert all(f"${{{name}" in script for name in check["env"])


def test_findings_beyond_githubs_cap_are_announced(tmp_path, capsys, monkeypatch):
    """GitHub shows 10 error and 10 warning annotations per step and drops the rest silently."""
    from tests.builders import make_report, visual
    # 13 visuals off the 8px grid (errors), one per row so nothing overlaps
    rd = make_report(tmp_path / "r", {"p": [visual(f"v{i:02d}", x=19, y=19 + 40 * i, w=101, h=21)
                                             for i in range(13)]})
    monkeypatch.setenv("GITHUB_WORKSPACE", str(tmp_path))
    main(["check", "--report", str(rd), "--guidelines", str(GUIDE), "--github"])
    out = capsys.readouterr().out
    errors = [ln for ln in out.splitlines() if ln.startswith("::error ")]
    assert len(errors) > 10
    [notice] = [ln for ln in out.splitlines() if "aren't annotated" in ln]
    assert f"{len(errors) - 10} more error(s)" in notice


def test_no_cap_notice_within_the_limit(card_chart_fixture, tmp_path, capsys, monkeypatch):
    shutil.copytree(card_chart_fixture.parent, tmp_path / "proj")
    monkeypatch.setenv("GITHUB_WORKSPACE", str(tmp_path))
    _github(capsys, tmp_path / "proj")
    assert "aren't annotated" not in capsys.readouterr().out


@pytest.mark.skipif(not BP.exists(), reason="needs the bp entry point (pip install -e .)")
def test_action_script_expands_globs(card_chart_fixture, tmp_path):
    for name in ("b", "a"):
        shutil.copytree(card_chart_fixture.parent, tmp_path / "reports" / name)
    code, out, summary, _ = _ci(tmp_path, "reports/*/Fixture.Report")
    assert code == 1  # the fixture fails the example guidelines
    text = summary.read_text()
    assert text.index("reports/a/Fixture.Report") < text.index("reports/b/Fixture.Report")  # sorted
    code, out, _, _ = _ci(tmp_path, "reports/*/Nope.Report")
    assert code == 2 and "'reports/*/Nope.Report' matches no report" in out
