# SPDX-License-Identifier: GPL-2.0-only
"""The standard library's top-level module names (spec/languages/python.md, step 3)."""

import sys

# Modules removed from the standard library since Python 3.0, so code written for an
# older Python 3 is classified the same whichever Python runs the scanner.
REMOVED = frozenset(
    {
        # Python 3.14
        "_compression",
        # Python 3.13 (PEP 594)
        "aifc", "audioop", "cgi", "cgitb", "chunk", "crypt", "imghdr", "lib2to3", "mailcap",
        "msilib", "nis", "nntplib", "ossaudiodev", "pipes", "sndhdr", "spwd", "sunau",
        "telnetlib", "uu", "xdrlib", "_crypt", "_msi",
        # Python 3.12
        "asynchat", "asyncore", "distutils", "imp", "smtpd", "_bootsubprocess", "_sha256", "_sha512",
        # Python 3.8 to 3.11
        "binhex", "formatter", "macpath", "parser", "symbol",
    }
)  # fmt: skip

# Modules added to the standard library since Python 3.11, the oldest Python that runs
# the scanner, so code written for a newer Python is classified the same too.
ADDED = frozenset(
    {
        # Python 3.12
        "_pydatetime", "_pylong", "_sha2",
        # Python 3.13
        "_android_support", "_apple_support", "_colorize", "_interpchannels", "_interpqueues",
        "_interpreters", "_ios_support", "_opcode_metadata", "_pyrepl", "_suggestions", "_sysconfig",
        "_wmi",
        # Python 3.14
        "annotationlib", "compression", "_ast_unparse", "_hmac", "_py_warnings", "_remote_debugging",
        "_types", "_zstd",
    }
)  # fmt: skip

MODULES = frozenset(sys.stdlib_module_names) | REMOVED | ADDED


def is_stdlib(top_level: str) -> bool:
    return top_level in MODULES
