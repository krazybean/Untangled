// SPDX-License-Identifier: MIT

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, test } from "vitest";

import { main } from "../src/cli.js";
import { Buffered, project } from "./helpers.js";

function run(...args: string[]): { code: number; out: string; err: string } {
  const out = new Buffered();
  const err = new Buffered();
  const code = main(args, out, err);
  return { code, out: out.text, err: err.text };
}

describe("scan", () => {
  test("writes the pairs document", () => {
    const root = project({ "a.ts": 'import "./b";', "b.ts": "" });
    const result = run("scan", root);
    expect(result.code).toBe(0);
    expect(JSON.parse(result.out)).toMatchObject({ format: "untangled-pairs", language: "typescript", edges: [{ from: "a.ts", to: "b.ts" }] });
    expect(result.err).toBe("");
  });

  test("snakefood format and --output", () => {
    const root = project({ "a.ts": 'import "./b";', "b.ts": "" });
    const output = join(root, "out.txt");
    expect(run("scan", root, "--format=snakefood", `--output=${output}`)).toEqual({ code: 0, out: "", err: "" });
    expect(readFileSync(output, "utf8")).toBe(`((${q(root)}, 'a.ts'), (${q(root)}, 'b.ts'))\n((${q(root)}, 'b.ts'), (None, None))\n`);
  });

  test("--dev, --source and --aliases, warnings on stderr", () => {
    const root = project({
      "a.ts": 'import "@/b"; import "./x.css";',
      "src/b.ts": "",
      "a.test.ts": "",
      "dist/c.js": "",
      "x.css": "",
      "aliases.json": '{ "@/*": ["src/*"] }',
    });
    const result = run("scan", root, "--dev", "--source=dist", `--aliases=${join(root, "aliases.json")}`);
    expect(result.code).toBe(0);
    const ids = (JSON.parse(result.out) as { nodes: { id: string }[] }).nodes.map((node) => node.id);
    expect(ids).toEqual(["a.test.ts", "a.ts", "dist/c.js", "src/b.ts"]);
    expect(result.err).toBe("warning: 1 import of non-code files gave no edge (.css 1)\n");
  });

  test("a missing folder fails with exit code 1", () => {
    const result = run("scan", join(project({}), "nope"));
    expect(result.code).toBe(1);
    expect(result.err).toMatch(/^error: .*nope is not a folder\n$/);
  });

  test("an unwritable output fails with exit code 1", () => {
    const root = project({ "a.ts": "" });
    expect(run("scan", root, `--output=${join(root, "no/such/folder/x.json")}`).code).toBe(1);
  });
});

describe("usage", () => {
  test("help and version", () => {
    expect(run("--help").out).toContain("Usage: untangled scan");
    expect(run("scan", "-h").code).toBe(0);
    expect(run("-V").out).toMatch(/^untangled-typescript \d+\.\d+\.\d+/);
  });

  test("errors exit with 2", () => {
    expect(run().code).toBe(2);
    expect(run("nope")).toMatchObject({ code: 2, err: expect.stringMatching(/^Unknown command: nope/) });
    expect(run("scan", "--venv=x")).toMatchObject({ code: 2, err: "Unknown option for scan: --venv\n" });
    expect(run("scan", "--dev=1")).toMatchObject({ code: 2, err: "Option --dev takes no value\n" });
    expect(run("scan", "--output")).toMatchObject({ code: 2, err: "Option --output needs a value, as in --output=...\n" });
    expect(run("scan", "--format=html")).toMatchObject({ code: 2, err: "Unknown format: html\n" });
  });

  test("analyze and report are not here yet", () => {
    for (const command of ["analyze", "report"]) {
      const result = run(command, ".");
      expect(result.code).toBe(2);
      expect(result.err).toContain(`untangled ${command} is not in the TypeScript library yet`);
    }
  });
});

function q(text: string): string {
  return `'${text.replaceAll("\\", "\\\\").replaceAll("'", "\\'")}'`;
}
