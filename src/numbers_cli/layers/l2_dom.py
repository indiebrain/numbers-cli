"""L2: the structured editing surface.

Every function takes an open document and a path (or two), resolves the path
through :mod:`numbers_cli.paths`, and reads or mutates the addressed element.
Formula writes are literal here; routing an edit through recalculation is the
router's job, not this layer's.
"""

from __future__ import annotations

from typing import Any

from numbers_parser import xl_col_to_name, xl_rowcol_to_cell

from ..engine import parser_engine as pe
from ..errors import PathError, UnsupportedOperation, UsageError
from ..paths import Target, resolve


def get(document: Any, path: str) -> dict[str, Any]:
    """Read whatever a path points at: a cell, range, row, column, or table."""
    target = resolve(document, path)
    if target.leaf_kind == "cell":
        return {"path": path, "a1": target.a1, **pe.cell_to_json(target.table.cell(target.row, target.col))}
    if target.leaf_kind == "range":
        cells = []
        for r in range(target.row, target.row_end + 1):
            for c in range(target.col, target.col_end + 1):
                cell = target.table.cell(r, c)
                cells.append({"a1": xl_rowcol_to_cell(r, c), **pe.cell_to_json(cell)})
        return {"path": path, "range": target.a1, "cells": cells}
    if target.leaf_kind == "row":
        values = list(target.table.rows(values_only=True)[target.row])
        return {"path": path, "row": target.row + 1, "values": _clean(values)}
    if target.leaf_kind == "col":
        values = [row[target.col] for row in target.table.rows(values_only=True)]
        return {"path": path, "col": xl_col_to_name(target.col), "values": _clean(values)}
    if target.table is not None:
        return {
            "path": path,
            "table": target.table.name,
            "rows": target.table.num_rows,
            "cols": target.table.num_cols,
        }
    if target.sheet is not None:
        return {"path": path, "sheet": target.sheet.name, "tables": [t.name for t in target.sheet.tables]}
    raise PathError("Path resolves to nothing addressable", hint="Point at a sheet, table, or cell")


def set_value(document: Any, path: str, raw: Any) -> dict[str, Any]:
    """Write a literal value into the cell (or every cell of a range) at ``path``."""
    target = resolve(document, path)
    cells = _leaf_cells(target, for_write=True)
    for row, col in cells:
        pe.write_value(target.table, row, col, raw)
    return {"path": path, "written": [xl_rowcol_to_cell(r, c) for r, c in cells], "value": raw}


def add(document: Any, path: str, kind: str, name: str | None = None, count: int = 1) -> dict[str, Any]:
    """Add a sheet, table, row, or column relative to ``path``."""
    kind = kind.lower()
    if kind == "sheet":
        document.add_sheet(name)
        return {"added": "sheet", "name": document.sheets[len(document.sheets) - 1].name}
    target = resolve(document, path)
    if kind == "table":
        if target.sheet is None:
            raise UsageError("Adding a table needs a sheet path", hint="For example /sheet[1]")
        table = target.sheet.add_table(name)
        return {"added": "table", "name": table.name, "sheet": target.sheet.name}
    if target.table is None:
        raise UsageError(f"Adding a {kind} needs a table path", hint="For example /sheet[1]/table[1]")
    if kind == "row":
        start = target.row if target.leaf_kind == "row" else None
        target.table.add_row(num_rows=count, start_row=start)
        return {"added": "row", "count": count, "table": target.table.name}
    if kind in ("col", "column"):
        start = target.col if target.leaf_kind == "col" else None
        target.table.add_column(num_cols=count, start_col=start)
        return {"added": "column", "count": count, "table": target.table.name}
    raise UsageError(f"Cannot add {kind!r}", hint="kind must be sheet, table, row, or col")


def remove(document: Any, path: str, kind: str | None = None, count: int = 1) -> dict[str, Any]:
    """Remove the sheet, table, row, or column addressed by ``path``."""
    target = resolve(document, path)
    kind = (kind or _infer_kind(target)).lower()
    if kind in ("sheet", "table"):
        # numbers-parser saves from its own model, not the ItemsList wrapper, so
        # dropping a sheet or table from that list does not persist. Rather than
        # report a success that silently does nothing, refuse and point at the
        # workarounds that do work.
        raise UnsupportedOperation(
            f"numbers-parser cannot delete a {kind}",
            hint=(
                "Rebuild the document without it (`nmbr dump` then edit and `nmbr batch` "
                "into a fresh file), or delete it in the Numbers application"
            ),
        )
    if kind == "row":
        _require(target.leaf_kind == "row" or None, "row", path)
        target.table.delete_row(num_rows=count, start_row=target.row)
        return {"removed": "row", "at": target.row + 1, "count": count}
    if kind in ("col", "column"):
        _require(target.leaf_kind == "col" or None, "col", path)
        target.table.delete_column(num_cols=count, start_col=target.col)
        return {"removed": "column", "at": xl_col_to_name(target.col), "count": count}
    raise UsageError(f"Cannot remove {kind!r}", hint="kind must be sheet, table, row, or col")


def query(document: Any, contains: str, path: str | None = None, ignore_case: bool = True) -> dict[str, Any]:
    """Find cells whose display text contains a substring, returning their paths.

    A pragmatic stand in for OfficeCli's CSS style selectors: it answers "where is
    this value?" which is what an agent most often needs before an edit.
    """
    needle = contains.lower() if ignore_case else contains
    matches = []
    for si, sheet in enumerate(document.sheets, start=1):
        for ti, table in enumerate(sheet.tables, start=1):
            if path:
                target = resolve(document, path)
                if target.sheet and target.sheet.name != sheet.name:
                    continue
                if target.table and target.table.name != table.name:
                    continue
            for r, row in enumerate(table.rows(values_only=True)):
                for c, value in enumerate(row):
                    if value is None:
                        continue
                    text = str(value)
                    hay = text.lower() if ignore_case else text
                    if needle in hay:
                        matches.append(
                            {
                                "path": f"/sheet[{si}]/table[{ti}]/cell[{xl_rowcol_to_cell(r, c)}]",
                                "value": text,
                            }
                        )
    return {"query": contains, "count": len(matches), "matches": matches}


# --- helpers -------------------------------------------------------------


def _clean(values: list[Any]) -> list[Any]:
    out = []
    for v in values:
        if hasattr(v, "isoformat"):
            out.append(v.isoformat())
        else:
            out.append(v)
    return out


def _leaf_cells(target: Target, for_write: bool) -> list[tuple[int, int]]:
    if target.leaf_kind == "cell":
        return [(target.row, target.col)]
    if target.leaf_kind == "range":
        return [
            (r, c)
            for r in range(target.row, target.row_end + 1)
            for c in range(target.col, target.col_end + 1)
        ]
    raise UsageError(
        "This operation needs a cell or range path",
        hint="For example /sheet[1]/table[1]/cell[A1] or .../range[A1:C3]",
    )


def _infer_kind(target: Target) -> str:
    if target.leaf_kind in ("row", "col"):
        return target.leaf_kind
    if target.table is not None and target.sheet is not None and target.leaf_kind is None:
        # A bare table path removes the table; a bare sheet path removes the sheet.
        return "table"
    if target.sheet is not None:
        return "sheet"
    raise UsageError("Cannot tell what to remove", hint="Pass --kind sheet|table|row|col")


def _require(value: Any, kind: str, path: str) -> None:
    if not value:
        raise PathError(f"Path does not address a {kind}: {path}", hint=f"Point at a {kind}")
