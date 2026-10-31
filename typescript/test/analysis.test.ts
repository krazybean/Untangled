// SPDX-License-Identifier: MIT

import { describe, expect, test } from "vitest";

import { AnalysisError, analyze, type Unit } from "../src/analysis/analyzer.js";
import { Clustering, describeUnmatched } from "../src/analysis/clustering.js";
import { findCycles } from "../src/analysis/cycles.js";
import { Filter } from "../src/analysis/filter.js";
import { Glob } from "../src/analysis/glob.js";
import { encode, number, PairsDocument } from "../src/graph.js";
import { NAME, SPEC, VERSION } from "../src/version.js";
import { build } from "./helpers.js";

function byId(units: Unit[]): Record<string, Unit> {
  return Object.fromEntries(units.map((unit) => [unit.id, unit]));
}

/** web/ and cli/ use core/; within core/, service uses repo. */
const layered = (): PairsDocument =>
  build([
    "web/controller.ts -> core/service.ts",
    "web/controller.ts -> core/repo.ts",
    "web/view.ts -> core/service.ts",
    "cli/command.ts -> core/service.ts",
    "core/service.ts -> core/repo.ts",
  ]);

describe("glob", () => {
  test("* and ? stay in one segment, ** crosses them", () => {
    expect(new Glob("src/*.ts").matches("src/a.ts")).toBe(true);
    expect(new Glob("src/*.ts").matches("src/x/a.ts")).toBe(false);
    expect(new Glob("src/?.ts").matches("src/ab.ts")).toBe(false);
    expect(new Glob("src/**").matches("src/x/y/a.ts")).toBe(true);
    expect(new Glob("**/test/**").matches("test/a.ts")).toBe(true);
    expect(new Glob("src/**/a.ts").matches("src/a.ts")).toBe(true);
  });

  test("a hyphen is literal, in the pattern and in the id", () => {
    expect(new Glob("src/user-controller.ts").matches("src/user-controller.ts")).toBe(true);
    expect(new Glob("src/*-controller.ts").matches("src/user-controller.ts")).toBe(true);
  });

  test("other characters are literal", () => {
    expect(new Glob("a+b(1).[ts]").matches("a+b(1).[ts]")).toBe(true);
    expect(new Glob("a.ts").matches("abts")).toBe(false);
    expect(new Glob("?.ts").matches("é.ts")).toBe(true);
  });
});

describe("filter", () => {
  test("drops builtins unless kept, and nodes no edge points to", () => {
    const document = build(["a.ts -> builtin:fs", "a.ts -> npm:x", "b.ts -> npm:y"]);
    const filtered = new Filter().exclude("b.ts").apply(document);
    expect(filtered.nodes().map((node) => node.id)).toEqual(["a.ts", "npm:x"]);
    expect(new Filter(true).apply(document).hasNode("builtin:fs")).toBe(true);
  });

  test("the last matching pattern wins", () => {
    const filter = new Filter().exclude("test/**").include("test/keep.ts");
    expect(filter.keeps("test/keep.ts")).toBe(true);
    expect(filter.keeps("test/drop.ts")).toBe(false);
    expect(filter.keeps("src/a.ts")).toBe(true);
  });
});

