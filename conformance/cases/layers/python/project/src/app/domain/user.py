# SPDX-License-Identifier: MIT

from app.infra.clock import Clock


class User:
    def __init__(self, clock: Clock) -> None:
        self.clock = clock
