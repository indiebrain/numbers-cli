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
