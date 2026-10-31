// SPDX-License-Identifier: MIT
// Structured diagnostics (spec/diagnostics.md): the value, the scanner's codes and `--diagnostics=json`.

import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, test } from "vitest";

import { main } from "../src/cli.js";
import { diagnosticText, encodeDiagnostic, errorDiagnostic, warningDiagnostic, type Diagnostic } from "../src/diagnostics.js";
import { PairsDocument } from "../src/graph.js";
import { scan, type ScanOptions } from "../src/scanner/scanner.js";
import { Buffered, project } from "./helpers.js";

const LAYERS = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "conformance", "cases", "layers", "typescript");
const PAIRS = join(LAYERS, "expected", "pairs.json");

function run(...args: string[]): { code: number; out: string; err: string } {
  const out = new Buffered();
  const err = new Buffered();
  const code = main(args, out, err);
  return { code, out: out.text, err: err.text };
}

const parsed = (err: string): Diagnostic[] => err.trimEnd().split("\n").map((line) => JSON.parse(line) as Diagnostic);

describe("the value", () => {
  test("the fields are written in the specified order", () => {
    const diagnostic = warningDiagnostic("uncovered-files", "three files", ["a.ts", "b/c.ts"]);
    expect(encodeDiagnostic(diagnostic)).toBe('{"level":"warning","code":"uncovered-files","message":"three files","files":["a.ts","b/c.ts"]}');
    expect(Object.keys(JSON.parse(encodeDiagnostic(diagnostic)) as object)).toEqual(["level", "code", "message", "files"]);
  });

  test("no files means no files field", () => {
    const diagnostic = errorDiagnostic("project-unreadable", "not a folder");
    expect(encodeDiagnostic(diagnostic)).toBe('{"level":"error","code":"project-unreadable","message":"not a folder"}');
    expect(diagnosticText(diagnostic)).toBe("error: not a folder");
    expect(diagnosticText(warningDiagnostic("c-d", "x"))).toBe("warning: x");
  });

  test("a special message stays one valid line", () => {
    const message = 'quote " backslash \\ newline \n tab \t cr \r nul \0 unit \x1f slash / unicode é 漢 😀 separator  ';
    const files = ['dir/na"me\n.ts', "ünï/ç.ts"];
    const text = encodeDiagnostic(warningDiagnostic("some-code", message, files));
    expect(text).not.toMatch(/[\n\r]/);
    const decoded = JSON.parse(text) as Diagnostic;
    expect(decoded.message).toBe(message);
    expect(decoded.files).toEqual(files);
    // Slashes and non-ASCII are written as they are; control characters are escaped in lower-case hex.
    expect(text).toContain("slash / unicode é 漢 😀");
    expect(text).toContain("\\u001f");
    expect(text).toContain("\\u0000");
  });

  test("text that is not valid Unicode is written with the replacement character", () => {
    const decoded = JSON.parse(encodeDiagnostic(warningDiagnostic("some-code", "bad \udcff byte", ["na\udcffme.ts"]))) as Diagnostic;
    expect(decoded.message).toBe("bad � byte");
    expect(decoded.files).toEqual(["na�me.ts"]);
  });
});

