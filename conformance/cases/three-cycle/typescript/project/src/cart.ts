// SPDX-License-Identifier: MIT

import { Order } from "./order.js";

export class Cart {
  checkout(): Order {
    return new Order(this);
  }
}
