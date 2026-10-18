# SPDX-License-Identifier: MIT

from cart import Cart


class Customer:
    @classmethod
    def current(cls) -> "Customer":
        return cls()

    def cart(self) -> Cart:
        return Cart()