describe("the scanner", () => {
  const scanned = (files: Record<string, string>, options: ScanOptions = {}): [string, string, string[]][] => {
    const result = scan(project(files), options);
    // The older warnings are the messages of the warning diagnostics, in order.
    expect(result.warnings).toEqual(result.diagnostics.filter((item) => item.level === "warning").map((item) => item.message));
    return result.diagnostics.map((item) => [item.level, item.code, item.files ?? []]);
  };

  test("a clean scan has none", () => {
    expect(scanned({ "a.ts": "export const x = 1;" })).toEqual([]);
  });

  test("a file that does not parse, and one that parses with errors", () => {
    expect(scanned({ "a.ts": "export const x = 1;", "bad.ts": "import ;;; (((" })).toEqual([["warning", "file-unparseable", ["bad.ts"]]]);
    expect(scanned({ "twice.ts": "let a = 1; let a = 2; import './x';" })).toEqual([["warning", "file-partially-parsed", ["twice.ts"]]]);
  });

  test("sources that do not exist or leave the project", () => {
    expect(scanned({ "a.ts": "" }, { sources: ["./nope/deeper/", "../outside"] })).toEqual([
      ["warning", "source-not-found", ["nope/deeper"]],
      ["warning", "source-outside-project", []],
    ]);
  });

  test("nothing to scan", () => {
    expect(scanned({ "README.md": "" })).toEqual([["warning", "nothing-scanned", []]]);
  });

  test("a configuration file that cannot be read, and an aliases file that is ignored", () => {
    expect(scanned({ "tsconfig.json": "{ nope", "a.ts": "" })).toEqual([["warning", "config-unreadable", ["tsconfig.json"]]]);
    expect(scanned({ "a.ts": "" }, { aliases: [join(project({}), "missing.json")] })).toEqual([["warning", "aliases-ignored", []]]);
  });

  test("build output, non-code imports, and packages that cannot be listed", () => {
    expect(scanned({ "a.ts": "export {}", "dist/a.js": "", "out/b.js": "" })).toEqual([["warning", "build-output-skipped", ["dist"]]]);
    expect(scanned({ "a.ts": 'import "./s.css";', "s.css": "" })).toEqual([["warning", "non-code-imports", []]]);
    expect(scanned({ "a.ts": 'import "react";' })).toEqual([["warning", "package-list-missing", []]]);
  });

  test("several diagnostics keep the order of the scan", () => {
    expect(scanned({ "bad.ts": "import ;;; (((", "tsconfig.json": "{ nope" }, { sources: ["nope"] })).toEqual([
      ["warning", "config-unreadable", ["tsconfig.json"]],
      ["warning", "source-not-found", ["nope"]],
      ["warning", "file-unparseable", ["bad.ts"]],
    ]);
  });

  test("the version of a pairs document", () => {
    const warnings: string[] = [];
    const diagnostics: Diagnostic[] = [];
    PairsDocument.fromObject({ format: "untangled-pairs", version: "0.99", language: "typescript", nodes: [], edges: [] }, warnings, diagnostics);
    expect(diagnostics.map((item) => [item.level, item.code])).toEqual([["warning", "document-version"]]);
    expect(warnings).toEqual([diagnostics[0]!.message]);
  });
});

