import warnings

import pytest

from numbers_cli.engine import parser_engine as pe

warnings.simplefilter("ignore")


@pytest.fixture
def doc_path(tmp_path):
    """A saved two-sheet document with a few values for tests to read and edit."""
    path = tmp_path / "book.numbers"
    doc = pe.new_document(["Budget", "Notes"])
    table = doc.sheets[0].tables[0]
    table.write("A1", "Item")
    table.write("B1", "Cost")
    table.write("A2", "Widget")
    table.write("B2", 10)
    pe.save_document(doc, path)
    return str(path)
