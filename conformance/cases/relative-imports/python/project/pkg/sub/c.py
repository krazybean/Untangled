# SPDX-License-Identifier: MIT

from .. import b
from ..a import thing

# Three dots from pkg/sub/c.py go above the top-level package.
from ...outside import name
