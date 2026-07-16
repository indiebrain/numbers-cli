"""Engine selection and the formula round trip.

A :class:`Session` opens one document, collects edits, and commits them with the
right engine for each:

* literal values are written in memory through ``parser_engine`` and saved once;
* formulas cannot be written by the parser at all (it would store the text
  ``=A1+A2`` verbatim), so after the parser save the session hands the formula
  cells to ``app_engine``, which enters them in Numbers where they evaluate, and
  reads the computed values back.

When a formula edit is requested but Numbers is unavailable the session raises
:class:`EngineUnavailable` rather than silently storing wrong text - unless the
caller opts into ``allow_text_formula`` to store the literal string on purpose.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .engine import app_engine, parser_engine as pe
from .errors import EngineUnavailable
from .layers import l2_dom
from .paths import resolve


def _index_of(items: Any, obj: Any) -> int:
    for i, item in enumerate(items):
        if item is obj:
            return i
    raise EngineUnavailable("Could not locate the addressed sheet or table", hint="Re-open the file")


class Session:
    """A single open document plus the edits to apply on :meth:`commit`."""

    def __init__(self, file: str | Path, allow_text_formula: bool = False):
        self.file = str(Path(file))
        self.allow_text_formula = allow_text_formula
        self.document = pe.open_document(self.file)
        self._literal: list[tuple[str, Any]] = []
        self._formula: list[dict[str, Any]] = []
        self.warnings: list[str] = []

    # -- collecting edits --------------------------------------------------

    def set(self, path: str, raw: Any) -> None:
        """Queue a value edit, classifying it as literal or formula."""
        if pe.is_formula_input(raw):
            self._queue_formula(path, raw)
        else:
            self._literal.append((path, raw))

    def _queue_formula(self, path: str, raw: str) -> None:
        target = resolve(self.document, path)
        cells = l2_dom._leaf_cells(target, for_write=True)  # cell or range
        sheet_idx = _index_of(self.document.sheets, target.sheet)
        table_idx = _index_of(target.sheet.tables, target.table)
        from numbers_parser import xl_rowcol_to_cell

        for row, col in cells:
            self._formula.append(
                {"sheet": sheet_idx, "table": table_idx, "a1": xl_rowcol_to_cell(row, col), "value": raw}
            )

    # -- applying edits ----------------------------------------------------

    def commit(self) -> dict[str, Any]:
        """Apply queued edits and save. Returns a summary of what happened."""
        written: list[str] = []
        for path, raw in self._literal:
            result = l2_dom.set_value(self.document, path, raw)
            written.extend(result["written"])
        pe.save_document(self.document, self.file)

        evaluated: list[dict[str, Any]] = []
        if self._formula:
            evaluated = self._apply_formulas()

        return {
            "file": self.file,
            "literal_cells": written,
            "formula_cells": evaluated,
        }

    def _apply_formulas(self) -> list[dict[str, Any]]:
        if not app_engine.available():
            if self.allow_text_formula:
                # Store the raw text through the parser, clearly flagged.
                for edit in self._formula:
                    self._store_text(edit)
                pe.save_document(self.document, self.file)
                self.warnings.append(
                    "Numbers is unavailable: formulas were stored as literal text and will NOT "
                    "evaluate until opened and recalculated in Numbers."
                )
                return [{"a1": e["a1"], "stored_as_text": e["value"]} for e in self._formula]
            raise EngineUnavailable(
                "Writing a formula needs the Numbers application, which is unavailable",
                hint="Install Numbers, or pass --as-text to store the formula string literally",
            )
        result = app_engine.set_cells(self.file, self._formula)
        return result.get("edits", [])

    def _store_text(self, edit: dict[str, Any]) -> None:
        from numbers_parser import xl_cell_to_rowcol

        sheet = self.document.sheets[edit["sheet"]]
        table = sheet.tables[edit["table"]]
        row, col = xl_cell_to_rowcol(edit["a1"])
        table.write(row, col, edit["value"])


def set_cells(file: str | Path, edits: list[tuple[str, Any]], allow_text_formula: bool = False) -> dict[str, Any]:
    """Convenience wrapper: open, queue every ``(path, value)`` edit, commit."""
    session = Session(file, allow_text_formula=allow_text_formula)
    for path, raw in edits:
        session.set(path, raw)
    summary = session.commit()
    summary["warnings"] = session.warnings
    return summary
