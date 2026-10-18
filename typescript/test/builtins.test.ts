// SPDX-License-Identifier: MIT

import { expect, test } from "vitest";

import { builtinName } from "../src/scanner/builtins.js";

test("node: names and bare builtin names", () => {
  const none = new Set<string>();
  expect(builtinName("node:fs/promises", none)).toBe("fs");
  expect(builtinName("node:test", none)).toBe("test");
  expect(builtinName("fs", none)).toBe("fs");
  expect(builtinName("path/posix", none)).toBe("path");
  expect(builtinName("react", none)).toBeUndefined();
  expect(builtinName("test", none)).toBeUndefined();
});

test("a declared package wins over a bare builtin name, not over node:", () => {
  const declared = new Set(["events"]);
  expect(builtinName("events", declared)).toBeUndefined();
  expect(builtinName("node:events", declared)).toBe("events");
});
