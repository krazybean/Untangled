// SPDX-License-Identifier: MIT

import { Cart } from "./cart.js";

export class Customer {
  static current(): Customer {
    return new Customer();
  }

  cart(): Cart {
    return new Cart();
  }
}
