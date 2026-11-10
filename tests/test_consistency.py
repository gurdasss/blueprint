"""Sweep: the things that drifted apart three times while the template was being built.

Each test here pins a claim the shipped files make against what the code actually does. They are
cheap, and they fail on the kind of change that is easy to make and hard to notice: a key renamed
in code but not in the file a client copies, a new contract directory that the wheel doesn't
ship, a message naming a key the loader refuses.
"""

import ast
import re
import tomllib
from pathlib import Path

import pytest
import yaml

from blueprint import guidelines
from blueprint.cli import build_parser
from blueprint.slots import ARCHIVE_DIR, CORE_TYPES, VISUALS_DIR, contracts

ROOT = Path(__file__).resolve().parent.parent
SHIPPED_YAML = sorted(
    p for d in ("guidelines", "template", "examples") for p in (ROOT / d).rglob("*.yaml")
)


def test_there_is_shipped_yaml_to_check():
    assert len(SHIPPED_YAML) > 5  # guard against the globs silently finding nothing


@pytest.mark.parametrize("path", SHIPPED_YAML, ids=lambda p: str(p.relative_to(ROOT)))
def test_no_shipped_file_uses_a_retired_key(path: Path):
    """A key the loader refuses must not survive in a file the repo ships: a client copying it
    gets an error, and a test fixture using it hides whatever it was meant to check."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return  # a layout or spec list, not a guidelines file
    for old, _ in guidelines.RETIRED:
        assert guidelines._get(data, old, guidelines._MISSING) is guidelines._MISSING, old


def _extensions_text(path: Path) -> str:
    """Only the part of a file that documents `extensions:` — the core has its own
    `typography:` key, so searching the whole file makes the check vacuous."""
    text = path.read_text(encoding="utf-8")
    marker = re.search(r"^#*\s*extensions:", text, re.MULTILINE)
    assert marker, f"{path} documents no extensions: block at all"
    return text[marker.start():]


@pytest.mark.parametrize("module", ["probe_annotations", "probe_card_theme"])
def test_the_guidelines_a_probe_script_writes_still_load(module: str, tmp_path: Path):
    """Both times a retired key survived, it was in scripts/: probe_card_theme's GUIDELINES and
    probe_annotations' BLUEPRINT_YAML. Re-running such a probe would fail at guidelines load."""
    src = (ROOT / "scripts" / f"{module}.py").read_text(encoding="utf-8")
    bodies = re.findall(r'^(?:GUIDELINES|BLUEPRINT_YAML) = (?:"""\\?\n(.*?)"""|"(.*?)")',
                        src, re.MULTILINE | re.DOTALL)
    found = [b[0] or b[1].encode().decode("unicode_escape") for b in bodies]
    assert found, f"{module}: no guidelines constant found (did it move?)"
    for i, body in enumerate(found):
        path = tmp_path / f"{module}-{i}.yaml"
        path.write_text(body, encoding="utf-8")
        guidelines.load(path)  # raises GuidelinesError on a retired key


@pytest.mark.parametrize("path", [Path("blueprint/defaults.yaml"),
                                  Path("template/guidelines.template.yaml")],
                         ids=str)
def test_every_extension_key_the_core_reads_is_documented(path: Path):
    """Both the built-in defaults and the template a client starts from list them: this is the
    drift that happened twice (custom_visuals, and the typography roles before it)."""
    text = _extensions_text(ROOT / path)
    for key in guidelines.EXTENSION_KEYS:
        assert f"{key}:" in text, f"{path} doesn't document extensions.{key}"
    for role in guidelines.EXTENSION_ROLES:  # the block, not just the word "typography"
        assert f"{role}:" in text, f"{path} doesn't document extensions.typography.{role}"


def test_extension_keys_lists_exactly_what_the_loader_reads():
    """EXTENSION_KEYS is hand-written, so tie it to the `ext` lookups in guidelines.py: a new
    extensions sub-key read by the code but missing from the tuple would otherwise go
    undocumented, which is the drift this file exists for."""
    tree = ast.parse((ROOT / "blueprint" / "guidelines.py").read_text(encoding="utf-8"))
    read: set[str] = set()
    for node in ast.walk(tree):
        # ext.get("key"[, default])
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get" and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "ext" and node.args
                and isinstance(node.args[0], ast.Constant)):
            read.add(node.args[0].value)
        # ext["key"]
        if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
                and node.value.id == "ext" and isinstance(node.slice, ast.Constant)):
            read.add(node.slice.value)
        # "key" in ext
        if (isinstance(node, ast.Compare) and isinstance(node.left, ast.Constant)
                and any(isinstance(op, ast.In) for op in node.ops)
                and any(isinstance(c, ast.Name) and c.id == "ext" for c in node.comparators)):
            read.add(node.left.value)
    assert read == set(guidelines.EXTENSION_KEYS), (
        f"guidelines.py reads {sorted(read)}, EXTENSION_KEYS says "
        f"{sorted(guidelines.EXTENSION_KEYS)}")


