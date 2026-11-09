from pathlib import Path

import pytest

from blueprint.pbir import semantic

ROOT = Path(__file__).resolve().parent.parent


def test_fixture_model():
    m = semantic.load(ROOT / "fixtures/02-card-and-chart/Fixture.SemanticModel")
    assert m.tables == {"Sales": {"Country", "Region", "Amount"}}
    assert m.measure_table("Total Amount") == "Sales"


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
