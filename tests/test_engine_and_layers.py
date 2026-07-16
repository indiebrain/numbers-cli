import datetime

import pytest

from numbers_cli.engine import parser_engine as pe
from numbers_cli.layers import l1_view, l2_dom
from numbers_cli.errors import UnsupportedOperation


def test_coerce_value_types():
    assert pe.coerce_value("42") == 42
    assert pe.coerce_value("3.5") == 3.5
    assert pe.coerce_value("true") is True
    assert pe.coerce_value("no") is False
    assert pe.coerce_value("2026-07-15") == datetime.datetime(2026, 7, 15)
    assert pe.coerce_value("hello") == "hello"
    assert pe.is_formula_input("=A1+A2") is True


def test_get_cell_and_range(doc_path):
    doc = pe.open_document(doc_path)
    cell = l2_dom.get(doc, "/sheet[1]/table[1]/cell[B2]")
    assert cell["value"] == 10.0
    rng = l2_dom.get(doc, "/sheet[1]/table[1]/range[A1:B2]")
    assert rng["range"] == "A1:B2"
    assert len(rng["cells"]) == 4


def test_set_literal_persists(doc_path):
    doc = pe.open_document(doc_path)
    l2_dom.set_value(doc, "/sheet[1]/table[1]/cell[C1]", "note")
    pe.save_document(doc, doc_path)
    reopened = pe.open_document(doc_path)
    assert l2_dom.get(reopened, "/sheet[1]/table[1]/cell[C1]")["value"] == "note"


def test_add_and_delete_rows(doc_path):
    doc = pe.open_document(doc_path)
    before = doc.sheets[0].tables[0].num_rows
    l2_dom.add(doc, "/sheet[1]/table[1]", "row", count=3)
    assert doc.sheets[0].tables[0].num_rows == before + 3
    l2_dom.remove(doc, "/sheet[1]/table[1]/row[1]", kind="row")
    assert doc.sheets[0].tables[0].num_rows == before + 2


def test_remove_sheet_is_refused(doc_path):
    doc = pe.open_document(doc_path)
    with pytest.raises(UnsupportedOperation):
        l2_dom.remove(doc, "/sheet[1]", kind="sheet")


def test_query_finds_by_substring(doc_path):
    doc = pe.open_document(doc_path)
    result = l2_dom.query(doc, "widget")
    assert result["count"] == 1
    assert result["matches"][0]["path"].endswith("cell[A2]")


def test_views_render(doc_path):
    doc = pe.open_document(doc_path)
    assert "Item" in l1_view.render_text_view(doc, "/sheet[1]/table[1]", "csv")
    assert "| Item |" in l1_view.render_text_view(doc, "/sheet[1]/table[1]", "md")
    assert "Budget" in l1_view.render_text_view(doc, None, "outline")
