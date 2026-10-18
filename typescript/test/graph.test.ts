// SPDX-License-Identifier: MIT

import { expect, test } from "vitest";

import { encode, PairsDocument } from "../src/graph.js";

test("sorts nodes and edges and merges kinds and counts", () => {
  const document = new PairsDocument("typescript");
  document.addNode("src/b.ts", "internal");
  document.addNode("src/a.ts", "internal");
  document.addNode("npm:react", "external");
  document.addEdge("src/b.ts", "src/a.ts", ["import"]);
  document.addEdge("src/a.ts", "npm:react", ["require"]);
  document.addEdge("src/a.ts", "npm:react", ["import", "type"]);
  expect(document.nodes().map((node) => node.id)).toEqual(["npm:react", "src/a.ts", "src/b.ts"]);
  expect(document.edges()).toEqual([
    { from: "src/a.ts", to: "npm:react", kinds: ["import", "require", "type"], count: 2 },
    { from: "src/b.ts", to: "src/a.ts", kinds: ["import"], count: 1 },
  ]);
});

test("drops self-edges", () => {
  const document = new PairsDocument("typescript");
  document.addNode("a.ts", "internal");
  document.addEdge("a.ts", "a.ts", ["import"]);
  expect(document.edges()).toEqual([]);
});

test("writes JSON with two spaces and a trailing newline", () => {
  const document = new PairsDocument("typescript");
  const text = document.toJson();
  expect(text.endsWith("}\n")).toBe(true);
  expect(text).toContain('\n  "format": "untangled-pairs",');
  expect(encode({ a: [1] })).toBe('{\n  "a": [\n    1\n  ]\n}\n');
});

test("writes snakefood lines for internal edges and lone files", () => {
  const document = new PairsDocument("typescript");
  document.addNode("a.ts", "internal");
  document.addNode("b's.ts", "internal");
  document.addNode("c.ts", "internal");
  document.addNode("npm:x", "external");
  document.addEdge("a.ts", "b's.ts", ["import"]);
  document.addEdge("a.ts", "npm:x", ["import"]);
  expect(document.toSnakefood("/p")).toBe(
    "(('/p', 'a.ts'), ('/p', 'b\\'s.ts'))\n" + "(('/p', 'b\\'s.ts'), (None, None))\n" + "(('/p', 'c.ts'), (None, None))\n",
  );
});
