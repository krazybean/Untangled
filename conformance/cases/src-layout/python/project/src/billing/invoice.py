# SPDX-License-Identifier: MIT

# vendored/ is under lib/, an import root through pyproject.toml.
from vendored.helper import money


class Invoice:
    total = money(0)
