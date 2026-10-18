# SPDX-License-Identifier: GPL-2.0-only
import textwrap
from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def project(tmp_path: Path) -> Callable[[dict[str, str | bytes]], str]:
    """Writes a project from {relative path: content} and returns its folder. Text is dedented."""

    def make(files: dict[str, str | bytes]) -> str:
        for name, content in files.items():
            path = tmp_path / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")
        return str(tmp_path)

    return make
