from pathlib import Path

import pytest

from blueprint.pbir import semantic

ROOT = Path(__file__).resolve().parent.parent


def test_fixture_model():
    m = semantic.load(ROOT / "fixtures/02-card-and-chart/Fixture.SemanticModel")
    assert m.tables == {"Sales": {"Country", "Region", "Amount"}}
    assert m.measure_table("Total Amount") == "Sales"


def test_blank_fixture_model_is_empty_not_an_error():
    m = semantic.load(ROOT / "fixtures/01-blank-report/Fixture.SemanticModel")
    assert (m.tables, m.measures) == ({}, {})


def test_parse_table_names_and_members():
    text = ("table 'Sales Data'\n\tlineageTag: x\n\n"
            "\tmeasure 'Gross %' = DIVIDE(1, 2)\n\t\tformatString: 0\n"
            "\tmeasure TotalSales = [A]+[B]\n"
            "\tcolumn 'Order Date'\n\t\tdataType: dateTime\n"
            "\tcolumn City = RELATED(x[y])\n"
            "\tcolumn 'Bob''s'\n"
            "\t\tcolumn NotAMember\n")
    assert semantic.parse_table(text) == ("Sales Data", {"Order Date", "City", "Bob's"}, {"Gross %", "TotalSales"})


def test_errors(tmp_path: Path):
    m = semantic.SemanticModel(tables={"A": {"x"}, "B": set()}, measures={"M": ["A", "B"]})
    with pytest.raises(semantic.ModelError, match="several tables"):
        m.measure_table("M")
    with pytest.raises(semantic.ModelError, match="no measure"):
        m.measure_table("Z")
    with pytest.raises(semantic.ModelError, match="has no column"):
        m.check_column("A", "y")
    with pytest.raises(semantic.ModelError, match="expected 'table <name>'"):
        semantic.parse_table("model Model\n")
    with pytest.raises(semantic.ModelError, match="byConnection"):
        semantic.model_dir_for(tmp_path, {"datasetReference": {"byConnection": {}}})
    with pytest.raises(semantic.ModelError, match="not found"):
        semantic.model_dir_for(tmp_path, {"datasetReference": {"byPath": {"path": "../Nope.SemanticModel"}}})


# probe 16: the hierarchy Desktop wrote into Sales.tmdl
HIERARCHY_TMDL = (
    "table Sales\r\n\tcolumn Country\r\n\t\tdataType: string\r\n\r\n\tcolumn Region\r\n\r\n"
    "\thierarchy Geography\r\n\t\tlineageTag: 1c532aa5-8b4d-4377-a0d9-2f88cbfd471d\r\n\r\n"
    "\t\tlevel Country\r\n\t\t\tlineageTag: 96a8fc60-b3a4-4c8d-ba60-fb8924982fbf\r\n\t\t\tcolumn: Country\r\n\r\n"
    "\t\tlevel Region\r\n\t\t\tlineageTag: 10795807-315b-45b3-ab90-5d16ec8ee6e2\r\n\t\t\tcolumn: Region\r\n\r\n"
    "\tpartition Sales = m\r\n\t\tmode: import\r\n"
)


def test_hierarchies_and_levels_are_parsed():
    assert semantic.parse_hierarchies(HIERARCHY_TMDL) == {"Geography": ("Country", "Region")}
    assert semantic.parse_table(HIERARCHY_TMDL)[1] == {"Country", "Region"}  # levels aren't columns
    quoted = "table T\n\thierarchy 'Sales Geo'\n\t\tlevel 'Sub Region'\n\tmeasure M = 1\n\t\tlevel X\n"
    assert semantic.parse_hierarchies(quoted) == {"Sales Geo": ("Sub Region",)}  # X isn't a level of it


def test_check_hierarchy_level(tmp_path: Path):
    m = semantic.SemanticModel(tables={"Sales": {"Country"}}, hierarchies={("Sales", "Geography"): ("Country", "Region")})
    m.check_hierarchy_level("Sales", "Geography", "Region")
    for args, match in ((("Nope", "Geography", "Region"), "no table"), (("Sales", "Geo", "Region"), "no hierarchy"),
                        (("Sales", "Geography", "City"), "no level 'City'")):
        with pytest.raises(semantic.ModelError, match=match):
            m.check_hierarchy_level(*args)


