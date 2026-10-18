# SPDX-License-Identifier: GPL-2.0-only
import os

import pytest

from untangled.text import path_text, utf8


def test_utf8_is_kept() -> None:
    assert utf8("café €".encode()) == "café €"


def test_invalid_utf8_is_read_as_windows_1252() -> None:
    assert utf8(b"caf\xe9 \x80") == "café €"


def test_bytes_windows_1252_leaves_undefined_are_read_as_latin_1() -> None:
    assert utf8(b"\x81\x8d\x8f\x90\x9d\xff") == "\x81\x8d\x8f\x90\x9dÿ"


@pytest.mark.skipif(os.name == "nt", reason="POSIX file names are bytes")
def test_path_text_reads_surrogate_escaped_names() -> None:
    assert path_text(os.fsdecode(b"caf\xe9.py")) == "café.py"
    assert path_text("plain/name.py") == "plain/name.py"
