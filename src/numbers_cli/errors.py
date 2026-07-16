"""Structured errors and the JSON response envelope.

Every command returns the same shape so an agent can parse the result and, when
something goes wrong, act on a stable ``code`` and a human readable ``hint``
rather than scraping a stack trace::

    {"ok": true,  "data": ...}
    {"ok": false, "error": {"code": "PATH_NOT_FOUND", "message": "...", "hint": "..."}}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class NumbersCliError(Exception):
    """Base class for every error the tool raises on purpose.

    ``code`` is a stable machine token, ``hint`` is a suggestion the agent can
    act on. Both flow straight into the JSON envelope.
    """

    code = "ERROR"

    def __init__(self, message: str, hint: str = "", code: str | None = None):
        super().__init__(message)
        self.message = message
        self.hint = hint
        if code:
            self.code = code


class UsageError(NumbersCliError):
    code = "USAGE"


class PathError(NumbersCliError):
    code = "PATH_INVALID"


class PathNotFound(NumbersCliError):
    code = "PATH_NOT_FOUND"


class DocumentError(NumbersCliError):
    code = "DOCUMENT_ERROR"


class EngineUnavailable(NumbersCliError):
    """Raised when an operation needs Numbers.app but it is not available."""

    code = "ENGINE_UNAVAILABLE"


class UnsupportedOperation(NumbersCliError):
    code = "UNSUPPORTED"


@dataclass
class Envelope:
    """The response wrapper shared by the command line and the MCP server."""

    ok: bool
    data: Any = None
    error: dict[str, str] | None = None
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def success(cls, data: Any = None, warnings: list[str] | None = None) -> "Envelope":
        return cls(ok=True, data=data, warnings=warnings or [])

    @classmethod
    def failure(cls, err: NumbersCliError, warnings: list[str] | None = None) -> "Envelope":
        return cls(
            ok=False,
            error={"code": err.code, "message": err.message, "hint": err.hint},
            warnings=warnings or [],
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"ok": self.ok}
        if self.ok:
            out["data"] = self.data
        else:
            out["error"] = self.error
        if self.warnings:
            out["warnings"] = self.warnings
        return out
