// SPDX-License-Identifier: MIT

import { expect, test } from "vitest";

import { parseJsonc } from "../src/scanner/jsonc.js";

test("allows comments and trailing commas", () => {
  expect(parseJsonc('// a\n{ /* b */ "x": [1, 2,], "y": { "z": 3, }, }')).toEqual({ x: [1, 2], y: { z: 3 } });
});

test("keeps comment-like text and commas inside strings", () => {
  expect(parseJsonc('{ "url": "http://x/*y*/", "s": ",}" }')).toEqual({ url: "http://x/*y*/", s: ",}" });
  expect(parseJsonc('{ "q": "a\\"//b" }')).toEqual({ q: 'a"//b' });
});

test("throws on invalid JSON", () => {
  expect(() => parseJsonc("{ x: 1 }")).toThrow();
});
