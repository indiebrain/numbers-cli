import pytest

from numbers_cli import paths
from numbers_cli.engine import parser_engine as pe
from numbers_cli.errors import PathError, PathNotFound


def test_parse_segments_and_quoting():
    segs = paths.parse("/sheet['Q1']/table[2]/cell[B3]")
    assert [(s.kind, s.selector, s.quoted) for s in segs] == [
        ("sheet", "Q1", True),
        ("table", "2", False),
        ("cell", "B3", False),
    ]


def test_parse_rejects_relative_and_malformed():
    with pytest.raises(PathError):
        paths.parse("sheet[1]")
    with pytest.raises(PathError):
        paths.parse("/sheet 1/")


def test_index_versus_name(doc_path):
    doc = pe.open_document(doc_path)
    by_index = paths.resolve(doc, "/sheet[1]")
    by_name = paths.resolve(doc, "/sheet['Budget']")
    assert by_index.sheet.name == by_name.sheet.name == "Budget"


def test_cell_a1_and_rowcol_agree(doc_path):
    doc = pe.open_document(doc_path)
    a1 = paths.resolve(doc, "/sheet[1]/table[1]/cell[B2]")
    rc = paths.resolve(doc, "/sheet[1]/table[1]/cell[2,2]")
    assert (a1.row, a1.col) == (rc.row, rc.col) == (1, 1)
    assert a1.a1 == "B2"


def test_range_is_normalised(doc_path):
    doc = pe.open_document(doc_path)
    t = paths.resolve(doc, "/sheet[1]/table[1]/range[C3:A1]")
    assert (t.row, t.col, t.row_end, t.col_end) == (0, 0, 2, 2)


def test_out_of_range_and_missing_names(doc_path):
    doc = pe.open_document(doc_path)
    with pytest.raises(PathNotFound):
        paths.resolve(doc, "/sheet[9]")
    with pytest.raises(PathNotFound):
        paths.resolve(doc, "/sheet['nope']")
    with pytest.raises(PathNotFound):
        paths.resolve(doc, "/sheet[1]/table[1]/cell[Z99]")


def test_leaf_must_be_last(doc_path):
    doc = pe.open_document(doc_path)
    with pytest.raises(PathError):
        paths.resolve(doc, "/sheet[1]/cell[A1]/table[1]")
