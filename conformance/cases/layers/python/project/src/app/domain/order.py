# SPDX-License-Identifier: MIT

from app.domain.user import User


class Order:
    def __init__(self, customer: User) -> None:
        self.customer = customer
