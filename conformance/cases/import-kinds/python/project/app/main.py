# SPDX-License-Identifier: MIT

import importlib
import typing
from importlib import import_module as load
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import Model

if typing.TYPE_CHECKING:
    from app.plugins import sheet

try:
    import ujson as json
except ImportError:
    import json


class Exporter:
    # A class body runs at import time, so this import is not local.
    from app.plugins import pdf

    def run(self, name: str) -> None:
        import app.models

        importlib.import_module("app.plugins.pdf")
        load(".plugins.sheet", "app")
        load(name)
        __import__("app.models")
        importlib.import_module(f"app.plugins.{name}")
