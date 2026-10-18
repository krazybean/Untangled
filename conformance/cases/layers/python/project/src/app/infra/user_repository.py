# SPDX-License-Identifier: MIT

from app.cache.store import Store
from app.domain.user import User
from app.infra.clock import Clock


class UserRepository:
    def __init__(self, clock: Clock, cache: Store) -> None:
        self.clock = clock
        self.cache = cache

    def find(self, id: int) -> User:
        return User(self.clock)
