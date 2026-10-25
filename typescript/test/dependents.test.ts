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
    expect(() => findDependents(graph(), ["core/service.ts", "nope"], false)).toThrow(new DependentsError('no node or symbol "nope" in the pairs document'));
    const clustered = new PairsDocument("typescript");
    clustered.addNode("core", "cluster", { members: ["a.ts"] });
    expect(() => findDependents(clustered, ["core"], false)).toThrow(/already clustered/);
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
