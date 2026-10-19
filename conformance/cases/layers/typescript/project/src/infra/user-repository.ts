// SPDX-License-Identifier: MIT

import type { Store } from "../cache/store.js";
import { User } from "../domain/user.js";
import type { Clock } from "./clock.js";

export class UserRepository {
  constructor(
    readonly clock: Clock,
    readonly cache: Store,
  ) {}

  find(id: number): User {
    return new User(this.clock);
  }
}
