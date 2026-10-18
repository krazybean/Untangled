# SPDX-License-Identifier: GPL-2.0-only
"""The standard library's top-level module names (spec/languages/python.md, step 3)."""

import sys

# Modules removed from the standard library since Python 3.0, so code written for an
# older Python 3 is classified the same whichever Python runs the scanner.
REMOVED = frozenset(
    {
        # Python 3.12
        "asynchat", "asyncore", "distutils", "imp", "smtpd",
        # Python 3.13 (PEP 594)
        "aifc", "audioop", "cgi", "cgitb", "chunk", "crypt", "imghdr", "lib2to3", "mailcap",
        "msilib", "nis", "nntplib", "ossaudiodev", "pipes", "sndhdr", "spwd", "sunau",
        "telnetlib", "uu", "xdrlib",
        # Python 3.8 to 3.11
        "binhex", "formatter", "macpath", "parser", "symbol",
    }
)  # fmt: skip

MODULES = frozenset(sys.stdlib_module_names) | REMOVED


def is_stdlib(top_level: str) -> bool:
    return top_level in MODULES
