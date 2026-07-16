"""Model Context Protocol server for Apple Numbers.

Exposes the same operations as the ``nmbr`` command line as MCP tools over stdio,
so Claude Code, Cursor, and other clients can call them as native tools - the
same integration OfficeCli offers. Each tool returns the shared response envelope
as a dict, so a client sees ``{"ok": ..., "data"/"error": ...}`` consistently.

Run with ``nmbr mcp`` (or ``python -m numbers_cli.mcp_server``).
"""

from __future__ import annotations

from typing import Any

# The MCP SDK is an optional dependency (the `mcp` extra). Importing this module
# without it raises ImportError, which the `nmbr mcp` command turns into a clear
# "install numbers-cli[mcp]" message.
from mcp.server.fastmcp import FastMCP

from .engine import app_engine, parser_engine as pe
from .errors import Envelope, NumbersCliError
from .layers import l1_view, l2_dom, l3_raw
from .ops import batch as batch_ops, dump as dump_ops, merge as merge_ops
from .router import set_cells


def _wrap(fn) -> dict[str, Any]:
    """Run a unit of work and package it in the response envelope."""
    try:
        data = fn()
        warnings = data.pop("warnings", []) if isinstance(data, dict) else []
        return Envelope.success(data, warnings=warnings).to_dict()
    except NumbersCliError as exc:
        return Envelope.failure(exc).to_dict()
    except Exception as exc:  # noqa: BLE001
        return Envelope.failure(NumbersCliError(str(exc), code="INTERNAL")).to_dict()


def build_server():
    mcp = FastMCP("apple-numbers")

    @mcp.tool()
    def numbers_doctor() -> dict:
        """Report tool version and whether the Numbers application back end is available."""
        return _wrap(
            lambda: {
                "numbers_parser": getattr(__import__("numbers_parser"), "__version__", "?"),
                "app_engine_available": app_engine.available(),
                "numbers_app": app_engine.numbers_app_path(),
            }
        )

    @mcp.tool()
    def numbers_create(file: str, sheets: list[str] | None = None, rows: int = 12, cols: int = 8) -> dict:
        """Create a blank .numbers file with the given sheet names."""

        def go():
            doc = pe.new_document(sheets or ["Sheet 1"], num_rows=rows, num_cols=cols)
            pe.save_document(doc, file)
            return {"created": file, "sheets": sheets or ["Sheet 1"]}

        return _wrap(go)

    @mcp.tool()
    def numbers_view(file: str, path: str | None = None, fmt: str = "text") -> dict:
        """Render a document, sheet, or table as text|csv|md|outline|json (L1)."""

        def go():
            doc = pe.open_document(file)
            rendered = l1_view.render_text_view(doc, path, fmt)
            return rendered if isinstance(rendered, dict) else {"format": fmt, "view": rendered}

        return _wrap(go)

    @mcp.tool()
    def numbers_get(file: str, path: str) -> dict:
        """Read a cell, range, row, column, or table by path (L2)."""
        return _wrap(lambda: l2_dom.get(pe.open_document(file), path))

    @mcp.tool()
    def numbers_set(file: str, path: str, value: str, as_text: bool = False) -> dict:
        """Write a value or =formula into a cell or range; formulas route through Numbers (L2)."""
        return _wrap(lambda: set_cells(file, [(path, value)], allow_text_formula=as_text))

    @mcp.tool()
    def numbers_add(file: str, kind: str, path: str = "", name: str | None = None, count: int = 1) -> dict:
        """Add a sheet, table, row, or column (L2)."""

        def go():
            doc = pe.open_document(file)
            result = l2_dom.add(doc, path, kind, name=name, count=count)
            pe.save_document(doc, file)
            return result

        return _wrap(go)

    @mcp.tool()
    def numbers_remove(file: str, path: str, kind: str | None = None, count: int = 1) -> dict:
        """Remove a row or column (removing sheets or tables is unsupported) (L2)."""

        def go():
            doc = pe.open_document(file)
            result = l2_dom.remove(doc, path, kind=kind, count=count)
            pe.save_document(doc, file)
            return result

        return _wrap(go)

    @mcp.tool()
    def numbers_query(file: str, contains: str, path: str | None = None, ignore_case: bool = True) -> dict:
        """Find cells whose text contains a substring and return their paths (L2)."""
        return _wrap(lambda: l2_dom.query(pe.open_document(file), contains, path=path, ignore_case=ignore_case))

    @mcp.tool()
    def numbers_batch(file: str, ops: list[dict], as_text: bool = False) -> dict:
        """Apply a list of set/add/remove operations in one pass."""
        return _wrap(lambda: batch_ops.apply(file, ops, allow_text_formula=as_text))

    @mcp.tool()
    def numbers_merge(template: str, data: dict, out: str) -> dict:
        """Fill {{placeholder}} tokens in a template from a data mapping."""
        return _wrap(lambda: merge_ops.merge(template, data, out))

    @mcp.tool()
    def numbers_dump(file: str) -> dict:
        """Serialise a document to a replayable JSON op-list."""
        return _wrap(lambda: dump_ops.dump(file))

    @mcp.tool()
    def numbers_raw(file: str, id: int | None = None, contains: str | None = None) -> dict:
        """Inspect the underlying IWA protobuf objects (L3, read only)."""
        return _wrap(lambda: l3_raw.read(file, message_id=id, contains=contains))

    @mcp.tool()
    def numbers_recalc(file: str) -> dict:
        """Recalculate formulas via the Numbers application and save."""
        return _wrap(lambda: app_engine.recalc(file))

    @mcp.tool()
    def numbers_export(file: str, to: str, out: str) -> dict:
        """Export via the Numbers application (csv|xlsx|pdf)."""
        return _wrap(lambda: app_engine.export(file, to, out))

    return mcp


def serve() -> None:  # pragma: no cover - long running
    build_server().run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover
    serve()
