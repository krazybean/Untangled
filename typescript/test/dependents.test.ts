// SPDX-License-Identifier: MIT

import { describe, expect, test } from "vitest";

import { Filter } from "../src/analysis/filter.js";
import { DependentsError, findDependents, renderDependentsText, type DependentsDocument } from "../src/analysis/dependents.js";
import { PairsDocument } from "../src/graph.js";
import { build } from "./helpers.js";

/**
 * web/controller -> core/service -> core/repo, web/view -> core/service, a cycle
 * core/repo <-> core/cache, and web/controller uses npm:acme.
 */
function graph(): PairsDocument {
  const document = build([
    "web/controller.ts -> core/service.ts",
    "web/view.ts -> core/service.ts",
    "core/service.ts -> core/repo.ts",
    "core/repo.ts -> core/cache.ts",
    "core/cache.ts -> core/repo.ts",
    "web/controller.ts -> npm:acme",
  ]);
  document.node("core/service.ts")!.symbols = ["Core.Service"];
  return document;
}

const depths = (document: DependentsDocument): Record<string, number> => Object.fromEntries(document.dependents.map((item) => [item.id, item.depth]));

describe("findDependents", () => {
  test("direct dependents by default", () => {
    const document = findDependents(graph(), ["core/service.ts"], false);
    expect(depths(document)).toEqual({ "web/controller.ts": 1, "web/view.ts": 1 });
    expect(document.transitive).toBe(false);
  });

  test("transitive dependents carry their shortest depth, sorted by depth then id", () => {
    const document = findDependents(graph(), ["core/cache.ts"], true);
    expect(document.dependents).toEqual([
      { id: "core/repo.ts", depth: 1 },
      { id: "core/service.ts", depth: 2 },
      { id: "web/controller.ts", depth: 3 },
      { id: "web/view.ts", depth: 3 },
    ]);
  });

  test("a target in a cycle is not its own dependent", () => {
    const document = findDependents(graph(), ["core/repo.ts"], true);
    expect(depths(document)["core/repo.ts"]).toBeUndefined();
    expect(depths(document)["core/cache.ts"]).toBe(1);
  });

  test("a symbol names the file that declares it", () => {
    const document = findDependents(graph(), ["Core.Service"], false);
    expect(document.targets).toEqual([{ target: "Core.Service", nodes: ["core/service.ts"] }]);
    expect(document.dependents.map((item) => item.id)).toEqual(["web/controller.ts", "web/view.ts"]);
  });

  test("an external package can be a target", () => {
    expect(depths(findDependents(graph(), ["npm:acme"], true))).toEqual({ "web/controller.ts": 1 });
  });

  test("several targets are one query at the shortest distance", () => {
    const document = findDependents(graph(), ["core/repo.ts", "core/service.ts"], true);
    // service is a target, so it is not listed even though it depends on repo.
    expect(depths(document)).toEqual({ "core/cache.ts": 1, "web/controller.ts": 1, "web/view.ts": 1 });
    expect(document.targets[0]!.nodes).toEqual(["core/repo.ts"]);
  });

  test("a symbol declared in several files matches all of them", () => {
    const document = build(["user.ts -> b.ts"]);
    document.node("b.ts")!.symbols = ["Polyfill"];
    document.addNode("a.ts", "internal", { symbols: ["Polyfill"] });
    const found = findDependents(document, ["Polyfill"], false);
    expect(found.targets[0]!.nodes).toEqual(["a.ts", "b.ts"]);
    expect(depths(found)).toEqual({ "user.ts": 1 });
  });

  test("the filter hides dependents but the walk goes through them", () => {
    const filter = new Filter().exclude("**").include("web/**");
    expect(depths(findDependents(graph(), ["core/cache.ts"], true, filter))).toEqual({ "web/controller.ts": 3, "web/view.ts": 3 });
  });

  test("an unknown target and a clustered document are errors", () => {
    expect(() => findDependents(graph(), ["core/service.ts", "nope"], false)).toThrow(new DependentsError('no node or symbol "nope" in the pairs document', "target-not-found"));
    const clustered = new PairsDocument("typescript");
    clustered.addNode("core", "cluster", { members: ["a.ts"] });
    expect(() => findDependents(clustered, ["core"], false)).toThrow(/already clustered/);
  });

  test("ids are sorted by byte value even when they look numeric", () => {
    const document = findDependents(build(["9 -> t", "10 -> t", "1e1 -> t", "2 -> t"]), ["t"], false);
    expect(document.dependents.map((item) => item.id)).toEqual(["10", "1e1", "2", "9"]);
  });

  test("only internal nodes answer to a symbol", () => {
    const document = build(["a.ts -> npm:y"]);
    document.node("npm:y")!.symbols = ["Vendor.Y"];
    expect(() => findDependents(document, ["Vendor.Y"], false)).toThrow(DependentsError);
  });
});

