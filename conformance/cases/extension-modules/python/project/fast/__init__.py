# SPDX-License-Identifier: MIT

# Cython source next to its stub: the stub wins, and neither is scanned.
from fast import _speedups

# Only a compiled extension.
from fast._native import checksum

# A .py module wins over its stub.
from fast.helpers import helper

# Only a stub, as for a C extension built from a .c file.
import fast._ctypes_only

# Nothing at all: unresolved.
import fast._not_built
