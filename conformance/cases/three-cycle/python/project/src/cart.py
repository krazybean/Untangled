# SPDX-License-Identifier: MIT

from order import Order


class Cart:
    def checkout(self) -> Order:
        return Order(self)