describe("clustering", () => {
  test("folder:N, with root files in .", () => {
    const clustering = Clustering.byFolder(1);
    expect(clustering.clusterOf({ id: "src/a/b.ts", kind: "internal" })).toBe("src");
    expect(clustering.clusterOf({ id: "b.ts", kind: "internal" })).toBe(".");
    expect(Clustering.byFolder(5).clusterOf({ id: "src/a/b.ts", kind: "internal" })).toBe("src/a");
  });

  test("namespace:N uses the module, else the folder", () => {
    const clustering = Clustering.fromString("namespace:2");
    expect(clustering.clusterOf({ id: "x.php", kind: "internal", module: "App\\Billing\\Tax" })).toBe("App\\Billing");
    expect(clustering.clusterOf({ id: "x.py", kind: "internal", module: "shop.billing.tax" })).toBe("shop.billing");
    expect(clustering.clusterOf({ id: "src/a/b/c.ts", kind: "internal" })).toBe("src/a");
    expect(clustering.name()).toBe("namespace:2");
  });

  test("rules: the first matching prefix wins, else the file is its own cluster", () => {
    const clustering = Clustering.parseRules("# comment\nsrc/core/  Core  # trailing\n\nsrc/ Web\r\n");
    expect(clustering.clusterOf({ id: "src/core/a.ts", kind: "internal" })).toBe("Core");
    expect(clustering.clusterOf({ id: "src/b.ts", kind: "internal" })).toBe("Web");
    expect(clustering.clusterOf({ id: "main.ts", kind: "internal" })).toBe("main.ts");
    expect(clustering.name()).toBe("rules");
    expect(() => Clustering.parseRules("a b c")).toThrow('rules line 1 must be "<prefix> <cluster>"');
  });

  test("unmatched lists the nodes no rule matches, sorted", () => {
    const files = build(["src/billing/a.ts -> src/newfolder/z.ts", "src/newfolder/b.ts -> src/billing/a.ts", "lib/c.ts -> lib/c.ts"]);
    expect(Clustering.parseRules("src/billing/ Billing\nlib/ Lib\n").unmatched(files)).toEqual(["src/newfolder/b.ts", "src/newfolder/z.ts"]);
    expect(Clustering.parseRules("src/ Core\nlib/ Lib\n").unmatched(files)).toEqual([]);
  });

  test("nothing is unmatched without the rules strategy, and only internal nodes can be", () => {
    const files = build(["src/a.ts -> lib/b.ts", "src/a.ts -> npm:left-pad"]);
    expect(Clustering.byFolder(1).unmatched(files)).toEqual([]);
    expect(Clustering.byNamespace(1).unmatched(files)).toEqual([]);
    expect(Clustering.parseRules("src/ Core\nlib/ Lib\n").unmatched(files)).toEqual([]);
  });

  test("describeUnmatched names the first few", () => {
    expect(describeUnmatched(["a.ts"])).toBe("rules: 1 file matches no rule and becomes its own cluster: a.ts");
    expect(describeUnmatched(["a.ts", "b.ts"])).toBe("rules: 2 files match no rule and each becomes its own cluster: a.ts, b.ts");
    expect(describeUnmatched([..."abcdefg"])).toBe("rules: 7 files match no rule and each becomes its own cluster: a, b, c, d, e and 2 more");
  });

  test("bad strategies", () => {
    expect(() => Clustering.fromString("folder:0")).toThrow(/unknown clustering/);
    expect(() => Clustering.fromString("module:1")).toThrow(/unknown clustering/);
    expect(() => Clustering.byFolder(0)).toThrow("clustering depth must be at least 1");
  });

  test("apply merges edges per cluster and counts the ones inside", () => {
    const { document, dropped } = Clustering.byFolder(1).apply(layered());
    expect(document.nodes()).toEqual([
      { id: "cli", kind: "cluster", members: ["cli/command.ts"] },
      { id: "core", kind: "cluster", members: ["core/repo.ts", "core/service.ts"] },
      { id: "web", kind: "cluster", members: ["web/controller.ts", "web/view.ts"] },
    ]);
    expect(document.edges()).toEqual([
      { from: "cli", to: "core", kinds: ["import"], count: 1 },
      { from: "web", to: "core", kinds: ["import"], count: 3 },
    ]);
    expect([...dropped]).toEqual([["core", 1]]);
  });
});

describe("cycles", () => {
  test("components of two or more, largest first, with the shortest example loop", () => {
    const successors = new Map([
      ["a", ["b"]],
      ["b", ["c", "a"]],
      ["c", ["a"]],
      ["d", ["e"]],
      ["e", ["d"]],
      ["f", ["f", "a"]],
    ]);
    expect(findCycles(successors)).toEqual([
      { members: ["a", "b", "c"], size: 3, example: ["a", "b", "a"] },
      { members: ["d", "e"], size: 2, example: ["d", "e", "d"] },
    ]);
  });

  test("deep chains do not overflow the stack", () => {
    const successors = new Map<string, string[]>();
    for (let index = 0; index < 50000; index++) {
      successors.set(`n${index}`, [`n${index + 1}`]);
    }
    successors.set("n50000", ["n0"]);
    expect(findCycles(successors)[0]!.size).toBe(50001);
  });
});

