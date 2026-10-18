// SPDX-License-Identifier: MIT
// Temporary projects for the tests.

import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { afterEach } from "vitest";

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
