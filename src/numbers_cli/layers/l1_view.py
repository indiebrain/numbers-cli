"""L1: semantic, read only views of a document.

These renderings let an agent confirm what an edit did without parsing the file
format. Text based views (text, csv, markdown, outline) are produced here from
``numbers-parser``. The image and page views (png, pdf, html) are produced by the
Numbers application and live in :mod:`numbers_cli.render`; this module routes to
them so ``view`` is a single entry point.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from ..errors import UsageError
from ..paths import resolve

TEXT_FORMATS = ("text", "csv", "md", "markdown", "outline", "json")
APP_FORMATS = ("png", "pdf", "html")


def _table_matrix(table: Any) -> list[list[str]]:
    """Return the table as a grid of display strings."""
    matrix: list[list[str]] = []
    for row in table.rows(values_only=True):
        matrix.append(["" if v is None else str(v) for v in row])
    return matrix


def _render_csv(matrix: list[list[str]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerows(matrix)
    return buf.getvalue().rstrip("\n")


def _render_markdown(matrix: list[list[str]]) -> str:
    if not matrix:
        return ""
    header, *body = matrix
    width = len(header)
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(["---"] * width) + " |"]
    for row in body:
        padded = row + [""] * (width - len(row))
        lines.append("| " + " | ".join(padded[:width]) + " |")
    return "\n".join(lines)


def _render_text(matrix: list[list[str]]) -> str:
    """A fixed width grid, columns sized to their widest cell."""
    if not matrix:
        return "(empty table)"
    cols = max(len(r) for r in matrix)
    widths = [0] * cols
    for row in matrix:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    lines = []
    for row in matrix:
        padded = [row[i] if i < len(row) else "" for i in range(cols)]
        lines.append("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(padded)))
    return "\n".join(lines)


def _outline(document: Any) -> str:
    lines: list[str] = []
    for si, sheet in enumerate(document.sheets, start=1):
        lines.append(f"sheet[{si}] {sheet.name!r}")
        for ti, table in enumerate(sheet.tables, start=1):
            lines.append(
                f"  table[{ti}] {table.name!r}  ({table.num_rows} rows x {table.num_cols} cols)"
            )
    return "\n".join(lines) if lines else "(empty document)"


def _tables_for(document: Any, path: str | None) -> list[Any]:
    """Which tables a view covers: one when a path names it, else all of them."""
    if path:
        target = resolve(document, path)
        if target.table is not None:
            return [target.table]
        if target.sheet is not None:
            return list(target.sheet.tables)
    return [t for sheet in document.sheets for t in sheet.tables]


def render_text_view(document: Any, path: str | None, fmt: str) -> str | dict:
    """Render a text based view. Callers handle the application backed formats."""
    fmt = fmt.lower()
    if fmt == "outline":
        return _outline(document)

    tables = _tables_for(document, path)
    if not tables:
        raise UsageError("Nothing to view", hint="The document or the addressed sheet has no tables")

    if fmt == "json":
        return {
            "tables": [
                {"name": t.name, "rows": t.num_rows, "cols": t.num_cols, "cells": _table_matrix(t)}
                for t in tables
            ]
        }

    renderers = {
        "csv": _render_csv,
        "md": _render_markdown,
        "markdown": _render_markdown,
        "text": _render_text,
    }
    if fmt not in renderers:
        raise UsageError(
            f"Unknown text format: {fmt!r}",
            hint=f"Text formats: {', '.join(TEXT_FORMATS)}. Image formats: {', '.join(APP_FORMATS)}",
        )
    render = renderers[fmt]
    blocks = []
    for table in tables:
        heading = f"# {table.name}" if len(tables) > 1 else ""
        block = render(_table_matrix(table))
        blocks.append(f"{heading}\n{block}".strip() if heading else block)
    return "\n\n".join(blocks)
