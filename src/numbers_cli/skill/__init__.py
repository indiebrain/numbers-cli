"""Bundled Claude Code skill and its installer.

The skill (``SKILL.md`` plus ``references/``) ships as package data alongside the
tool, so ``nmbr skill install`` can copy it into a Claude Code skills directory.
This runs at command time, not at ``brew install`` time - Homebrew's install
sandbox cannot write to a user's home directory, but a normal command can.
"""

from __future__ import annotations

import shutil
from importlib import resources
from pathlib import Path

from ..errors import UsageError

SKILL_NAME = "apple-numbers"
DEFAULT_ROOT = Path.home() / ".claude" / "skills"


def bundled_skill_dir() -> Path:
    """Return the on-disk path of the skill bundled inside the package."""
    # The skill files live next to this module (numbers_cli/skill/).
    with resources.as_file(resources.files("numbers_cli") / "skill") as p:
        path = Path(p)
    if not (path / "SKILL.md").exists():  # pragma: no cover - packaging guard
        raise UsageError(
            "The bundled skill was not found in this install",
            hint="Reinstall numbers-cli; the skill ships as package data",
        )
    return path


def install(dest_root: str | Path | None = None, force: bool = False) -> Path:
    """Copy the bundled skill into ``<dest_root>/apple-numbers``.

    ``dest_root`` defaults to ``~/.claude/skills``. Refuses to overwrite an
    existing skill directory unless ``force`` is set.
    """
    src = bundled_skill_dir()
    root = Path(dest_root).expanduser() if dest_root else DEFAULT_ROOT
    target = root / SKILL_NAME

    if target.exists():
        if not force:
            raise UsageError(
                f"{target} already exists",
                hint="Pass --force to overwrite the installed skill",
            )
        shutil.rmtree(target)

    root.mkdir(parents=True, exist_ok=True)
    # copy_tree, skipping any Python package cruft that should not travel.
    shutil.copytree(
        src,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "__init__.py"),
    )
    return target
