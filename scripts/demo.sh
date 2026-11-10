#!/usr/bin/env bash
# Build Blueprint's end-to-end demo: every visual type and binding a Desktop probe has verified,
# on a copy of fixture 02, then check it and prove that re-running changes nothing.
#
#   bash scripts/demo.sh                          # builds /tmp/bp-demo
#   DEMO=/mnt/c/Users/<you>/bp-demo bash scripts/demo.sh   # on the Windows drive, to open in Desktop
#   SPEC_PAGES_ONLY=1 bash scripts/demo.sh        # drop fixture 02's hand-built page (CI's action job)
#
# Open <DEMO>/project/Fixture.pbip in Power BI Desktop afterwards (close it before re-running).
# Specs: examples/demo/*.yaml. The user opened this demo in Desktop on 2026-11-09 and every page
# looked as expected. tests/test_demo.py runs this script.
set -euo pipefail

BP="$(cd "$(dirname "$0")/.." && pwd)"
DEMO="${DEMO:-/tmp/bp-demo}"
R="$DEMO/project"
export BLUEPRINT_GUIDELINES="$BP/guidelines/example.yaml"
SPECS=(overview charts pies dates-tables geography geo-charts geo-line dashboard kpi-detail grid)
cd "$BP"
if [ -z "${VIRTUAL_ENV:-}" ] && [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi

step() { printf '\n==== %s\n' "$*"; }

step "1. a fresh copy of fixture 02 in $R"
rm -rf "$DEMO" && mkdir -p "$DEMO" && cp -r fixtures/02-card-and-chart "$R"

step "2. add to the model what the probes created in Desktop"
python - "$R" <<'EOF'
import sys
from pathlib import Path

sys.path.insert(0, "scripts")
from probe_apply_charts import DATE_COLUMN  # probes 13-14
from probe_apply_hierarchy import HIERARCHY  # probe 16

MEASURE = ("\tmeasure 'Target Amount' = 600\r\n\t\tformatString: 0\r\n"  # probe 10
           "\t\tlineageTag: 9ab090f9-bd7f-43c4-82be-86470a46784b\r\n\r\n")
tmdl = Path(sys.argv[1]) / "Fixture.SemanticModel/definition/tables/Sales.tmdl"
text = tmdl.read_bytes().decode()
text = text.replace("\tcolumn Country", MEASURE + "\tcolumn Country", 1)
text = text.replace("\tpartition Sales = m", DATE_COLUMN + HIERARCHY + "\tpartition Sales = m", 1)
tmdl.write_bytes(text.encode())
print("model: + [Target Amount], + Sales[Order Date], + hierarchy Geography")
EOF

step "3. report-level guidelines: the new card's fonts (probes 07, 15)"
cat > "$R/Fixture.Report/.blueprint.yaml" <<'EOF'
typography:
  callout:    { font: Segoe UI Light, size: 32 }
  card_label: { font: Arial, size: 14 }
EOF

step "4. before (errors expected)"
bp inspect --report "$R"
bp check --report "$R" || true

step "5. build: apply every spec, snap to the grid, write the theme"
for s in "${SPECS[@]}"; do bp apply "examples/demo/$s.yaml" --report "$R"; done
bp fmt --report "$R"
bp theme --report "$R"

if [ -n "${SPEC_PAGES_ONLY:-}" ]; then
  step "5b. drop the fixture's hand-built page (its page size and margin are judgement calls)"
  python - "$R/Fixture.Report" <<'PY'
import shutil
import sys
from pathlib import Path

from blueprint.pbir import jsonfmt, registry
from blueprint.pbir.reader import read_report

report = read_report(Path(sys.argv[1]))
pages_json = report.root / "definition/pages/pages.json"
doc = jsonfmt.load(pages_json)
for page in report.pages:
    if page.spec is None:
        shutil.rmtree(report.root / "definition/pages" / page.name)
        doc = registry.without_page(doc, page.name)
        print(f"removed page {page.display_name!r} ({page.name})")
if doc.get("activePageName") not in doc["pageOrder"]:
    doc["activePageName"] = doc["pageOrder"][0]
pages_json.write_bytes(jsonfmt.dump_bytes(doc))
PY
  bp manifest --report "$R"
fi

step "6. after (0 errors expected)"
bp check --report "$R"

step "7. re-running changes nothing"
for s in "${SPECS[@]}"; do
  out=$(bp apply "examples/demo/$s.yaml" --report "$R")
  [[ "$out" == "No changes."* ]] || { echo "apply $s changed something:"; echo "$out"; exit 1; }
done
for cmd in fmt theme manifest; do
  out=$(bp "$cmd" --report "$R" --dry-run)
  [[ "$out" == "No changes."* ]] || { echo "$cmd would change something:"; echo "$out"; exit 1; }
done
echo "No changes from apply, fmt, theme or manifest."

step "done: open $R/Fixture.pbip in Power BI Desktop"
