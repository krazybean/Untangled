# SPDX-License-Identifier: GPL-2.0-only
"""Text helpers for names and paths read from source code and the filesystem."""

import os


def utf8(raw: bytes) -> str:
    """Decodes UTF-8, or else Windows-1252, the encoding legacy code was almost always
    written in (spec/pairs-format.md). The five bytes Windows-1252 leaves undefined are
    read as Latin-1, so nothing is replaced or rejected."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return "".join(_windows_1252(byte) for byte in raw)


def path_text(path: str) -> str:
    """A file name as UTF-8 text. On POSIX, os functions hand back names that are not
    valid UTF-8 with surrogate escapes; this reads their bytes as utf8() does."""
    return utf8(os.fsencode(path))


def _windows_1252(byte: int) -> str:
    if byte < 0x80:
        return chr(byte)
    try:
        return bytes([byte]).decode("cp1252")
    except UnicodeDecodeError:
        return chr(byte)
