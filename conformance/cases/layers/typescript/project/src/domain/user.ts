// SPDX-License-Identifier: MIT

import type { Clock } from "../infra/clock.js";

export class User {
  constructor(readonly clock: Clock) {}
}
