"""Apply a list of operations to one document in a single open and save pass.

An operation list is JSON, for example::

    [
      {"op": "add", "kind": "table", "path": "/sheet[1]", "name": "Q1"},
      {"op": "set", "path": "/sheet[1]/table['Q1']/cell[A1]", "value": "Revenue"},
      {"op": "set", "path": "/sheet[1]/table['Q1']/cell[B1]", "value": "=SUM(B2:B9)"}
    ]

Structural operations (``add``, ``remove``) are applied in order as they are read,
so later ``set`` operations can address elements the batch just created. Value
operations are collected and committed together at the end, which lets every
formula go through one Numbers recalculation instead of one per cell.
"""

from __future__ import annotations

from typing import Any

from ..engine import parser_engine as pe
from ..errors import UsageError
from ..layers import l2_dom
from ..router import Session


def apply(file: str, ops: list[dict[str, Any]], allow_text_formula: bool = False) -> dict[str, Any]:
    if not isinstance(ops, list):
        raise UsageError("Batch operations must be a JSON array", hint="See `nmbr dump` for the shape")

    session = Session(file, allow_text_formula=allow_text_formula)
    applied: list[dict[str, Any]] = []

    for i, op in enumerate(ops):
        kind = op.get("op")
        if kind == "set":
            session.set(op["path"], op["value"])  # queued, committed at the end
            applied.append({"op": "set", "path": op["path"]})
        elif kind == "add":
            result = l2_dom.add(
                session.document, op.get("path", ""), op["kind"], name=op.get("name"), count=op.get("count", 1)
            )
            applied.append({"op": "add", **result})
        elif kind == "remove":
            result = l2_dom.remove(session.document, op["path"], kind=op.get("kind"), count=op.get("count", 1))
            applied.append({"op": "remove", **result})
        else:
            raise UsageError(f"Unknown op at index {i}: {kind!r}", hint="Supported ops: set, add, remove")

    summary = session.commit()
    summary["applied"] = applied
    summary["warnings"] = session.warnings
    return summary