describe("analyze", () => {
  test("header and an empty project", () => {
    const analysis = analyze(new PairsDocument("typescript"));
    expect(Object.keys(analysis)).toEqual(["format", "version", "language", "generator", "clustering", "summary", "units", "cycles"]);
    expect(analysis).toMatchObject({ format: "untangled-analysis", version: SPEC, language: "typescript", clustering: null });
    expect(analysis.generator).toEqual({ name: NAME, version: VERSION });
    expect(analysis.summary).toEqual({
      units: 0,
      edges: 0,
      cycles: 0,
      largest_cycle: 0,
      units_in_cycles: 0,
      units_in_cycles_ratio: 0,
      mean_fan_out: 0,
      external_packages: 0,
      unresolved_references: 0,
    });
  });

  test("file units", () => {
    const analysis = analyze(
      build(["a.ts -> b.ts", "a.ts -> c.ts", "b.ts -> a.ts", "a.ts -> npm:x", "c.ts -> npm:x", "c.ts -> unresolved:module:y", "d.ts"]),
    );
    expect(byId(analysis.units)).toEqual({
      "a.ts": { id: "a.ts", fan_in: 1, fan_out: 2, external: 1, unresolved: 0, instability: 0.6667 },
      "b.ts": { id: "b.ts", fan_in: 1, fan_out: 1, external: 0, unresolved: 0, instability: 0.5 },
      "c.ts": { id: "c.ts", fan_in: 1, fan_out: 0, external: 1, unresolved: 1, instability: 0 },
      "d.ts": { id: "d.ts", fan_in: 0, fan_out: 0, external: 0, unresolved: 0, instability: null },
    });
    expect(analysis.summary).toMatchObject({ units: 4, edges: 3, cycles: 1, largest_cycle: 2, units_in_cycles: 2, units_in_cycles_ratio: 0.5, mean_fan_out: 0.75, external_packages: 1, unresolved_references: 1 });
    expect(analysis.cycles).toEqual([{ members: ["a.ts", "b.ts"], size: 2, example: ["a.ts", "b.ts", "a.ts"] }]);
  });

  test("clusters: Ca and Ce count files, fan-in and fan-out count clusters", () => {
    const units = byId(analyze(layered(), Clustering.byFolder(1)).units);
    expect(units.core).toEqual({ id: "core", fan_in: 2, fan_out: 0, ca: 3, ce: 0, external: 0, unresolved: 0, instability: 0, members: ["core/repo.ts", "core/service.ts"] });
    expect(units.web).toMatchObject({ fan_out: 1, ca: 0, ce: 2, instability: 1 });
  });

  test("refuses an already clustered document", () => {
    const document = new PairsDocument("typescript");
    document.addNode("core", "cluster", { members: [] });
    expect(() => analyze(document)).toThrow(AnalysisError);
  });

  test("encodes as the other libraries do", () => {
    const text = encode(analyze(build(["a.ts -> b.ts", "b.ts -> c.ts", "c.ts -> a.ts", "c.ts -> d.ts"])));
    expect(text).toContain('"units_in_cycles_ratio": 0.75,\n');
    expect(text).toContain('"instability": 0.6667\n');
    expect(text).toContain('  "cycles": [\n    {\n      "members": [\n');
  });
});

describe("numbers", () => {
  test("rounds half away from zero on the shortest decimal form", () => {
    expect(number(1 / 3)).toBe(0.3333);
    expect(number(2 / 3)).toBe(0.6667);
    expect(number(0.12345)).toBe(0.1235);
    expect(number(1.00005)).toBe(1.0001);
    expect(number(1)).toBe(1);
    expect(number(1e-7)).toBe(0);
  });
});

describe("reading pairs documents", () => {
  const valid = { format: "untangled-pairs", version: "0.1", language: "php", nodes: [{ id: "a", kind: "internal", module: "A" }, { id: "b", kind: "internal" }], edges: [{ from: "a", to: "b", kinds: ["new", "use"], count: 2 }] };

  test("reads nodes, extra fields and edges", () => {
    const document = PairsDocument.fromObject(valid);
    expect(document.language).toBe("php");
    expect(document.node("a")).toEqual({ id: "a", kind: "internal", module: "A" });
    expect(document.edges()).toEqual([{ from: "a", to: "b", kinds: ["new", "use"], count: 2 }]);
  });

  test("another minor version is a warning, another major version an error", () => {
    const warnings: string[] = [];
    PairsDocument.fromObject({ ...valid, version: "0.2" }, warnings);
    expect(warnings).toEqual(["pairs document version 0.2 is newer or older than 0.1; reading it anyway"]);
    expect(() => PairsDocument.fromObject({ ...valid, version: "1.0" })).toThrow('unsupported pairs document version "1.0" (this library reads 0.1)');
  });

  test("invalid documents", () => {
    expect(() => PairsDocument.fromObject([])).toThrow(/not an Untangled pairs document/);
    expect(() => PairsDocument.fromObject({ ...valid, nodes: undefined })).toThrow(/needs "language", "nodes" and "edges"/);
    expect(() => PairsDocument.fromObject({ ...valid, nodes: [{ id: 1 }] })).toThrow(/every node needs/);
    expect(() => PairsDocument.fromObject({ ...valid, edges: [{ from: "a" }] })).toThrow(/every edge needs/);
    expect(() => PairsDocument.fromObject({ ...valid, edges: [{ from: "a", to: "z" }] })).toThrow("edge a -> z names a node that is not in the document");
  });

  test("missing kinds and counts", () => {
    const document = PairsDocument.fromObject({ ...valid, edges: [{ from: "a", to: "b", count: 0 }] });
    expect(document.edges()).toEqual([{ from: "a", to: "b", kinds: [], count: 1 }]);
  });
});
