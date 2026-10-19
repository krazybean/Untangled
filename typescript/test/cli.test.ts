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

  test("analyze and report options", () => {
    expect(run("report", "--format=json")).toMatchObject({ code: 2, err: "Unknown format: json\n" });
    expect(run("report", "--format=dot", "--style=fancy")).toMatchObject({ code: 2, err: "Unknown style: fancy\n" });
    expect(run("report", "--style=classic")).toMatchObject({ code: 2, err: "--style only applies to --format=dot\n" });
    expect(run("analyze", "--cluster=module:1")).toMatchObject({ code: 2, err: expect.stringMatching(/^error: unknown clustering/) });
    expect(run("analyze", "--format=dot")).toMatchObject({ code: 2, err: "Unknown option for analyze: --format\n" });
    expect(run("analyze", "--cluster=rules:/no/such/file")).toMatchObject({ code: 1, err: "error: cannot read rules file /no/such/file\n" });
  });
});

describe("analyze", () => {
  const files = { "package.json": '{ "name": "shop" }', "src/a.ts": 'import "./b"; import "../lib/c";', "src/b.ts": 'import "./a";', "lib/c.ts": 'import "fs";' };

  test("scans a project and writes the analysis", () => {
    const result = run("analyze", project(files));
    expect(result.code).toBe(0);
    const analysis = JSON.parse(result.out) as { summary: { units: number; cycles: number }; clustering: null };
    expect(analysis.summary).toMatchObject({ units: 3, cycles: 1 });
    expect(result.out.endsWith("\n")).toBe(true);
  });

  test("reads a saved pairs document, with clustering and filters", () => {
    const root = project(files);
    run("scan", root, `--output=${join(root, "pairs.json")}`);
    const result = run("analyze", join(root, "pairs.json"), "--cluster=folder:1", "--exclude=lib/**");
    const analysis = JSON.parse(result.out) as { clustering: string; units: { id: string }[] };
    expect(analysis.clustering).toBe("folder:1");
    expect(analysis.units.map((unit) => unit.id)).toEqual(["src"]);
  });

  test("rules files", () => {
    const root = project({ ...files, "rules.txt": "src/ App\n" });
    const analysis = JSON.parse(run("analyze", root, `--cluster=rules:${join(root, "rules.txt")}`).out) as { units: { id: string }[] };
    expect(analysis.units.map((unit) => unit.id)).toEqual(["App", "lib/c.ts"]);
  });

  test("bad pairs documents fail with exit code 1", () => {
    const root = project({ "bad.json": "{", "other.json": '{ "format": "x" }', "clustered.json": JSON.stringify({ format: "untangled-pairs", version: "0.1", language: "php", nodes: [{ id: "a", kind: "cluster" }], edges: [] }) });
    expect(run("analyze", join(root, "bad.json"))).toMatchObject({ code: 1, err: expect.stringMatching(/^error: .*bad\.json is not valid JSON/) });
    expect(run("analyze", join(root, "other.json"))).toMatchObject({ code: 1, err: expect.stringMatching(/^error: not an Untangled pairs document/) });
    expect(run("analyze", join(root, "clustered.json"))).toMatchObject({ code: 1, err: expect.stringMatching(/^error: the pairs document is already clustered/) });
  });
});

describe("report", () => {
  test("HTML with the package.json name as title, or --title", () => {
    const root = project({ "package.json": '{ "name": "shop" }', "a.ts": 'import "./b";', "b.ts": "" });
    expect(run("report", root).out).toContain("<title>Dependencies: shop</title>");
    expect(run("report", root, "--title=Mine").out).toContain("<title>Dependencies: Mine</title>");
    const bare = project({ "a.ts": "" });
    expect(run("report", bare).out).toContain(`<title>Dependencies: ${bare.split("/").at(-1)!}</title>`);
  });

  test("DOT, default and classic", () => {
    const root = project({ "a.ts": 'import "./b"; import "react";', "b.ts": "", "package.json": '{ "dependencies": { "react": "1" } }' });
    expect(run("report", root, "--format=dot").out).toContain('  "a.ts" -> "b.ts";\n');
    expect(run("report", root, "--format=dot", "--style=classic").out).toContain('  "npm:react" [fillcolor=white];\n');
  });
});

function q(text: string): string {
  return `'${text.replaceAll("\\", "\\\\").replaceAll("'", "\\'")}'`;
}
