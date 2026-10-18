# SPDX-License-Identifier: MIT

"""Syntax from Python 3.12 to 3.14, which an older Python cannot parse as a whole. Its
imports are the same on every Python: older ones read it statement by statement."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.types import Payload

type Alias = list[int]  # Python 3.12


class Box[T]:  # Python 3.12
    def label(self, item: T) -> str:
        from app import format

        return f"{format.name(item)["short"]}"  # Python 3.12 f-string

    def load(self, text: str) -> object:
        try:
            import app.fast as parser
        except ImportError, ModuleNotFoundError:  # Python 3.14
            parser = json
        return parser.loads(text)
