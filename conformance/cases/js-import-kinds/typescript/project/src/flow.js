// SPDX-License-Identifier: MIT
// @flow
import type { Value } from "./d";
import { value } from "./b";

export function show(item: Value): string {
  return item + value;
}