describe("findDependents: limiting the walk", () => {
  const ids = (document: DependentsDocument): string[] => document.dependents.map((item) => item.id);

  test("--max-depth stops the walk", () => {
    const found = (maxDepth: number): Record<string, number> => depths(findDependents(graph(), ["core/cache.ts"], true, undefined, { maxDepth }));
    expect(found(1)).toEqual({ "core/repo.ts": 1 });
    expect(found(2)).toEqual({ "core/repo.ts": 1, "core/service.ts": 2 });
    expect(found(3)).toEqual({ "core/repo.ts": 1, "core/service.ts": 2, "web/controller.ts": 3, "web/view.ts": 3 });
    expect(found(1000)).toEqual(found(3));
  });

  test("a maximum depth of 1 is the direct dependents", () => {
    const direct = findDependents(graph(), ["core/service.ts"], false);
    const limited = findDependents(graph(), ["core/service.ts"], true, undefined, { maxDepth: 1 });
    expect(limited.dependents).toEqual(direct.dependents);
    expect(limited.transitive).toBe(true);
  });

  test("a maximum depth below 1 is refused", () => {
    expect(() => findDependents(graph(), ["core/service.ts"], true, undefined, { maxDepth: 0 })).toThrow(DependentsError);
    expect(() => findDependents(graph(), ["core/service.ts"], true, undefined, { maxDepth: Number.NaN })).toThrow(DependentsError);
  });

  test("a maximum depth without a transitive search is refused", () => {
    for (const maxDepth of [1, 2]) {
      expect(() => findDependents(graph(), ["core/service.ts"], false, undefined, { maxDepth })).toThrow(
        new DependentsError("the maximum depth only applies to a transitive search"),
      );
    }
  });

  test("--through only goes into matching files", () => {
    const found = (through: string[], targets = ["core/cache.ts"]): Record<string, number> => depths(findDependents(graph(), targets, true, undefined, { through }));
    expect(found(["core/**"])).toEqual({ "core/repo.ts": 1, "core/service.ts": 2 });
    // Repo is not eligible, so nothing is found by way of it, even the web files that use service.
    expect(found(["web/**"])).toEqual({});
    // The patterns are alternatives.
    expect(found(["core/**", "web/**"])).toEqual({ "core/repo.ts": 1, "core/service.ts": 2, "web/controller.ts": 3, "web/view.ts": 3 });
    // The target is the start of the walk whatever it matches: cache is not in the list.
    expect(found(["core/repo.ts"])).toEqual({ "core/repo.ts": 1 });
  });

  test("--through finds the shortest path through eligible files only", () => {
    // c is two steps from t by way of x, but x is not eligible: by way of m and a it is three.
    const document = build(["x.ts -> t.ts", "c.ts -> x.ts", "a.ts -> t.ts", "m.ts -> a.ts", "c.ts -> m.ts"]);
    expect(depths(findDependents(document, ["t.ts"], true, undefined, { through: ["a.ts", "m.ts", "c.ts"] }))).toEqual({ "a.ts": 1, "m.ts": 2, "c.ts": 3 });
    expect(depths(findDependents(document, ["t.ts"], true))).toEqual({ "a.ts": 1, "x.ts": 1, "c.ts": 2, "m.ts": 2 });
  });

  test("--through applies to direct dependents too", () => {
    expect(ids(findDependents(graph(), ["core/service.ts"], false, undefined, { through: ["web/controller.ts"] }))).toEqual(["web/controller.ts"]);
  });

  test("--through combines with --max-depth and the output filter", () => {
    const both = ["core/**", "web/**"];
    expect(depths(findDependents(graph(), ["core/cache.ts"], true, undefined, { through: both, maxDepth: 2 }))).toEqual({ "core/repo.ts": 1, "core/service.ts": 2 });
    // --exclude hides service from the list but the walk still goes through it.
    const hidden = new Filter().exclude("core/service.ts");
    expect(depths(findDependents(graph(), ["core/cache.ts"], true, hidden, { through: both }))).toEqual({ "core/repo.ts": 1, "web/controller.ts": 3, "web/view.ts": 3 });
    // --include cannot bring back a file --through left out.
    expect(findDependents(graph(), ["core/cache.ts"], true, new Filter().include("**"), { through: ["web/**"] }).dependents).toEqual([]);
  });

  test("--through with two targets and a cycle lists each file once", () => {
    const document = findDependents(graph(), ["core/repo.ts", "core/cache.ts"], true, undefined, { through: ["core/**", "web/**"] });
    expect(depths(document)).toEqual({ "core/service.ts": 1, "web/controller.ts": 2, "web/view.ts": 2 });
  });
});

