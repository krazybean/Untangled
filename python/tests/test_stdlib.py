# SPDX-License-Identifier: GPL-2.0-only
from untangled.scanner.stdlib import is_stdlib


def test_the_standard_library_is_the_same_on_every_python() -> None:
    # Added in Python 3.14, removed in 3.12 and 3.13: builtins whichever Python runs the scanner.
    for name in ("os", "annotationlib", "compression", "distutils", "imp", "cgi", "telnetlib"):
        assert is_stdlib(name), name
    assert not is_stdlib("yaml")