describe("the command line", () => {
  const messy = (): string => project({ "a.ts": "export const x = 1;", "bad.ts": "import ;;; (((", "tsconfig.json": "{ nope" });

  test("text is the default and json says the same thing", () => {
    const root = messy();
    const text = run("scan", root);
    const json = run("scan", root, "--diagnostics=json");
    expect([text.code, json.code]).toEqual([0, 0]);
    expect(json.out).toBe(text.out);
    expect(run("scan", root, "--diagnostics=text").err).toBe(text.err);
    const textLines = text.err.trimEnd().split("\n");
    const lines = parsed(json.err);
    expect(lines.map((item) => `${item.level}: ${item.message}`)).toEqual(textLines);
    expect(lines.map((item) => [item.level, item.code, item.files])).toEqual([
      ["warning", "config-unreadable", ["tsconfig.json"]],
      ["warning", "file-unparseable", ["bad.ts"]],
    ]);
    expect(textLines[1]).toMatch(/^warning: bad\.ts: cannot parse/);
  });

  test("the lines are the same every time", () => {
    const root = messy();
    expect(run("scan", root, "--diagnostics=json")).toEqual(run("scan", root, "--diagnostics=json"));
  });

  test("no diagnostics means nothing on standard error", () => {
    for (const format of ["text", "json"]) {
      const result = run("scan", join(LAYERS, "project"), `--diagnostics=${format}`);
      expect(result.code).toBe(0);
      expect(result.out).not.toBe("");
      expect(result.err).toBe("");
    }
  });

  test("every command takes the option", () => {
    for (const args of [["scan", join(LAYERS, "project")], ["analyze", PAIRS], ["report", PAIRS], ["dependents", PAIRS, "src/domain/user.ts"]]) {
      const result = run(...args, "--diagnostics=json");
      expect(result.code, args.join(" ")).toBe(0);
      expect(result.out).not.toBe("");
      expect(result.err).toBe("");
    }
  });

  test("an unknown format is a usage error", () => {
    for (const format of ["github", "xml", ""]) {
      expect(run("scan", join(LAYERS, "project"), `--diagnostics=${format}`)).toEqual({
        code: 2,
        out: "",
        err: `Unknown diagnostics format: ${format} (use text or json)\n`,
      });
    }
    expect(run("scan", join(LAYERS, "project"), "--diagnostics")).toMatchObject({ code: 2, err: expect.stringContaining("Option --diagnostics needs a value") });
  });

  test("usage errors stay text in json mode", () => {
    expect(run("scan", ".", "--nope", "--diagnostics=json")).toEqual({ code: 2, out: "", err: "Unknown option for scan: --nope\n" });
  });

  test("unmatched rules are a warning, or with --strict an error", () => {
    const root = project({ "rules": "src/domain/ Core\n" });
    const rules = `--cluster=rules:${join(root, "rules")}`;
    const warned = run("analyze", PAIRS, rules, "--diagnostics=json");
    expect(warned.code).toBe(0);
    expect(warned.out).not.toBe("");
    const [line] = parsed(warned.err) as [Diagnostic];
    expect([line.level, line.code]).toEqual(["warning", "unmatched-rules"]);
    expect(line.files).toEqual(["bootstrap.ts", "src/http/router.ts", "src/http/user-controller.ts", "src/infra/clock.ts", "src/infra/user-repository.ts"]);
    expect(run("analyze", PAIRS, rules).err).toBe(`warning: ${line.message}\n`);

    const strict = run("analyze", PAIRS, rules, "--strict", "--diagnostics=json");
    expect([strict.code, strict.out]).toEqual([1, ""]);
    expect(parsed(strict.err)).toEqual([{ level: "error", code: "unmatched-rules", message: line.message, files: line.files }]);
    expect(run("analyze", PAIRS, rules, "--strict").err).toBe(`error: ${line.message}\n`);
  });

  test("the pairs document version is a diagnostic", () => {
    const data = JSON.parse(readFileSync(PAIRS, "utf8")) as { version: string };
    data.version = "0.99";
    const root = project({});
    writeFileSync(join(root, "pairs.json"), JSON.stringify(data));
    const result = run("analyze", join(root, "pairs.json"), "--diagnostics=json");
    expect(result.code).toBe(0);
    expect(parsed(result.err).map((item) => [item.level, item.code])).toEqual([["warning", "document-version"]]);
  });

  const failures: [string, string[], string][] = [
    ["project", ["scan", "/no/such/folder"], "project-unreadable"],
    ["project, for analyze", ["analyze", "/no/such/folder"], "project-unreadable"],
    ["rules file", ["analyze", PAIRS, "--cluster=rules:/no/such/rules"], "rules-file-unreadable"],
    ["target", ["dependents", PAIRS, "src/nope.ts"], "target-not-found"],
    ["target outside", ["dependents", join(LAYERS, "project"), "/no/such/src/domain/user.ts"], "target-outside-project"],
    ["output", ["scan", join(LAYERS, "project"), "--output=/no/such/folder/pairs.json"], "output-unwritable"],
  ];
  test.each(failures)("a failure is the last diagnostic and an error: %s", (_name, args, code) => {
    const result = run(...args, "--diagnostics=json");
    expect([result.code, result.out]).toEqual([1, ""]);
    const last = parsed(result.err).at(-1)!;
    expect([last.level, last.code]).toEqual(["error", code]);
    // Text mode says the same, as before.
    expect(run(...args)).toEqual({ code: 1, out: "", err: `error: ${last.message}\n` });
  });

  test("documents that cannot be used", () => {
    const clustered = { format: "untangled-pairs", version: "0.1", language: "typescript", nodes: [{ id: "a", kind: "cluster" }], edges: [] };
    const root = project({ "bad.json": "{nope", "list.json": "[]", "clustered.json": JSON.stringify(clustered) });
    for (const name of ["bad.json", "list.json"]) {
      const result = run("analyze", join(root, name), "--diagnostics=json");
      expect(result.code).toBe(1);
      expect([parsed(result.err)[0]!.level, parsed(result.err)[0]!.code]).toEqual(["error", "document-invalid"]);
    }
    expect(parsed(run("analyze", join(root, "clustered.json"), "--diagnostics=json").err)[0]!.code).toBe("document-clustered");
    expect(parsed(run("dependents", join(root, "clustered.json"), "a", "--diagnostics=json").err)[0]!.code).toBe("document-clustered");
  });
});
