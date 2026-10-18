// SPDX-License-Identifier: MIT

import type { User } from "./user.js";

export class Order {
  constructor(readonly customer: User) {}
}