describe("findDependents: target spellings", () => {
  const nodes = (target: string, root?: string): string[] => findDependents(graph(), [target], false, undefined, { root }).targets[0]!.nodes;

  test("paths are respelled to project ids", () => {
    for (const target of ["core/service.ts", "./core/service.ts", "core\\service.ts", "core//x/../service.ts", "/work/app/core/service.ts", "/work/app/./core/../core/service.ts"]) {
      expect(nodes(target, "/work/app"), target).toEqual(["core/service.ts"]);
    }
    expect(nodes("C:\\work\\app\\core\\service.ts", "c:/work/app")).toEqual(["core/service.ts"]);
  });

  test("an absolute path outside the project is refused", () => {
    for (const target of ["/work/other/core/service.ts", "/work/application/core/service.ts", "/work/app/../app2/x.ts", "D:\\work\\app\\core\\service.ts"]) {
      expect(() => nodes(target, "/work/app"), target).toThrow(/is outside the project folder \/work\/app/);
    }
  });

  test("an absolute path matches nothing without a project folder", () => {
    expect(() => nodes("/work/app/core/service.ts")).toThrow(/no node or symbol "\/work\/app\/core\/service.ts"/);
  });

  test("an as-written match still wins over a respelling", () => {
    const document = build(["./a/b.ts -> a/b.ts"]);
    expect(findDependents(document, ["./a/b.ts"], false).targets[0]!.nodes).toEqual(["./a/b.ts"]);
  });
});

describe("renderDependentsText", () => {
  test("nothing depends on a top-level file", () => {
    const document = findDependents(graph(), ["web/controller.ts"], true);
    expect(document.dependents).toEqual([]);
    expect(renderDependentsText(document)).toBe("No dependents of web/controller.ts\n");
  });

  test("groups dependents by folder", () => {
    const document = findDependents(graph(), ["core/service.ts", "core/repo.ts"], false);
    expect(renderDependentsText(document)).toBe("3 dependents of core/service.ts, core/repo.ts\n\ncore/\n  cache.ts\n\nweb/\n  controller.ts\n  view.ts\n");
  });

  test("shows the depth when transitive, and root files go first", () => {
    const document = findDependents(build(["index.ts -> lib/a.ts", "lib/b.ts -> lib/a.ts"]), ["lib/a.ts"], true);
    expect(renderDependentsText(document)).toBe("2 dependents of lib/a.ts\n\n./\n  index.ts  (depth 1)\n\nlib/\n  b.ts  (depth 1)\n");
  });

  test("counts one dependent in the singular", () => {
    expect(renderDependentsText(findDependents(build(["a.ts -> b.ts"]), ["b.ts"], false))).toMatch(/^1 dependent of b\.ts\n/);
  });
});
