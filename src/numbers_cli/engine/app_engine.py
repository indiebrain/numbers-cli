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


# Numbers has shipped under more than one bundle identifier over the years, and
# managed or re-signed installs (for example an MDM-deployed build) can rename
# the application on disk. Detection therefore tries several signals rather than
# a single hard-coded path.
_BUNDLE_IDS = ("com.apple.Numbers", "com.apple.iWork.Numbers")


def _mdfind_bundle(bundle_id: str) -> str | None:
    """Ask Spotlight for the app with ``bundle_id``. ``None`` if unindexed."""
    try:
        out = subprocess.run(
            ["mdfind", f"kMDItemCFBundleIdentifier == '{bundle_id}'"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    lines = out.stdout.strip().splitlines()
    return lines[0] if lines else None


def _launch_services_path(name: str) -> str | None:
    """Resolve an app by name through LaunchServices, via ``osascript``.

    This is the authoritative signal: it mirrors how the automation script
    reaches the app (``Application("Numbers")``), so if this resolves a path the
    engine will work. It also succeeds when the app has been renamed on disk or
    when Spotlight is disabled, both of which defeat the path and ``mdfind``
    checks.
    """
    if shutil.which("osascript") is None:
        return None
    try:
        out = subprocess.run(
            ["osascript", "-e", f'POSIX path of (path to application "{name}")'],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    path = out.stdout.strip()
    return path if out.returncode == 0 and path else None


def numbers_app_path() -> str | None:
    """Return the path to the Numbers application, or ``None`` if not installed."""
    # 1. The standard install location: cheap and covers the common case.
    fixed = Path("/Applications/Numbers.app")
    if fixed.exists():
        return str(fixed)
    # 2. LaunchServices, which resolves renamed installs and does not need
    #    Spotlight. This is what the automation actually drives, so a hit here
    #    means the engine will work.
    resolved = _launch_services_path("Numbers")
    if resolved:
        return resolved
    # 3. Spotlight, for any known bundle identifier, as a final fallback.
    for bundle_id in _BUNDLE_IDS:
        hit = _mdfind_bundle(bundle_id)
        if hit:
            return hit
    return None


def numbers_app_info() -> dict[str, Any] | None:
    """Identity of the resolved Numbers application, or ``None`` if not installed.

    Reads the bundle's ``Info.plist`` directly (no application launch), so it is
    cheap and side effect free. Surfacing the display name, version, and bundle
    identifier makes it obvious *which* app the engine will drive - Apple has
    shipped it under more than one name (for example "Numbers Creator Studio"
    with bundle ``com.apple.Numbers``), which is otherwise invisible.
    """
    path = numbers_app_path()
    if path is None:
        return None
    info: dict[str, Any] = {"path": path, "name": None, "version": None, "bundle_id": None}
    plist = Path(path) / "Contents" / "Info.plist"
    try:
        import plistlib

        with open(plist, "rb") as handle:
            data = plistlib.load(handle)
        info["name"] = data.get("CFBundleDisplayName") or data.get("CFBundleName")
        info["version"] = data.get("CFBundleShortVersionString")
        info["bundle_id"] = data.get("CFBundleIdentifier")
    except (OSError, ValueError):  # unreadable or malformed plist
        pass
    return info


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


def health() -> dict[str, Any]:
    """Exercise the application back end end to end and report whether it works.

    :func:`available` only proves that ``osascript`` and a Numbers app *resolve*;
    it never drives the automation, so it reports healthy even when every app
    operation is broken (as happened when ``app.open`` began returning ``null``).
    This probe writes a throwaway document with the parser, opens it through the
    JXA ``get`` path - the same ``withDocument`` open that real operations use -
    and confirms the value round trips. It launches Numbers, so it is opt in
    (``nmbr doctor --probe``) rather than part of the default report.
    """
    result: dict[str, Any] = {"available": available(), "app": numbers_app_info()}
    if not available():
        result["healthy"] = False
        result["error"] = "Numbers application not detected"
        return result

    import tempfile

    from . import parser_engine as pe

    try:
        with tempfile.TemporaryDirectory() as tmp:
            probe = Path(tmp) / "numbers-cli-healthcheck.numbers"
            doc = pe.new_document(["Check"], num_rows=2, num_cols=2)
            doc.sheets[0].tables[0].write("A1", 1)
            pe.save_document(doc, probe)
            read = get_cells(probe, [{"sheet": 0, "table": 0, "a1": "A1"}])
            value = read.get("cells", [{}])[0].get("value")
            result["healthy"] = str(value) in ("1", "1.0")
            if not result["healthy"]:
                result["error"] = f"round trip returned {value!r}, expected 1"
    except NumbersCliError as exc:
        result["healthy"] = False
        result["error"] = str(exc)
    return result
