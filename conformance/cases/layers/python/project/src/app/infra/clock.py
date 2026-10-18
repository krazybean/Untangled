# SPDX-License-Identifier: MIT

from datetime import datetime


class Clock:
    def now(self) -> datetime:
        return datetime.now()
