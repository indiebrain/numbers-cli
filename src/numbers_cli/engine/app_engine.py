"""The Numbers application back end, driven through ``osascript`` (JavaScript for
Automation).

Used only for what the parser cannot do: entering real formulas so Numbers
evaluates them, forcing a recalculation, and native export (csv, xlsx, pdf). It
is macOS only and needs the Numbers application plus Automation permission, which
macOS prompts for on first use.

Every entry point checks :func:`available` first and raises
:class:`EngineUnavailable` with an actionable hint when Numbers is missing, so a
formula edit fails loudly instead of silently storing wrong text.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..errors import EngineUnavailable, NumbersCliError

# The automation script ships inside the package (numbers_cli/jxa/) so it is
# found the same way whether running from the source tree or a pip install.
_JXA = Path(__file__).resolve().parent.parent / "jxa" / "numbers_ops.js"


def numbers_app_path() -> str | None:
    """Return the path to Numbers.app, or ``None`` if it is not installed."""
    fixed = Path("/Applications/Numbers.app")
    if fixed.exists():
        return str(fixed)
    try:
        out = subprocess.run(
            ["mdfind", "kMDItemCFBundleIdentifier == 'com.apple.iWork.Numbers'"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        first = out.stdout.strip().splitlines()
        return first[0] if first else None
    except (OSError, subprocess.SubprocessError):
        return None


def available() -> bool:
    """True when this machine can drive Numbers (macOS, osascript, Numbers.app)."""
    return shutil.which("osascript") is not None and numbers_app_path() is not None


def _require_available() -> None:
    if shutil.which("osascript") is None:
        raise EngineUnavailable(
            "osascript is not available; the Numbers application back end is macOS only",
            hint="Formula recalculation, rendering, and export need macOS with Numbers installed",
        )
    if numbers_app_path() is None:
        raise EngineUnavailable(
            "The Numbers application is not installed",
            hint="Install Numbers from the App Store to enable formulas, rendering, and export",
        )


def _run(payload: dict[str, Any], timeout: int = 120) -> dict[str, Any]:
    _require_available()
    if not _JXA.exists():  # pragma: no cover - packaging guard
        raise NumbersCliError(f"Missing automation script: {_JXA}", code="INTERNAL")
    try:
        proc = subprocess.run(
            ["osascript", "-l", "JavaScript", str(_JXA), json.dumps(payload)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise EngineUnavailable(
            "The Numbers application did not respond in time",
            hint="Close any modal dialog in Numbers and retry",
        )
    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        hint = "Grant Automation permission to your terminal in System Settings > Privacy & Security"
        if "-1743" in stderr or "Not authorized" in stderr:
            raise EngineUnavailable(f"Numbers automation was denied: {stderr}", hint=hint)
        raise NumbersCliError(f"Numbers automation failed: {stderr}", code="APP_ERROR", hint=hint)
    try:
        result = json.loads(proc.stdout.strip() or "{}")
    except json.JSONDecodeError:
        raise NumbersCliError(f"Unreadable automation output: {proc.stdout!r}", code="APP_ERROR")
    if not result.get("ok", False):
        raise NumbersCliError(
            f"Numbers reported an error: {result.get('error', 'unknown')}", code="APP_ERROR"
        )
    return result


def _edit(sheet: int | None, table: int | None, a1: str, value: Any) -> dict[str, Any]:
    """A single cell edit in the shape the JXA dispatcher expects (zero based indices)."""
    return {"sheet": sheet, "table": table, "a1": a1, "value": value}


def set_cells(file: str | Path, edits: list[dict[str, Any]]) -> dict[str, Any]:
    """Set cell values or formulas through Numbers so formulas evaluate, then save."""
    return _run({"op": "set", "file": str(Path(file).resolve()), "edits": edits})


def recalc(file: str | Path) -> dict[str, Any]:
    """Force Numbers to recalculate the document and save it."""
    return _run({"op": "recalc", "file": str(Path(file).resolve())})


def get_cells(file: str | Path, cells: list[dict[str, Any]]) -> dict[str, Any]:
    """Read evaluated cell values and formulas back from Numbers."""
    return _run({"op": "get", "file": str(Path(file).resolve()), "cells": cells})


def export(file: str | Path, fmt: str, out: str | Path) -> dict[str, Any]:
    """Export the document with Numbers' native exporter (csv, xlsx, pdf)."""
    return _run(
        {
            "op": "export",
            "file": str(Path(file).resolve()),
            "format": fmt,
            "out": str(Path(out).resolve()),
        }
    )
