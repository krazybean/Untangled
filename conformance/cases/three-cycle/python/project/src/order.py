# SPDX-License-Identifier: MIT

from cart import Cart
from customer import Customer


class Order:
    def __init__(self, cart: Cart) -> None:
        self.cart = cart

    def customer(self) -> Customer:
        return Customer.current()
