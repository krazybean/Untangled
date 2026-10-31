// SPDX-License-Identifier: MIT
// Which files a JavaScript/TypeScript project has, and which of them are scanned
// (spec/languages/typescript.md, "Input").

import { readdirSync, statSync } from "node:fs";
import { join } from "node:path";

import { decode } from "../text.js";
import { isUnder, joinPath } from "./paths.js";
import { warningDiagnostic, warningMessages, type Diagnostic } from "../diagnostics.js";

export const CODE_EXTENSIONS = [".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs"];
export const DECLARATION_SUFFIXES = [".d.ts", ".d.mts", ".d.cts"];
const BUILD_FOLDERS = new Set(["dist", "build", "coverage"]);
const TEST_FOLDERS = new Set(["__tests__", "__mocks__", "test", "tests"]);
const TEST_FILE = /\.(test|spec)\.[^./]+$/;

export class ProjectError extends Error {}

export class Project {
  /**
   * Every file outside node_modules and hidden folders, by id: project-relative POSIX path.
   * Files in hidden folders are added by has() when an import names them.
   */
  readonly files = new Map<string, Buffer>();
  /** Code files scanned by default, sorted. */
  readonly scanned: string[] = [];
  /** Build output files not scanned, per build folder. */
  readonly skippedBuild = new Map<string, number>();
  /** The folders holding a node_modules folder ("" for the root). */
  readonly nodeModules = new Set<string>();
  readonly diagnostics: Diagnostic[] = [];
  /** The messages of the warning diagnostics, for callers that read strings. */
  get warnings(): string[] {
    return warningMessages(this.diagnostics);
  }

  constructor(
    readonly root: string,
    options: { dev: boolean; sources: string[]; outDir: string | undefined },
  ) {
    let rootStat;
    try {
      rootStat = statSync(root);
    } catch {
      throw new ProjectError(`${root} is not a folder`);
    }
    if (!rootStat.isDirectory()) {
      throw new ProjectError(`${root} is not a folder`);
    }
    const stack: [Buffer, string][] = [[Buffer.from(root), ""]];
    while (stack.length) {
      const [folder, prefix] = stack.pop()!;
      for (const entry of readdirSync(folder, { encoding: "buffer", withFileTypes: true })) {
        const name = decode(entry.name);
        const path = Buffer.from(join(folder.toString("latin1"), entry.name.toString("latin1")), "latin1");
        const id = prefix ? `${prefix}/${name}` : name;
        if (entry.isDirectory()) {
          if (name === "node_modules") {
            this.nodeModules.add(prefix);
          } else if (!name.startsWith(".")) {
            stack.push([path, id]);
          }
        } else if (entry.isFile() || (entry.isSymbolicLink() && isFile(path))) {
          this.files.set(id, path);
        }
      }
    }

    const sources: string[] = [];
    for (const source of options.sources) {
      const path = joinPath("", source);
      if (path === undefined) {
        this.diagnostics.push(warningDiagnostic("source-outside-project", `--source=${source}: outside the project, ignored`));
      } else if (!this.files.has(path) && ![...this.files.keys()].some((id) => isUnder(id, path))) {
        this.diagnostics.push(warningDiagnostic("source-not-found", `--source=${source}: no such file or folder in the project`, [path]));
      } else {
        sources.push(path);
      }
    }

    for (const id of [...this.files.keys()].sort()) {
      if (!isCode(id) || isDeclaration(id)) {
        continue;
      }
      if (sources.some((source) => isUnder(id, source))) {
        this.scanned.push(id);
        continue;
      }
      const build = buildFolder(id, options.outDir);
      if (build !== undefined) {
        this.skippedBuild.set(build, (this.skippedBuild.get(build) ?? 0) + 1);
      } else if (options.dev || !isTest(id)) {
        this.scanned.push(id);
      }
    }
  }

  /**
   * Whether the project has this file. A file in a hidden folder is not listed up front, and
   * is added once an import names it.
   */
  has(id: string): boolean {
    if (this.files.has(id)) {
      return true;
    }
    if (!id.split("/").slice(0, -1).some((part) => part.startsWith("."))) {
      return false;
    }
    const path = Buffer.from(join(this.root, id));
    if (!isFile(path)) {
      return false;
    }
    this.files.set(id, path);
    return true;
  }

  /** Whether a code file outside build output may be scanned when a scanned file imports it. */
  followable(id: string, outDir: string | undefined): boolean {
    return isCode(id) && buildFolder(id, outDir) === undefined;
  }
}

export function isCode(id: string): boolean {
  return CODE_EXTENSIONS.some((extension) => id.endsWith(extension));
}

export function isDeclaration(id: string): boolean {
  return DECLARATION_SUFFIXES.some((suffix) => id.endsWith(suffix));
}

export function isTest(id: string): boolean {
  const parts = id.split("/");
  return TEST_FILE.test(parts.at(-1)!) || parts.slice(0, -1).some((part) => TEST_FOLDERS.has(part));
}

/** The build output folder holding a file (`dist`, `packages/a/build`, the outDir), if any. */
function buildFolder(id: string, outDir: string | undefined): string | undefined {
  if (outDir && isUnder(id, outDir) && outDir !== id) {
    return outDir;
  }
  const parts = id.split("/").slice(0, -1);
  const index = parts.findIndex((part) => BUILD_FOLDERS.has(part));
  return index === -1 ? undefined : parts.slice(0, index + 1).join("/");
}

function isFile(path: Buffer): boolean {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
}
