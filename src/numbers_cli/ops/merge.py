"""Template merge: fill ``{{placeholder}}`` tokens from a data mapping.

Mirrors OfficeCli's ``merge``. Every text cell in the template is scanned for
``{{key}}`` tokens and each token is replaced with the matching value from the
data mapping. A cell that is exactly one token adopts the value's native type
(so ``{{total}}`` with ``total: 1234`` becomes the number 1234); a cell that
mixes text and tokens stays text with the tokens substituted in place.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from numbers_parser import xl_rowcol_to_cell

from ..engine import parser_engine as pe
from ..errors import UsageError

_TOKEN = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")
_WHOLE = re.compile(r"^\{\{\s*([^}]+?)\s*\}\}$")


def merge(template: str, data: dict[str, Any], out: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise UsageError("Merge data must be a JSON object of key/value pairs")
    if Path(out).resolve() == Path(template).resolve():
        raise UsageError("Refusing to overwrite the template", hint="Choose a different --out path")

    doc = pe.open_document(template)
    filled: list[dict[str, Any]] = []
    missing: set[str] = set()

    for si, sheet in enumerate(doc.sheets, start=1):
        for ti, table in enumerate(sheet.tables, start=1):
            for r, row in enumerate(table.rows(values_only=True)):
                for c, value in enumerate(row):
                    if not isinstance(value, str) or "{{" not in value:
                        continue
                    new_value, keys, unknown = _substitute(value, data)
                    missing |= unknown
                    if new_value != value:
                        table.write(r, c, new_value)
                        filled.append(
                            {
                                "path": f"/sheet[{si}]/table[{ti}]/cell[{xl_rowcol_to_cell(r, c)}]",
                                "keys": sorted(keys),
                            }
                        )

    pe.save_document(doc, out)
    result = {"out": out, "filled": filled, "count": len(filled)}
    if missing:
        result["warnings"] = [f"No data for placeholders: {', '.join(sorted(missing))}"]
    return result


def _substitute(text: str, data: dict[str, Any]) -> tuple[Any, set[str], set[str]]:
    """Return ``(new_value, resolved_keys, missing_keys)`` for one cell."""
    whole = _WHOLE.match(text)
    if whole:
        key = whole.group(1)
        if key in data:
            return data[key], {key}, set()
        return text, set(), {key}

    resolved: set[str] = set()
    missing: set[str] = set()

    def replace(match: re.Match) -> str:
        key = match.group(1)
        if key in data:
            resolved.add(key)
            return str(data[key])
        missing.add(key)
        return match.group(0)

    return _TOKEN.sub(replace, text), resolved, missing
