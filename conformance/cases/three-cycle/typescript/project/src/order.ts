// SPDX-License-Identifier: MIT

import type { Cart } from "./cart.js";
import { Customer } from "./customer.js";

export class Order {
  constructor(readonly cart: Cart) {}

  customer(): Customer {
    return Customer.current();
  }
}
