"""Detection of the Numbers application.

These cover the pure resolution logic in :mod:`numbers_cli.engine.app_engine`
without touching a real macOS install: the subprocess and filesystem probes are
monkeypatched so the tests run on any platform.
"""

import subprocess

from numbers_cli.engine import app_engine as ae


def test_numbers_app_path_prefers_fixed_location(monkeypatch):
    monkeypatch.setattr(ae.Path, "exists", lambda self: True)
    assert ae.numbers_app_path() == "/Applications/Numbers.app"


def test_numbers_app_path_resolves_renamed_install(monkeypatch):
    # A managed or re-signed install lives under a different on-disk name; the
    # fixed path misses but LaunchServices still resolves it.
    monkeypatch.setattr(ae.Path, "exists", lambda self: False)
    monkeypatch.setattr(
        ae, "_launch_services_path", lambda name: "/Applications/Numbers Creator Studio.app"
    )

    def unreachable(bundle_id):
        raise AssertionError("mdfind should not run once LaunchServices resolves")

    monkeypatch.setattr(ae, "_mdfind_bundle", unreachable)
    assert ae.numbers_app_path() == "/Applications/Numbers Creator Studio.app"


def test_numbers_app_path_falls_back_to_spotlight(monkeypatch):
    monkeypatch.setattr(ae.Path, "exists", lambda self: False)
    monkeypatch.setattr(ae, "_launch_services_path", lambda name: None)
    seen = []

    def fake_mdfind(bundle_id):
        seen.append(bundle_id)
        return "/Apps/Numbers.app" if bundle_id == "com.apple.Numbers" else None

    monkeypatch.setattr(ae, "_mdfind_bundle", fake_mdfind)
    assert ae.numbers_app_path() == "/Apps/Numbers.app"
    assert seen == ["com.apple.Numbers"]  # current bundle id tried first


def test_numbers_app_path_none_when_absent(monkeypatch):
    monkeypatch.setattr(ae.Path, "exists", lambda self: False)
    monkeypatch.setattr(ae, "_launch_services_path", lambda name: None)
    monkeypatch.setattr(ae, "_mdfind_bundle", lambda bundle_id: None)
    assert ae.numbers_app_path() is None


def test_launch_services_path_reads_osascript(monkeypatch):
    monkeypatch.setattr(ae.shutil, "which", lambda cmd: "/usr/bin/osascript")

    def fake_run(cmd, capture_output, text, timeout):
        assert cmd[0] == "osascript"
        return subprocess.CompletedProcess(
            cmd, 0, stdout="/Applications/Numbers Creator Studio.app/\n", stderr=""
        )

    monkeypatch.setattr(ae.subprocess, "run", fake_run)
    assert ae._launch_services_path("Numbers") == "/Applications/Numbers Creator Studio.app/"


def test_launch_services_path_none_on_error(monkeypatch):
    monkeypatch.setattr(ae.shutil, "which", lambda cmd: "/usr/bin/osascript")

    def fake_run(cmd, capture_output, text, timeout):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="not found")

    monkeypatch.setattr(ae.subprocess, "run", fake_run)
    assert ae._launch_services_path("Numbers") is None


def test_launch_services_path_none_without_osascript(monkeypatch):
    monkeypatch.setattr(ae.shutil, "which", lambda cmd: None)
    assert ae._launch_services_path("Numbers") is None


def test_available_reflects_detection(monkeypatch):
    monkeypatch.setattr(ae.shutil, "which", lambda cmd: "/usr/bin/osascript")
    monkeypatch.setattr(ae, "numbers_app_path", lambda: "/Applications/Numbers.app")
    assert ae.available() is True
    monkeypatch.setattr(ae, "numbers_app_path", lambda: None)
    assert ae.available() is False


# --- app identity and functional health probe --------------------------------

import plistlib
from pathlib import Path

from numbers_cli.errors import NumbersCliError


def _fake_app_bundle(tmp_path, **plist):
    app = tmp_path / "Numbers Creator Studio.app"
    (app / "Contents").mkdir(parents=True)
    with open(app / "Contents" / "Info.plist", "wb") as handle:
        plistlib.dump(plist, handle)
    return str(app)


def test_numbers_app_info_reads_bundle_plist(tmp_path, monkeypatch):
    app = _fake_app_bundle(
        tmp_path,
        CFBundleDisplayName="Numbers Creator Studio",
        CFBundleName="Numbers",
        CFBundleShortVersionString="15.3",
        CFBundleIdentifier="com.apple.Numbers",
    )
    monkeypatch.setattr(ae, "numbers_app_path", lambda: app)
    info = ae.numbers_app_info()
    assert info["name"] == "Numbers Creator Studio"  # display name wins over CFBundleName
    assert info["version"] == "15.3"
    assert info["bundle_id"] == "com.apple.Numbers"
    assert info["path"] == app


def test_numbers_app_info_none_when_absent(monkeypatch):
    monkeypatch.setattr(ae, "numbers_app_path", lambda: None)
    assert ae.numbers_app_info() is None


def test_health_reports_healthy_on_round_trip(monkeypatch):
    monkeypatch.setattr(ae, "available", lambda: True)
    monkeypatch.setattr(ae, "numbers_app_info", lambda: {"name": "Numbers", "version": "15.3"})
    monkeypatch.setattr(
        ae, "get_cells", lambda file, cells: {"cells": [{"a1": "A1", "value": 1}]}
    )
    result = ae.health()
    assert result["healthy"] is True
    assert "error" not in result
    assert result["app"]["version"] == "15.3"


def test_health_reports_unhealthy_when_engine_errors(monkeypatch):
    monkeypatch.setattr(ae, "available", lambda: True)
    monkeypatch.setattr(ae, "numbers_app_info", lambda: None)

    def boom(file, cells):
        raise NumbersCliError("Numbers reported an error: doc is null", code="APP_ERROR")

    monkeypatch.setattr(ae, "get_cells", boom)
    result = ae.health()
    assert result["healthy"] is False
    assert "doc is null" in result["error"]


def test_health_short_circuits_when_unavailable(monkeypatch):
    monkeypatch.setattr(ae, "available", lambda: False)

    def unreachable(file, cells):
        raise AssertionError("must not drive Numbers when it is unavailable")

    monkeypatch.setattr(ae, "get_cells", unreachable)
    result = ae.health()
    assert result["healthy"] is False
    assert "not detected" in result["error"]