def test_the_documented_extension_keys_are_all_accepted(tmp_path: Path):
    """And the other direction: a key the docs show must load, not raise."""
    body = (
        "extensions:\n"
        "  severity: {grid: warning}\n"
        "  decorative_types: [image, shape]\n"
        "  max_resize: 0.25\n"
        "  typography:\n"
        "    subtitle: {font: Segoe UI, size: 12}\n"
        "    callout: {font: Segoe UI Light, size: 32}\n"
        "    card_label: {font: Arial, size: 14}\n"
        "  custom_visuals:\n"
        f'    search_path: ["{ARCHIVE_DIR}"]\n'
    )
    path = tmp_path / "extensions.yaml"
    path.write_text(body, encoding="utf-8")
    rules = guidelines.load(path)
    assert rules.check.severity["grid"] == "warning"
    assert rules.check.decorative_types == ("image", "shape")
    assert rules.max_resize == 0.25
    assert {"subtitle", "callout", "card_label"} <= set(rules.typography)
    assert rules.visuals == (ARCHIVE_DIR,)


def test_the_core_contract_set_matches_its_constant():
    assert sorted(contracts()) == sorted(CORE_TYPES)
    assert sorted(p.stem for p in VISUALS_DIR.glob("*.yaml")) == sorted(CORE_TYPES)


def test_every_yaml_blueprint_loads_at_runtime_is_packaged():
    """package-data globs don't recurse: `visuals/*.yaml` does not ship `visuals/archive/*.yaml`,
    so an archived contract would be missing from a pip install (the repo checkout hides it)."""
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    globs = data["tool"]["setuptools"]["package-data"]["blueprint"]
    pkg = ROOT / "blueprint"
    for path in sorted(pkg.rglob("*.yaml")):
        rel = path.relative_to(pkg)
        assert any(rel.match(g) for g in globs), f"{rel} matches no package-data glob: {globs}"


def test_no_stale_file_lingers_in_the_build_directory():
    """setuptools copies into build/lib and never removes anything, so a wheel built in a tree
    with a stale build/ ships files whose source is gone. That shipped the eight archived
    contracts as `blueprint/visuals/*.yaml` — a pip install would see 15 core types and no
    archive. Harmless in a fresh checkout (build/ is gitignored); this catches the local case."""
    lib = ROOT / "build" / "lib" / "blueprint"
    if not lib.is_dir():
        pytest.skip("no build/ directory")
    stale = [str(p.relative_to(lib)) for p in lib.rglob("*")
             if p.is_file() and not (ROOT / "blueprint" / p.relative_to(lib)).exists()]
    assert stale == [], f"run `rm -rf build` before packaging; stale: {stale}"


def test_no_message_in_the_code_names_a_retired_key():
    """`bp fmt` warned about "grid.max_resize" long after that key stopped loading. Only string
    literals count: `rules.check.severity[...]` is attribute access, not something a user reads."""
    retired = {old for old, _ in guidelines.RETIRED}
    offenders = []
    for path in sorted((ROOT / "blueprint").rglob("*.py")):
        if path.name == "guidelines.py":
            continue  # it owns the RETIRED table and names them on purpose
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for key in retired:
                    if key in node.value:
                        offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}: {key}")
    assert offenders == []


def test_every_rule_id_has_a_severity_and_the_ids_are_the_ci_contract():
    """Rule ids and exit codes are a CI contract (CLAUDE.md), so a rule may not appear without a
    severity, and a severity may not name a rule that doesn't exist."""
    assert set(guidelines.DEFAULT_SEVERITY) == set(guidelines.RULES)
    assert set(guidelines.DEFAULT_SEVERITY.values()) <= set(guidelines.SEVERITIES)


def _readme_commands() -> dict[str, set[str]]:
    """{subcommand: every --flag the README writes on a `bp <cmd>` line}."""
    out: dict[str, set[str]] = {}
    for line in (ROOT / "README.md").read_text(encoding="utf-8").splitlines():
        m = re.search(r"\bbp (apply|check|fmt|describe|manifest|inspect|theme)\b", line)
        if not m:
            continue
        out.setdefault(m.group(1), set()).update(re.findall(r"(--[a-z][a-z-]+)", line))
    return out


def _flags_of(subcommand: str) -> set[str]:
    """What that subcommand's own parser accepts, straight from cli.build_parser()."""
    sub = next(a for a in build_parser()._subparsers._group_actions if a.choices)
    return {f for f in sub.choices[subcommand]._option_string_actions if f.startswith("--")}


def test_the_extractor_reads_past_the_first_flag():
    """Guard for this file's own test: `--report` comes first on nearly every README line, so a
    lazy pattern would only ever see that one and the check below would be vacuous."""
    assert "--visuals" in _readme_commands()["apply"]


@pytest.mark.parametrize("subcommand", sorted(_readme_commands()))
def test_the_readme_quotes_flags_that_exist(subcommand: str):
    """Agents copy these command lines, and a flag renamed in cli.py has to fail here."""
    unknown = _readme_commands()[subcommand] - _flags_of(subcommand)
    assert unknown == set(), f"bp {subcommand}: README uses {sorted(unknown)}"
