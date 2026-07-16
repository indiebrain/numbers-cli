"""Serialise a document to a replayable recipe.

``dump`` walks the document and emits a JSON structure that describes how to
rebuild it: the sheets and their tables, plus a batch style operation list of the
non empty cell values. Feeding the ``ops`` back through :mod:`numbers_cli.ops.batch`
into a freshly created file reproduces the data content of the original.

Formulas are emitted as their ``=...`` text so a replay through Numbers re-enters
and re-evaluates them; note that the surrounding styling and layout are not part
of the recipe.
"""

from __future__ import annotations

from typing import Any

from numbers_parser import xl_rowcol_to_cell

from ..engine import parser_engine as pe


def dump(file: str) -> dict[str, Any]:
    doc = pe.open_document(file)
    structure: list[dict[str, Any]] = []
    ops: list[dict[str, Any]] = []

    for si, sheet in enumerate(doc.sheets, start=1):
        tables = []
        for ti, table in enumerate(sheet.tables, start=1):
            tables.append({"name": table.name, "rows": table.num_rows, "cols": table.num_cols})
            table_path = f"/sheet[{si}]/table[{ti}]"
            for r in range(table.num_rows):
                for c in range(table.num_cols):
                    cell = table.cell(r, c)
                    value = _cell_recipe_value(cell)
                    if value is None:
                        continue
                    ops.append(
                        {"op": "set", "path": f"{table_path}/cell[{xl_rowcol_to_cell(r, c)}]", "value": value}
                    )
        structure.append({"name": sheet.name, "tables": tables})

    return {"document": {"sheets": structure}, "ops": ops, "op_count": len(ops)}


def _cell_recipe_value(cell: Any) -> Any:
    """Return the value to replay, or ``None`` to skip an empty cell."""
    if getattr(cell, "is_formula", False):
        formula = getattr(cell, "formula", None)
        if formula:
            return formula if str(formula).startswith("=") else f"={formula}"
    value = getattr(cell, "value", None)
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value
