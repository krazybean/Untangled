// SPDX-License-Identifier: MIT

import { describe, expect, test } from "vitest";

import { collapse, compareText, decode, sortText } from "../src/text.js";

describe("decode", () => {
  test("reads UTF-8 and drops a BOM", () => {
    expect(decode(new Uint8Array([0xef, 0xbb, 0xbf, 0x63, 0x61, 0x66, 0xc3, 0xa9]))).toBe("café");
  });

  test("reads invalid UTF-8 as Windows-1252", () => {
    expect(decode(new Uint8Array([0x63, 0x61, 0x66, 0xe9, 0x80]))).toBe("café€");
  });
});

describe("compareText", () => {
  test("orders by code point, as UTF-8 bytes do", () => {
    // U+FF5E sorts before U+1F600, though its UTF-16 code unit is larger than a surrogate's.
    expect(sortText(["😀", "～", "a", "B", "é"])).toEqual(["B", "a", "é", "～", "😀"]);
    expect(compareText("a", "a")).toBe(0);
    expect(compareText("a", "ab")).toBeLessThan(0);
  });
});

test("collapse turns runs of whitespace into one space", () => {
  expect(collapse("  a\n\t  b  ")).toBe("a b");
});
