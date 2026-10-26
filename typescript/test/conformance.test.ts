// SPDX-License-Identifier: MIT
// Runs the shared cases in conformance/cases (see conformance/README.md): every case with a
// typescript/ folder, scanned with the --source paths in its typescript/sources file and the
// --aliases files in its typescript/aliases file, must produce its expected pairs document, every
// expected analysis[.<strategy>].json, and every expected graph[.<strategy>].dot byte for byte.

import { existsSync, mkdtempSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, test } from "vitest";

import { analyze } from "../src/analysis/analyzer.js";
import { Clustering } from "../src/analysis/clustering.js";
import { Filter } from "../src/analysis/filter.js";
import { main } from "../src/cli.js";
import { encode, PairsDocument } from "../src/graph.js";
import { renderDot } from "../src/report/dot.js";
import { Report } from "../src/report/report.js";
import { scan } from "../src/scanner/scanner.js";
import { Buffered } from "./helpers.js";

const CASES = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "conformance", "cases");
const TYPESCRIPT_CASES = readdirSync(CASES)
  .filter((name) => existsSync(join(CASES, name, "typescript")))
  .sort();

/** The non-empty lines of an optional file: one value per line, so a value may hold spaces. */
function lines(file: string): string[] {
  return existsSync(file) ? readFileSync(file, "utf8").split(/\r?\n/).filter(Boolean) : [];
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
  return comparable(rest) as Record<string, unknown>;
}

/** Equality as the spec defines it for conformance: numbers compare to 4 decimal places. */
function comparable(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(comparable);
  }
  if (typeof value === "object" && value !== null) {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, comparable(item)]));
  }
  return typeof value === "number" ? Math.round(value * 10000) / 10000 : value;
}

/** The clustering an expected file's suffix names: "" (none), ".rules", or ".namespace-2" and the like. */
function clustering(name: string, suffix: string): Clustering | undefined {
  if (suffix === "") {
    return undefined;
  }
  if (suffix === ".rules") {
    return Clustering.parseRules(readFileSync(join(CASES, name, "typescript", "clusters.rules"), "utf8"));
  }
  return Clustering.fromString(suffix.slice(1).replace(/-(?=[0-9]+$)/, ":"));
}

function expectedFiles(name: string, pattern: RegExp): [string, string][] {
  const folder = join(CASES, name, "typescript", "expected");
  return readdirSync(folder)
    .sort()
    .flatMap((file) => {
      const match = pattern.exec(file);
      return match ? [[file, match[1]!] as [string, string]] : [];
    });
}

test("lines keeps spaces and drops empty lines", () => {
  const file = join(mkdtempSync(join(tmpdir(), "untangled-lines-")), "args");
  writeFileSync(file, "--include=docs/a b/**\n\nsrc/My Folder/A.php\r\n");
  expect(lines(file)).toEqual(["--include=docs/a b/**", "src/My Folder/A.php"]);
  expect(lines(`${file}.missing`)).toEqual([]);
});

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

  for (const [file, suffix] of expectedFiles(name, /^analysis(.*)\.json$/)) {
    test(file, () => {
      const analysis = analyze(new Filter().apply(scanCase(name).pairs), clustering(name, suffix));
      // The generator names this library's version, which the expected files do not pin.
      const generator = /\n {2}"generator": \{[^}]*\},/;
      expect(encode(analysis).replace(generator, "")).toBe(readFileSync(join(expected, file), "utf8").replace(generator, ""));
    });
  }

  for (const [file, suffix] of expectedFiles(name, /^graph(.*)\.dot$/)) {
    test(file, () => {
      const report = Report.build(name, new Filter().apply(scanCase(name).pairs), clustering(name, suffix));
      expect(renderDot(report)).toBe(readFileSync(join(expected, file), "utf8"));
    });
  }

  // `dependents` on the expected pairs document with the arguments, one per line, of
  // `dependents.<name>.args`. A .json expectation is compared as a document, a .txt one byte for byte.
  for (const [file] of expectedFiles(name, /^(dependents\..*\.(?:json|txt))$/)) {
    test(file, () => {
      const args = lines(join(CASES, name, "typescript", `${file.replace(/\.(json|txt)$/, "")}.args`));
      const out = new Buffered();
      const err = new Buffered();
      expect(main(["dependents", join(expected, "pairs.json"), ...args], out, err), err.text).toBe(0);
      const want = readFileSync(join(expected, file), "utf8");
      if (file.endsWith(".json")) {
        expect(withoutGenerator(JSON.parse(out.text) as Record<string, unknown>)).toEqual(withoutGenerator(JSON.parse(want) as Record<string, unknown>));
        expect(out.text.endsWith("}\n")).toBe(true);
      } else {
        expect(out.text).toBe(want);
      }
    });
  }
});

// The analyses and graphs of every other library's cases, from their pairs documents: analyze
// and report must not depend on which library scanned the project.
const OTHER_CASES = readdirSync(CASES)
  .flatMap((name) => ["php", "python"].map((language) => [name, language] as [string, string]))
  .filter(([name, language]) => existsSync(join(CASES, name, language, "expected", "pairs.json")))
  .sort();

describe.each(OTHER_CASES)("%s/%s pairs document", (name, language) => {
  const folder = join(CASES, name, language);
  const pairs = (): PairsDocument => PairsDocument.fromObject(JSON.parse(readFileSync(join(folder, "expected", "pairs.json"), "utf8")));
  const strategy = (suffix: string): Clustering | undefined =>
    suffix === ".rules"
      ? Clustering.parseRules(readFileSync(join(folder, "clusters.rules"), "utf8"))
      : suffix === ""
        ? undefined
        : Clustering.fromString(suffix.slice(1).replace(/-(?=[0-9]+$)/, ":"));
  const files = (pattern: RegExp): [string, string][] =>
    readdirSync(join(folder, "expected"))
      .sort()
      .flatMap((file) => {
        const match = pattern.exec(file);
        return match ? [[file, match[1]!] as [string, string]] : [];
      });

  for (const [file, suffix] of files(/^analysis(.*)\.json$/)) {
    test(file, () => {
      const expected = readFileSync(join(folder, "expected", file), "utf8");
      const actual = encode(analyze(new Filter().apply(pairs()), strategy(suffix)));
      const generator = /\n {2}"generator": \{[^}]*\},/;
      expect(actual.replace(generator, "")).toBe(expected.replace(generator, ""));
    });
  }

  for (const [file, suffix] of files(/^graph(.*)\.dot$/)) {
    test(file, () => {
      const report = Report.build(name, new Filter().apply(pairs()), strategy(suffix));
      expect(renderDot(report)).toBe(readFileSync(join(folder, "expected", file), "utf8"));
    });
  }
});
