"""The ``nmbr`` command line.

Each subcommand resolves to a small handler that returns a plain data structure
or raises a :class:`NumbersCliError`. ``main`` wraps the result in the shared JSON
envelope so an agent gets a consistent, parseable response, or a readable table
when ``--human`` is passed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .engine import app_engine, parser_engine as pe
from .errors import Envelope, NumbersCliError, UsageError
from .layers import l1_view, l2_dom
from .router import Session, set_cells


# --- command handlers ----------------------------------------------------


def cmd_create(args: argparse.Namespace) -> Any:
    path = Path(args.file)
    if path.exists() and not args.force:
        raise UsageError(f"{path} already exists", hint="Pass --force to overwrite")
    sheets = args.sheets or ["Sheet 1"]
    doc = pe.new_document(sheets, num_rows=args.rows, num_cols=args.cols)
    pe.save_document(doc, path)
    return {"created": str(path), "sheets": sheets}


def cmd_view(args: argparse.Namespace) -> Any:
    fmt = args.as_.lower()
    if fmt in l1_view.APP_FORMATS:
        from . import render

        out = render.render(args.file, fmt, args.out, args.path)
        return {"rendered": out, "format": fmt}
    doc = pe.open_document(args.file)
    rendered = l1_view.render_text_view(doc, args.path, fmt)
    return rendered if isinstance(rendered, dict) else {"format": fmt, "view": rendered}


def cmd_get(args: argparse.Namespace) -> Any:
    doc = pe.open_document(args.file)
    return l2_dom.get(doc, args.path)


def cmd_set(args: argparse.Namespace) -> Any:
    summary = set_cells(args.file, [(args.path, args.value)], allow_text_formula=args.as_text)
    return summary


def cmd_add(args: argparse.Namespace) -> Any:
    doc = pe.open_document(args.file)
    result = l2_dom.add(doc, args.path or "", args.kind, name=args.name, count=args.count)
    pe.save_document(doc, args.file)
    return result


def cmd_remove(args: argparse.Namespace) -> Any:
    doc = pe.open_document(args.file)
    result = l2_dom.remove(doc, args.path, kind=args.kind, count=args.count)
    pe.save_document(doc, args.file)
    return result


def cmd_query(args: argparse.Namespace) -> Any:
    doc = pe.open_document(args.file)
    return l2_dom.query(doc, args.contains, path=args.path, ignore_case=not args.case_sensitive)


def cmd_recalc(args: argparse.Namespace) -> Any:
    return app_engine.recalc(args.file)


def cmd_export(args: argparse.Namespace) -> Any:
    out = args.out or str(Path(args.file).with_suffix("." + args.to.replace("xlsx", "xlsx")))
    return app_engine.export(args.file, args.to, out)


def cmd_batch(args: argparse.Namespace) -> Any:
    from .ops import batch

    ops = json.loads(Path(args.ops).read_text()) if Path(args.ops).exists() else json.loads(args.ops)
    return batch.apply(args.file, ops, allow_text_formula=args.as_text)


def cmd_merge(args: argparse.Namespace) -> Any:
    from .ops import merge

    data = json.loads(Path(args.data).read_text())
    return merge.merge(args.template, data, args.out)


def cmd_dump(args: argparse.Namespace) -> Any:
    from .ops import dump

    return dump.dump(args.file)


def cmd_raw(args: argparse.Namespace) -> Any:
    from .layers import l3_raw

    return l3_raw.read(args.file, message_id=args.id, contains=args.grep)


def cmd_mcp(args: argparse.Namespace) -> Any:  # pragma: no cover - long running
    try:
        from .mcp_server import serve
    except ImportError:
        raise UsageError(
            "The MCP server support is not installed",
            hint="Install the optional extra: pip install 'numbers-cli[mcp]'",
            code="MCP_NOT_INSTALLED",
        )
    serve()
    return None


def cmd_doctor(args: argparse.Namespace) -> Any:
    return {
        "version": __version__,
        "numbers_parser": _parser_version(),
        "app_engine_available": app_engine.available(),
        "numbers_app": app_engine.numbers_app_path(),
    }


def _parser_version() -> str:
    try:
        import numbers_parser

        return numbers_parser.__version__
    except Exception:  # noqa: BLE001
        return "unknown"


# --- argument parser -----------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nmbr", description="OfficeCli-style tool for Apple Numbers")
    parser.add_argument("--human", action="store_true", help="print human readable output")
    parser.add_argument("--version", action="version", version=f"nmbr {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create", help="create a blank .numbers file")
    p.add_argument("file")
    p.add_argument("--sheets", nargs="+", help="sheet names (default: one 'Sheet 1')")
    p.add_argument("--rows", type=int, default=12)
    p.add_argument("--cols", type=int, default=8)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_create)

    p = sub.add_parser("view", help="render a document, sheet, or table (L1)")
    p.add_argument("file")
    p.add_argument("path", nargs="?", help="optional path, for example /sheet[1]/table[1]")
    p.add_argument("--as", dest="as_", default="text", help="text|csv|md|outline|json|png|pdf|html")
    p.add_argument("--out", help="output file for png|pdf|html")
    p.set_defaults(func=cmd_view)

    p = sub.add_parser("get", help="read a cell, range, row, column, or table (L2)")
    p.add_argument("file")
    p.add_argument("path")
    p.set_defaults(func=cmd_get)

    p = sub.add_parser("set", help="write a value or =formula into a cell or range (L2)")
    p.add_argument("file")
    p.add_argument("path")
    p.add_argument("value")
    p.add_argument("--as-text", action="store_true", help="store a formula string literally if Numbers is absent")
    p.set_defaults(func=cmd_set)

    p = sub.add_parser("add", help="add a sheet, table, row, or column (L2)")
    p.add_argument("file")
    p.add_argument("path", nargs="?", help="context path, for example /sheet[1] or /sheet[1]/table[1]")
    p.add_argument("--kind", required=True, choices=["sheet", "table", "row", "col", "column"])
    p.add_argument("--name", help="name for a new sheet or table")
    p.add_argument("--count", type=int, default=1)
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("remove", help="remove a sheet, table, row, or column (L2)")
    p.add_argument("file")
    p.add_argument("path")
    p.add_argument("--kind", choices=["sheet", "table", "row", "col", "column"])
    p.add_argument("--count", type=int, default=1)
    p.set_defaults(func=cmd_remove)

    p = sub.add_parser("query", help="find cells whose text contains a substring (L2)")
    p.add_argument("file")
    p.add_argument("contains")
    p.add_argument("--path", help="restrict to a sheet or table")
    p.add_argument("--case-sensitive", action="store_true")
    p.set_defaults(func=cmd_query)

    p = sub.add_parser("recalc", help="recalculate formulas via Numbers.app")
    p.add_argument("file")
    p.set_defaults(func=cmd_recalc)

    p = sub.add_parser("export", help="export via Numbers.app (csv|xlsx|pdf)")
    p.add_argument("file")
    p.add_argument("--to", required=True, choices=["csv", "xlsx", "pdf"])
    p.add_argument("--out", help="output path (default: alongside the source)")
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("batch", help="apply a JSON list of operations in one pass")
    p.add_argument("file")
    p.add_argument("ops", help="path to a .json file or an inline JSON array")
    p.add_argument("--as-text", action="store_true")
    p.set_defaults(func=cmd_batch)

    p = sub.add_parser("merge", help="fill {{placeholders}} in a template from JSON data")
    p.add_argument("template")
    p.add_argument("data", help="path to a JSON file of key/value pairs")
    p.add_argument("-o", "--out", required=True)
    p.set_defaults(func=cmd_merge)

    p = sub.add_parser("dump", help="serialise a document to a replayable JSON op-list")
    p.add_argument("file")
    p.set_defaults(func=cmd_dump)

    p = sub.add_parser("raw", help="inspect the underlying IWA protobuf objects (L3, read)")
    p.add_argument("file")
    p.add_argument("--id", type=int, help="show a single message by id")
    p.add_argument("--grep", help="only messages whose type name contains this text")
    p.set_defaults(func=cmd_raw)

    p = sub.add_parser("doctor", help="report versions and back end availability")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("mcp", help="run the MCP server over stdio")
    p.set_defaults(func=cmd_mcp)

    return parser


def _print_human(env: Envelope) -> None:
    if not env.ok:
        err = env.error or {}
        print(f"error [{err.get('code')}]: {err.get('message')}", file=sys.stderr)
        if err.get("hint"):
            print(f"  hint: {err['hint']}", file=sys.stderr)
        return
    data = env.data
    if isinstance(data, dict) and "view" in data:
        print(data["view"])
    else:
        print(json.dumps(data, indent=2, default=str))
    for w in env.warnings:
        print(f"warning: {w}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        data = args.func(args)
        warnings = data.pop("warnings", []) if isinstance(data, dict) else []
        env = Envelope.success(data, warnings=warnings)
    except NumbersCliError as exc:
        env = Envelope.failure(exc)
    except BrokenPipeError:  # pragma: no cover
        return 0
    except Exception as exc:  # noqa: BLE001 - last resort, still structured
        env = Envelope.failure(NumbersCliError(str(exc), code="INTERNAL"))

    if getattr(args, "human", False):
        _print_human(env)
    else:
        print(json.dumps(env.to_dict(), default=str))
    return 0 if env.ok else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
