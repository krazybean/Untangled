# SPDX-License-Identifier: GPL-2.0-only
"""Something Untangled tells the user about, as spec/diagnostics.md defines it: a level, a stable
code for the condition, a message for people, and the project-relative files it is about."""

import json
from dataclasses import dataclass, field
from typing import Any

WARNING = "warning"
ERROR = "error"


@dataclass(frozen=True)
class Diagnostic:
    level: str
    code: str
    message: str
    files: list[str] = field(default_factory=list)
    """Project-relative paths with `/`, in the order they are reported."""

    @classmethod
    def warning(cls, code: str, message: str, files: list[str] | None = None) -> "Diagnostic":
        return cls(WARNING, code, message, list(files or []))

    @classmethod
    def error(cls, code: str, message: str, files: list[str] | None = None) -> "Diagnostic":
        return cls(ERROR, code, message, list(files or []))

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"level": self.level, "code": self.code, "message": _valid(self.message)}
        if self.files:
            data["files"] = [_valid(file) for file in self.files]
        return data

    def to_json(self) -> str:
        """The JSON Lines form: one compact object, no line break."""
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))

    def to_text(self) -> str:
        """The text form: `warning: <message>` or `error: <message>`, without the line break."""
        return f"{self.level}: {self.message}"


def _valid(text: str) -> str:
    """The text with U+FFFD for what is not valid Unicode (a lone surrogate, as in an undecodable file name)."""
    return "".join("�" if "\ud800" <= char <= "\udfff" else char for char in text)
