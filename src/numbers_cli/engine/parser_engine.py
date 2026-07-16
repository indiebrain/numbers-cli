"""The ``numbers-parser`` back end: direct read and write of ``.numbers`` files.

This is the default engine for everything structural. It never launches an
application, so it is fast and works anywhere ``numbers-parser`` installs. What
it cannot do - evaluate a formula, render a page, export to another format - is
delegated to :mod:`numbers_cli.engine.app_engine`.
"""

from __future__ import annotations

import datetime as _dt
import warnings
from pathlib import Path
from typing import Any

import numbers_parser as np

from ..errors import DocumentError, UnsupportedOperation

# Values that look like these strings are coerced to their typed form on write,
# so `nmbr set ... 42` stores a number and `nmbr set ... true` stores a boolean.
_TRUE = {"true", "yes"}
_FALSE = {"false", "no"}


def open_document(path: str | Path) -> np.Document:
    """Open an existing ``.numbers`` file.

    Raises :class:`DocumentError` with an actionable hint for the failure modes an
    agent is most likely to hit: a missing file or a password protected document.
    """
    p = Path(path)
    if not p.exists():
        raise DocumentError(f"No such file: {p}", hint="Check the path, or use `nmbr create` first")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # parser warns about fonts, categories, etc.
            return np.Document(str(p))
    except np.UnsupportedError as exc:
        raise DocumentError(
            f"Cannot open {p.name}: {exc}",
            hint="Password protected files must be re-saved without a password in Numbers first",
        )
    except (np.FileError, np.FileFormatError, Exception) as exc:  # noqa: BLE001
        raise DocumentError(f"Failed to open {p.name}: {exc}", hint="Is this a valid .numbers file?")


def new_document(
    sheet_names: list[str] | None = None,
    num_rows: int = 12,
    num_cols: int = 8,
) -> np.Document:
    """Create a blank document. The first sheet keeps its default table."""
    names = sheet_names or ["Sheet 1"]
    doc = np.Document(sheet_name=names[0], num_rows=num_rows, num_cols=num_cols)
    for name in names[1:]:
        doc.add_sheet(name, num_rows=num_rows, num_cols=num_cols)
    return doc


def save_document(doc: np.Document, path: str | Path) -> None:
    try:
        doc.save(str(path))
    except Exception as exc:  # noqa: BLE001
        raise DocumentError(f"Failed to save {Path(path).name}: {exc}")


def coerce_value(raw: Any) -> Any:
    """Turn a command line string into the typed value ``numbers-parser`` expects.

    Strings that parse as an integer, float, boolean, or ``YYYY-MM-DD`` date are
    stored as that type; everything else is stored as text. A leading ``=`` marks
    a formula and is handled by the caller, not here.
    """
    if not isinstance(raw, str):
        return raw
    text = raw.strip()
    if text == "":
        return None
    low = text.lower()
    if low in _TRUE:
        return True
    if low in _FALSE:
        return False
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return _dt.datetime.strptime(text, fmt)
        except ValueError:
            continue
    return text


def cell_to_json(cell: Any) -> dict[str, Any]:
    """Serialise a cell into a JSON friendly record."""
    value = getattr(cell, "value", None)
    if isinstance(value, (_dt.datetime, _dt.date)):
        value = value.isoformat()
    elif isinstance(value, _dt.timedelta):
        value = value.total_seconds()
    record: dict[str, Any] = {
        "type": type(cell).__name__,
        "value": value,
        "formatted": getattr(cell, "formatted_value", None),
    }
    if getattr(cell, "is_formula", False):
        record["formula"] = getattr(cell, "formula", None)
    return record


def is_formula_input(raw: Any) -> bool:
    return isinstance(raw, str) and raw.strip().startswith("=")


def write_value(table: Any, row: int, col: int, raw: Any) -> None:
    """Write a literal (non formula) value into a cell."""
    if is_formula_input(raw):  # pragma: no cover - callers route formulas elsewhere
        raise UnsupportedOperation(
            "Formula writing is handled by the router, not the parser engine directly",
            hint="Use `nmbr set` which routes formulas through recalculation",
        )
    table.write(row, col, coerce_value(raw))
