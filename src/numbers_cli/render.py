"""L1 rendering to images and pages.

HTML is produced locally from the parsed tables, so it needs no application and
works cross platform - handy for a quick visual check. PDF and PNG are page
faithful renderings and come from the Numbers application through
:mod:`numbers_cli.engine.app_engine` (PNG is a PDF rasterised with ``sips``).
"""

from __future__ import annotations

import html as _html
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .engine import app_engine, parser_engine as pe
from .errors import UsageError
from .layers.l1_view import _table_matrix, _tables_for


def render(file: str, fmt: str, out: str | None, path: str | None) -> str:
    fmt = fmt.lower()
    if fmt == "html":
        return _render_html(file, out, path)
    if fmt == "pdf":
        target = out or str(Path(file).with_suffix(".pdf"))
        app_engine.export(file, "pdf", target)
        return target
    if fmt == "png":
        return _render_png(file, out)
    raise UsageError(f"Cannot render {fmt!r}", hint="Renderable formats: html, pdf, png")


def _render_html(file: str, out: str | None, path: str | None) -> str:
    doc = pe.open_document(file)
    tables = _tables_for(doc, path)
    parts = [
        "<!doctype html><meta charset='utf-8'>",
        "<style>table{border-collapse:collapse;margin:1em 0;font-family:sans-serif}"
        "td,th{border:1px solid #ccc;padding:4px 8px}h2{font-family:sans-serif}</style>",
    ]
    for table in tables:
        parts.append(f"<h2>{_html.escape(table.name)}</h2>")
        parts.append("<table>")
        for i, row in enumerate(_table_matrix(table)):
            tag = "th" if i == 0 else "td"
            cells = "".join(f"<{tag}>{_html.escape(v)}</{tag}>" for v in row)
            parts.append(f"<tr>{cells}</tr>")
        parts.append("</table>")
    markup = "\n".join(parts)
    target = out or str(Path(file).with_suffix(".html"))
    Path(target).write_text(markup, encoding="utf-8")
    return target


def _render_png(file: str, out: str | None) -> str:
    if shutil.which("sips") is None:
        raise UsageError("PNG rendering needs `sips`, a macOS tool", hint="Use --as pdf on other platforms")
    target = out or str(Path(file).with_suffix(".png"))
    with tempfile.TemporaryDirectory() as tmp:
        pdf = str(Path(tmp) / "page.pdf")
        app_engine.export(file, "pdf", pdf)
        subprocess.run(["sips", "-s", "format", "png", pdf, "--out", target], check=True, capture_output=True)
    return target
