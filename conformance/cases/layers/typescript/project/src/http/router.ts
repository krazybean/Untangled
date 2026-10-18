// SPDX-License-Identifier: MIT

import { UserController } from "./user-controller.js";

export class Router {
  dispatch(): void {
    new UserController(this).show(1);
  }
}
