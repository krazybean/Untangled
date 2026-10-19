// SPDX-License-Identifier: MIT
// Runs the shared cases in conformance/cases (see conformance/README.md): every case with a
// typescript/ folder, scanned with the --source paths in its typescript/sources file and the
// --aliases files in its typescript/aliases file, must produce its expected pairs document.
// analyze and report are not in this library yet, so their expected files are only required.

import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, test } from "vitest";

import { scan } from "../src/scanner/scanner.js";

const CASES = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "conformance", "cases");
const TYPESCRIPT_CASES = readdirSync(CASES)
  .filter((name) => existsSync(join(CASES, name, "typescript")))
  .sort();

function lines(file: string): string[] {
  return existsSync(file) ? readFileSync(file, "utf8").split(/\s+/).filter(Boolean) : [];
}

function scanCase(name: string): ReturnType<typeof scan> {
  const folder = join(CASES, name, "typescript");
  return scan(join(folder, "project"), {
    sources: lines(join(folder, "sources")),
    aliases: lines(join(folder, "aliases")).map((file) => join(folder, file)),
  });
}

function withoutGenerator(document: Record<string, unknown>): Record<string, unknown> {
  const { generator: _generator, ...rest } = document;
  return rest;
}

test("there are cases", () => {
  expect(TYPESCRIPT_CASES.length).toBeGreaterThanOrEqual(7);
});

describe.each(TYPESCRIPT_CASES)("%s", (name) => {
  const expected = join(CASES, name, "typescript", "expected");

  test("pairs", () => {
    const document = JSON.parse(readFileSync(join(expected, "pairs.json"), "utf8")) as Record<string, unknown>;
    expect(withoutGenerator(scanCase(name).pairs.toObject())).toEqual(withoutGenerator(document));
  });

  test("the expected pairs document is written as the spec asks", () => {
    const text = readFileSync(join(expected, "pairs.json"), "utf8");
    expect(scanCase(name).pairs.toJson().replace(/"generator": \{[^}]*\}/, "")).toBe(
      text.replace(/"generator": \{[^}]*\}/, ""),
    );
  });

  test("has an expected analysis", () => {
    expect(existsSync(join(expected, "analysis.json"))).toBe(true);
  });
});
