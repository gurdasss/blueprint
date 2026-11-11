"""Rebinding a Blueprint visual in place (bp apply re-run): render.with_bindings."""

from blueprint.pbir import render

B = render.Binding


def _col(name):
    return {"Column": {"Expression": {"SourceRef": {"Entity": "Sales"}}, "Property": name}}


def _meas(name):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": "Sales"}}, "Property": name}}


DOC = {
    "name": "v",
    "position": {"x": 16, "y": 232},
    "visual": {
        "visualType": "clusteredColumnChart",
        "query": {"queryState": {"Category": {"projections": [{"field": _col("Country")}]}},
                  "sortDefinition": {"sort": [{"field": _meas("Total Amount"), "direction": "Descending"}],
                                     "isDefaultSort": True}},
        "objects": {"labels": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}]},
        "visualContainerObjects": {"title": [{"properties": {"text": {"expr": {"Literal": {"Value": "'T'"}}}}}]},
        "drillFilterOtherVisuals": True,
    },
    "filterConfig": {"filters": [
        {"name": "auto-country", "field": _col("Country"), "type": "Categorical"},     # Desktop's own
        {"name": "auto-total", "field": _meas("Total Amount"), "type": "Advanced"},    # Desktop's own
        {"name": "user", "field": _col("Region"), "type": "Categorical", "howCreated": "User"},
        {"name": "cond", "field": _col("Country"), "type": "Categorical",
         "filter": {"Version": 2}},                                                    # has a condition
    ]},
    "annotations": [{"name": "blueprint.visual", "value": "column-1"}],
}


def test_query_is_replaced_and_state_about_gone_fields_cleared():
    out = render.with_bindings(DOC,
                               {"Category": [B("column", "Sales", "Region")], "Y": [B("measure", "Sales", "Target")]},
                               frozenset({"Category"}))
    q = out["visual"]["query"]
    assert list(q) == ["queryState"]  # the sort was on Total Amount, no longer bound
    assert q["queryState"]["Category"]["projections"][0]["active"] is True
    names = [f["name"] for f in out["filterConfig"]["filters"]]
    assert names == ["user", "cond"]  # Desktop's own filters on gone fields dropped, the rest kept
    for key in ("objects", "visualContainerObjects", "drillFilterOtherVisuals"):
        assert out["visual"][key] == DOC["visual"][key]  # formatting and title untouched
    assert (out["position"], out["annotations"]) == (DOC["position"], DOC["annotations"])


def test_sort_and_desktop_filters_on_still_bound_fields_are_kept():
    out = render.with_bindings(DOC,
                               {"Category": [B("column", "Sales", "Country")], "Y": [B("measure", "Sales", "Total Amount")]},
                               frozenset({"Category"}))
    assert out["visual"]["query"]["sortDefinition"] == DOC["visual"]["query"]["sortDefinition"]
    assert [f["name"] for f in out["filterConfig"]["filters"]] == ["auto-country", "auto-total", "user", "cond"]


def test_no_filters_left_drops_filter_config_and_stale_expansion():
    doc = {"visual": {"visualType": "slicer", "query": {"queryState": {}},
                      "expansionStates": [{"roles": ["Values"], "levels": [{"queryRefs": ["Sales.Country"]}]}]},
           "filterConfig": {"filters": [{"name": "a", "field": _col("Country"), "type": "Categorical"}]}}
    out = render.with_bindings(doc, {"Values": [B("column", "Sales", "Region")]}, frozenset({"Values"}))
    assert "filterConfig" not in out and "expansionStates" not in out["visual"]
    kept = render.with_bindings(doc, {"Values": [B("column", "Sales", "Country")]}, frozenset({"Values"}))
    assert kept["visual"]["expansionStates"] == doc["visual"]["expansionStates"]


def test_fingerprint_is_stable_and_order_sensitive():
    a = {"Category": [("column", "Sales", "Country", None), ("column", "Sales", "Region", None)]}
    assert render.bindings_fingerprint(a) == render.bindings_fingerprint(dict(a))
    assert render.bindings_fingerprint(a) != render.bindings_fingerprint({"Category": a["Category"][::-1]})
    assert len(render.bindings_fingerprint(a)) == 16
