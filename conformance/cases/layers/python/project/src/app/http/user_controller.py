# SPDX-License-Identifier: MIT

from app.domain.order import Order
from app.http.router import Router
from app.infra.user_repository import UserRepository


class UserController:
    def __init__(self, router: Router) -> None:
        self.router = router

    def show(self, id: int, users: UserRepository | None = None) -> Order | None:
        return None
