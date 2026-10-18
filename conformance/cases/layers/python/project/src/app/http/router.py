# SPDX-License-Identifier: MIT

from app.http.user_controller import UserController


class Router:
    def dispatch(self) -> None:
        UserController(self).show(1)
