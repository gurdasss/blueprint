# PyInstaller spec for the standalone `bp` executable (one file: engine + interpreter).
#
# Build from the repository root, with Blueprint installed (non-editable) beside PyInstaller:
#     pyinstaller --noconfirm --clean packaging/windows/bp.spec
# Output: dist/bp.exe on Windows (dist/bp elsewhere, used only to test this spec locally).
#
# Data files. The engine finds its data from each module's own __file__
# (slots.VISUALS_DIR, guidelines.DEFAULTS, pbir/schemas.SCHEMA_DIR). In a frozen app,
# PyInstaller sets a module's __file__ under sys._MEIPASS (PyInstaller 6.22.3,
# loader/pyimod02_importers.py: spec.origin -> __file__), so the data must sit at the same
# package-relative paths inside the bundle. The patterns below are pyproject.toml's
# [tool.setuptools.package-data], so the exe carries exactly what the wheel carries.
# jsonschema and jsonschema_specifications (Draft 7 metaschemas) are collected by their
# hooks in pyinstaller-hooks-contrib (stdhooks/hook-jsonschema*.py).
from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files(
    "blueprint",
    includes=["*.yaml", "visuals/*.yaml", "pbir/schemas/**/*.json"],
)

a = Analysis(
    ["bp_entry.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="bp",
    debug=False,
    strip=False,
    upx=False,
    console=True,
)
