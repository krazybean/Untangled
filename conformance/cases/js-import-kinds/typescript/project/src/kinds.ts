// SPDX-License-Identifier: MIT

import a from "./a";
import "./b";
import * as c from "./c";
// Type-only: the whole statement, or every name in it.
import type { Value } from "./d";
import { type Value as V2, type Value as V3 } from "./e";
// One name is a value, so this is a plain import.
import { type Value as V4, value as f } from "./f";
export { value as g } from "./g";
export * from "./h";
export type { Value as HValue } from "./i";
import j = require("./j");
// typeof import() is a type-level import.
type K = typeof import("./k");

const lazy = import("./a");
const pick = (name: string) => import(`./plugins/${name}`);
const fixed = import(`./plugins/en`);
const name = "./c";
const loaded = require(name);
// Not a call of require or import: no reference.
const text = "require('./b')";

export { a, c, f, j, lazy, pick, fixed, loaded, text };
export type { Value, V2, V3, V4, K };
