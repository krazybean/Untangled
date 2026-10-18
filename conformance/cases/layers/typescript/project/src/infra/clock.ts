// SPDX-License-Identifier: MIT

import { performance } from "node:perf_hooks";

export class Clock {
  now(): number {
    return performance.now();
  }
}
