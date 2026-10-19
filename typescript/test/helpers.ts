// SPDX-License-Identifier: MIT
// Temporary projects for the tests.

import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { afterEach } from "vitest";

import { PairsDocument } from "../src/graph.js";

const created: string[] = [];

afterEach(() => {
  for (const folder of created.splice(0)) {
    rmSync(folder, { recursive: true, force: true });
  }
});

/** A temporary folder with these files (path → content), removed after the test. */
export function project(files: Record<string, string | Uint8Array>): string {
  const root = mkdtempSync(join(tmpdir(), "untangled-"));
  created.push(root);
  for (const [path, content] of Object.entries(files)) {
    mkdirSync(dirname(join(root, path)), { recursive: true });
    writeFileSync(join(root, path), content);
  }
  return root;
}

/** Output collected by the CLI. */
export class Buffered {
  text = "";
  write(text: string): void {
    this.text += text;
  }
}

/**
 * A file-level pairs document from "from -> to" lines. Ids with a prefix (`npm:`,
 * `builtin:`, `unresolved:`) get that kind; every other id is an internal file.
 */
export function build(lines: string[], language = "typescript"): PairsDocument {
  const document = new PairsDocument(language);
  const kinds: Record<string, string> = { npm: "external", builtin: "builtin", unresolved: "unresolved" };
  for (const line of lines) {
    const [from, to] = line.split(" -> ") as [string, string | undefined];
    for (const id of to === undefined ? [from] : [from, to]) {
      const prefix = id.includes(":") ? id.slice(0, id.indexOf(":")) : "";
      document.addNode(id, kinds[prefix] ?? "internal");
    }
    if (to !== undefined) {
      document.addEdge(from, to, ["import"]);
    }
  }
  return document;
}
