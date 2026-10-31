// SPDX-License-Identifier: MIT
// A file that cannot be read is file-unreadable. The read is made to fail by replacing readFileSync for one
// file name, so that the test does not depend on file permissions, which differ between platforms and for
// privileged users.

import { describe, expect, test, vi } from "vitest";

vi.mock("node:fs", async (importOriginal) => {
  const actual = await importOriginal<typeof import("node:fs")>();
  const readFileSync = ((path: Parameters<typeof actual.readFileSync>[0], ...rest: unknown[]) => {
    // The scanner passes the path as a Buffer.
    if (String(path).endsWith("locked.ts")) {
      throw Object.assign(new Error("EACCES: permission denied"), { code: "EACCES" });
    }
    return (actual.readFileSync as (...args: unknown[]) => unknown)(path, ...rest);
  }) as typeof actual.readFileSync;
  return { ...actual, readFileSync, default: { ...actual, readFileSync } };
});

import { scan } from "../src/scanner/scanner.js";
import { project } from "./helpers.js";

describe("a file that cannot be read", () => {
  test("is reported as file-unreadable, and stays in the pairs document", () => {
    const result = scan(project({ "a.ts": 'import "./b";', "b.ts": "export {};", "locked.ts": "export const x = 1;" }));
    expect(result.diagnostics.map((item) => [item.level, item.code, item.files])).toEqual([["warning", "file-unreadable", ["locked.ts"]]]);
    expect(result.diagnostics[0]!.message).toMatch(/^locked\.ts: cannot read it/);
    expect(result.warnings).toEqual([result.diagnostics[0]!.message]);
    expect(result.pairs.node("locked.ts")).toMatchObject({ error: "read" });
  });
});
