# SPDX-License-Identifier: MIT

# `pricing` is a submodule, VERSION a name defined in shop/__init__.py.
from shop import VERSION, pricing


class Cart:
    version = VERSION

    def total(self) -> float:
        return pricing.total(self)