# Shaped like Microsoft's sample models: a hidden auto-date table, and hidden ID columns and a
# hidden measure (an `isHidden` line under the member, two tabs in; deeper lines aren't the flag).
HIDDEN_TMDL = (
    "table Vendor\n\tlineageTag: 1\n\n"
    "\tmeasure 'Vendor Count' = COUNTROWS(Vendor)\n\t\tisHidden\n\n"
    "\tmeasure Spend = SUM(Vendor[Amount])\n\t\tformatString: 0\n\n"
    "\tcolumn VendorID\n\t\tdataType: double\n\t\tisHidden\n\t\tsummarizeBy: none\n\n"
    "\tcolumn Vendor\n\t\tdataType: string\n\n"
    "\tcolumn Notes = \"x\"\n\t\tannotation Y =\n\t\t\tisHidden\n\n"
    "\tpartition Vendor = m\n\t\tmode: import\n"
)


def test_parse_hidden_members_and_tables():
    assert semantic.parse_hidden(HIDDEN_TMDL) == (False, {"Vendor Count", "VendorID"})
    auto = "table LocalDateTable_1\n\tisHidden\n\tshowAsVariationsOnly\n\n\tcolumn Date\n\t\tdataType: dateTime\n"
    assert semantic.parse_hidden(auto) == (True, set())
    assert semantic.parse_hidden(auto.replace("\n", "\r\n")) == (True, set())


def test_load_records_hidden(tmp_path):
    tables = tmp_path / "M" / "definition" / "tables"
    tables.mkdir(parents=True)
    (tables / "Vendor.tmdl").write_text(HIDDEN_TMDL)
    (tables / "LocalDateTable_1.tmdl").write_text("table LocalDateTable_1\n\tisHidden\n\n\tcolumn Date\n")
    m = semantic.load(tmp_path / "M")
    assert m.hidden_tables == {"LocalDateTable_1"}
    assert m.hidden == {("Vendor", "Vendor Count"), ("Vendor", "VendorID")}
    assert m.measure_table("Vendor Count") == "Vendor"  # hidden fields still bind, as in Desktop


def test_describe_lists_a_hidden_tables_visible_measures(tmp_path):
    from blueprint.commands.describe import _model
    from tests.builders import make_report
    rd = make_report(tmp_path / "r", {"p": []})
    tables = tmp_path / "r" / "M" / "definition" / "tables"
    tables.mkdir(parents=True)
    # Procurement-sample shape: the hidden table holds the measures the report uses.
    (tables / "Facts.tmdl").write_text("table Facts\n\tisHidden\n\n\tmeasure Total = 1\n\n"
                                       "\tmeasure Helper = 2\n\t\tisHidden\n\n\tcolumn Amount\n")
    (tables / "LocalDateTable_1.tmdl").write_text("table LocalDateTable_1\n\tisHidden\n\n\tcolumn Date\n")
    import json
    pbir = rd / "definition.pbir"
    pbir.write_text(json.dumps({"version": "4.0", "datasetReference": {"byPath": {"path": "../M"}}}))
    from blueprint.pbir.reader import read_report
    m = _model(read_report(rd))
    assert m["tables"] == {"Facts": {"columns": [], "measures": ["[Total]"], "hierarchies": {},
                                     "hidden": ["Facts[Amount]", "[Helper]"]}}
    assert m["hidden_tables"] == ["LocalDateTable_1"]


@pytest.mark.parametrize(("call", "hint"), [
    (lambda m: m.measure_table("total amount"), "(did you mean [Total Amount]?)"),  # Power BI ignores case
    (lambda m: m.measure_table("Totl Amount"), "(did you mean [Total Amount]?)"),
    (lambda m: m.check_column("sales", "Country"), "(did you mean 'Sales'?)"),
    (lambda m: m.check_column("Sales", "country"), "(did you mean Sales[Country]?)"),
    (lambda m: m.check_column("Sales", "Contry"), "(did you mean Sales[Country]?)"),
    (lambda m: m.check_column("Sales", "Total Amount"), "('Total Amount' is a measure: write it as [Total Amount])"),
    (lambda m: m.check_hierarchy_level("Sales", "Geografy", "Country"), "(did you mean Sales[Geography]?)"),
])
def test_unknown_names_suggest_the_close_ones(call, hint):
    """Agents write field names from memory; a miss names the likely field so the next try works."""
    model = semantic.SemanticModel(tables={"Sales": {"Country", "Region", "Amount"}},
                                   measures={"Total Amount": ["Sales"]},
                                   hierarchies={("Sales", "Geography"): ("Country", "Region")})
    with pytest.raises(semantic.ModelError) as exc:
        call(model)
    assert str(exc.value).endswith(hint)


def test_no_hint_when_nothing_is_close():
    model = semantic.SemanticModel(tables={"Sales": {"Country"}}, measures={"Total Amount": ["Sales"]})
    with pytest.raises(semantic.ModelError, match=r"^no measure \[Xyz\] in the semantic model$"):
        model.measure_table("Xyz")
