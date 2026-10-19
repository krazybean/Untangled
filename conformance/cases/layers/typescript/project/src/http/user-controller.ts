// SPDX-License-Identifier: MIT

import type { Order } from "../domain/order.js";
import type { Router } from "./router.js";
import type { UserRepository } from "../infra/user-repository.js";

export class UserController {
  constructor(readonly router: Router) {}

  show(id: number, users?: UserRepository): Order | undefined {
    return undefined;
  }
}
