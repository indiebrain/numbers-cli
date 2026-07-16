"""The address grammar shared by every layer.

OfficeCli navigates Office files with stable paths such as ``/slide[1]/shape[2]``.
This module gives Numbers the same idea. A path is a sequence of bracketed
segments, resolved left to right against an open document::

    /sheet[1]/table[1]/cell[B2]
    /sheet['Budget']/table['Q1 plan']/range[A1:C3]
    /sheet[2]/table[1]/row[3]
    /sheet[1]/table[1]/col[B]

Selector forms inside the brackets:

* an integer, one based, matching the display order in Numbers - ``sheet[1]``;
* a quoted name, single or double quotes - ``sheet['Budget']``;
* for ``cell``: an A1 reference (``cell[B2]``) or a one based ``row,col`` pair
  (``cell[2,1]``);
* for ``range``: an A1 range (``range[A1:C3]``);
* for ``row`` / ``col``: a one based index (``row[3]``) or, for a column, a
  column letter (``col[B]``).

Resolution never mutates the document; it returns a :class:`Target` describing
what the leaf points at so each layer can read or edit it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from numbers_parser import xl_cell_to_rowcol, xl_col_to_name

from .errors import PathError, PathNotFound

_SEGMENT = re.compile(r"^(?P<kind>[a-zA-Z]+)\[(?P<sel>.+)\]$")
_A1_CELL = re.compile(r"^\$?[A-Za-z]+\$?[0-9]+$")
_A1_RANGE = re.compile(r"^\$?[A-Za-z]+\$?[0-9]+:\$?[A-Za-z]+\$?[0-9]+$")
_COL_LETTERS = re.compile(r"^[A-Za-z]+$")
_INT = re.compile(r"^[0-9]+$")
_ROWCOL = re.compile(r"^[0-9]+\s*,\s*[0-9]+$")

CONTAINER_KINDS = ("sheet", "table")
LEAF_KINDS = ("cell", "range", "row", "col", "column")


@dataclass
class Segment:
    kind: str
    selector: str  # selector text, quotes stripped
    quoted: bool = False  # whether the selector was quoted in the source path


@dataclass
class Target:
    """The resolved endpoint of a path.

    ``sheet`` and ``table`` are the ``numbers-parser`` objects. ``leaf_kind`` is
    one of ``cell``, ``range``, ``row``, ``col`` or ``None`` when the path stops
    at the table. The remaining fields are populated to match ``leaf_kind`` and
    use zero based row and column indices, the convention ``numbers-parser`` uses
    internally.
    """

    document: Any
    sheet: Any = None
    table: Any = None
    leaf_kind: str | None = None
    row: int | None = None
    col: int | None = None
    row_end: int | None = None
    col_end: int | None = None

    @property
    def a1(self) -> str | None:
        from numbers_parser import xl_rowcol_to_cell

        if self.leaf_kind == "cell":
            return xl_rowcol_to_cell(self.row, self.col)
        if self.leaf_kind == "range":
            return (
                f"{xl_rowcol_to_cell(self.row, self.col)}:"
                f"{xl_rowcol_to_cell(self.row_end, self.col_end)}"
            )
        return None


def _strip_quotes(text: str) -> tuple[str, bool]:
    """Return ``(value, was_quoted)``; strips a single or double quote pair."""
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        return text[1:-1], True
    return text, False


def parse(path: str) -> list[Segment]:
    """Parse a path string into segments, without touching a document."""
    if not path or not path.strip():
        raise PathError("Empty path", hint="Provide a path such as /sheet[1]/table[1]/cell[A1]")
    raw = path.strip()
    if not raw.startswith("/"):
        raise PathError(
            f"Path must start with '/': {path!r}",
            hint="Use an absolute path, for example /sheet[1]/table[1]",
        )
    segments: list[Segment] = []
    for part in raw.strip("/").split("/"):
        m = _SEGMENT.match(part.strip())
        if not m:
            raise PathError(
                f"Bad path segment: {part!r}",
                hint="Each segment looks like kind[selector], for example table['Q1']",
            )
        kind = m.group("kind").lower()
        sel, quoted = _strip_quotes(m.group("sel").strip())
        segments.append(Segment(kind=kind, selector=sel, quoted=quoted))
    return segments


def _lookup(container: Any, selector: str, kind: str, quoted: bool) -> Any:
    """Resolve a ``sheet`` or ``table`` selector against an ItemsList."""
    # A bare integer with no quotes is a one based index; otherwise it is a name.
    if not quoted and _INT.match(selector):
        idx = int(selector) - 1
        try:
            return container[idx]
        except (IndexError, KeyError):
            raise PathNotFound(
                f"No {kind} at index {selector}",
                hint=f"The document has {len(container)} {kind}(s); indices are one based",
            )
    try:
        return container[selector]
    except (KeyError, IndexError):
        names = ", ".join(repr(getattr(item, "name", "?")) for item in container)
        raise PathNotFound(
            f"No {kind} named {selector!r}",
            hint=f"Available {kind}s: {names}",
        )


def _resolve_leaf(kind: str, selector: str, table: Any, target: Target) -> None:
    n_rows, n_cols = table.num_rows, table.num_cols

    def check(row: int | None = None, col: int | None = None) -> None:
        if row is not None and not (0 <= row < n_rows):
            raise PathNotFound(
                f"Row {row + 1} is outside the table",
                hint=f"Table '{table.name}' has {n_rows} rows",
            )
        if col is not None and not (0 <= col < n_cols):
            raise PathNotFound(
                f"Column {xl_col_to_name(col)} is outside the table",
                hint=f"Table '{table.name}' has {n_cols} columns",
            )

    if kind == "cell":
        if _A1_CELL.match(selector):
            row, col = xl_cell_to_rowcol(selector)
        elif _ROWCOL.match(selector):
            r_txt, c_txt = (p.strip() for p in selector.split(","))
            row, col = int(r_txt) - 1, int(c_txt) - 1
        else:
            raise PathError(
                f"Bad cell selector: {selector!r}",
                hint="Use an A1 reference (cell[B2]) or one based row,col (cell[2,1])",
            )
        check(row, col)
        target.leaf_kind, target.row, target.col = "cell", row, col

    elif kind == "range":
        if not _A1_RANGE.match(selector):
            raise PathError(
                f"Bad range selector: {selector!r}",
                hint="Use an A1 range, for example range[A1:C3]",
            )
        start, end = selector.split(":")
        r1, c1 = xl_cell_to_rowcol(start)
        r2, c2 = xl_cell_to_rowcol(end)
        (r1, r2), (c1, c2) = sorted((r1, r2)), sorted((c1, c2))
        check(r1, c1)
        check(r2, c2)
        target.leaf_kind = "range"
        target.row, target.col, target.row_end, target.col_end = r1, c1, r2, c2

    elif kind == "row":
        if not _INT.match(selector):
            raise PathError(f"Bad row selector: {selector!r}", hint="Use a one based index, row[3]")
        row = int(selector) - 1
        check(row=row)
        target.leaf_kind, target.row = "row", row

    elif kind in ("col", "column"):
        if _INT.match(selector):
            col = int(selector) - 1
        elif _COL_LETTERS.match(selector):
            col = xl_cell_to_rowcol(selector + "1")[1]
        else:
            raise PathError(
                f"Bad column selector: {selector!r}",
                hint="Use a one based index (col[2]) or a letter (col[B])",
            )
        check(col=col)
        target.leaf_kind, target.col = "col", col

    else:  # pragma: no cover - guarded by the segment loop
        raise PathError(f"Unknown leaf kind: {kind!r}")


def resolve(document: Any, path: str) -> Target:
    """Resolve ``path`` against an open document into a :class:`Target`."""
    segments = parse(path)
    target = Target(document=document)
    seen_leaf = False

    for seg in segments:
        if seen_leaf:
            raise PathError(
                f"Segment {seg.kind!r} follows a leaf",
                hint="A cell, range, row or column must be the last segment",
            )
        quoted = seg.quoted

        if seg.kind == "sheet":
            if target.sheet is not None:
                raise PathError("Two sheet segments in one path")
            target.sheet = _lookup(document.sheets, seg.selector, "sheet", quoted)
        elif seg.kind == "table":
            if target.sheet is None:
                raise PathError(
                    "table[...] needs a sheet first",
                    hint="Write /sheet[1]/table[1], not /table[1]",
                )
            target.table = _lookup(target.sheet.tables, seg.selector, "table", quoted)
        elif seg.kind in LEAF_KINDS:
            if target.table is None:
                raise PathError(
                    f"{seg.kind}[...] needs a sheet and table first",
                    hint="Write /sheet[1]/table[1]/cell[A1]",
                )
            _resolve_leaf(seg.kind, seg.selector, target.table, target)
            seen_leaf = True
        else:
            raise PathError(
                f"Unknown segment kind: {seg.kind!r}",
                hint="Known kinds: sheet, table, cell, range, row, col",
            )

    return target
