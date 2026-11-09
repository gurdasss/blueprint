# samples/

Real PBIP reports used to study the format. **Everything here except this file is gitignored**,
so nothing from a real report gets committed. Committed test data lives in `fixtures/`,
built from scratch.

Tests that need a sample look it up by folder name and skip when it's missing:

| Folder | Source |
|---|---|
| `retail-analysis/` | Microsoft's "Retail Analysis Sample" PBIX, saved as PBIP from Power BI Desktop |
| `procurement/` | Microsoft's "Procurement Analysis Sample", saved as PBIP |
| `sales-marketing/` | Microsoft's "Sales and Marketing Sample" as PBIP (its files are named `Supplier-Quality-Analysis-Sample-PBIX.*`, but it's the Sales and Marketing report) |
| `supplier-quality/` | Microsoft's "Supplier Quality Analysis Sample" as PBIP |

Copy a sample in without its `.pbi/cache.abf` (data). Tests that take the `real_report` fixture
(`tests/conftest.py`) run once per sample folder here: byte-exact round-trips, schema validity,
`fmt` idempotence, `check` after `fmt`, the TMDL reader against the declared members, and a spec of
the report's own fields applied, checked and re-applied (`tests/test_real_reports.py`). Tests that
assert facts about one particular report take `retail_report` and skip without it.
