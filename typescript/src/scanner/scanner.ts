// SPDX-License-Identifier: MIT
// Scans a JavaScript/TypeScript project into a pairs document, following
// spec/languages/typescript.md.

import { readFileSync } from "node:fs";

import { BUILTIN, EXTERNAL, INTERNAL, PairsDocument, UNRESOLVED } from "../graph.js";
import { compareText, decode, sortText } from "../text.js";
import { loadConfig } from "./config.js";
import { collect, TYPE, type FileImports } from "./imports.js";
import { Project } from "./project.js";
import { Resolver } from "./resolver.js";

export interface ScanOptions {
  dev?: boolean;
  sources?: string[];
  aliases?: string[];
}

export interface ScanResult {
  pairs: PairsDocument;
  warnings: string[];
}

const KINDS: Record<string, string> = { builtin: BUILTIN, npm: EXTERNAL, unresolved: UNRESOLVED };

export function scan(root: string, options: ScanOptions = {}): ScanResult {
  const config = loadConfig(root, options.aliases ?? []);
  const project = new Project(root, { dev: options.dev ?? false, sources: options.sources ?? [], outDir: config.outDir });
  const warnings = [...config.warnings, ...project.warnings];
  const resolver = new Resolver(project, config, warnings);

  // Scan the default files, then any test or declaration file a scanned file imports.
  const results = new Map<string, FileImports>();
  const targets = new Map<string, [string, string[]][]>();
  const recovered: string[] = [];
  const assets = new Map<string, number>();
  const queue = [...project.scanned];
  for (let index = 0; index < queue.length; index++) {
    const file = queue[index]!;
    if (results.has(file)) {
      continue;
    }
    let result: FileImports;
    try {
      result = collect(decode(readFileSync(project.files.get(file)!)), file);
    } catch (error) {
      result = { references: [], error: `cannot read it: ${(error as Error).message}`, unread: "read" };
    }
    results.set(file, result);
    if (result.error !== undefined) {
      warnings.push(`${file}: ${result.error}`);
    } else if (result.recovered !== undefined) {
      recovered.push(`${file}: ${result.recovered}`);
    }
    const list: [string, string[]][] = [];
    targets.set(file, list);
    for (const reference of result.references) {
      const kinds = reference.type ? [reference.kind, TYPE] : [reference.kind];
      if (reference.specifier === undefined) {
        list.push([`unresolved:dynamic:${reference.text ?? ""}`, kinds]);
        continue;
      }
      const target = resolver.resolve(file, reference.specifier);
      if ("asset" in target) {
        assets.set(target.asset, (assets.get(target.asset) ?? 0) + 1);
        continue;
      }
      list.push([target.id, kinds]);
      if (
        !results.has(target.id) &&
        project.files.has(target.id) &&
        project.followable(target.id, config.outDir)
      ) {
        // A test or a declaration file: every other followable file is scanned already.
        queue.push(target.id);
      }
    }
  }

  const pairs = new PairsDocument("typescript");
  for (const [file, result] of results) {
    pairs.addNode(file, INTERNAL, result.unread === undefined ? {} : { error: result.unread });
  }
  for (const [file, list] of targets) {
    for (const [target, kinds] of list) {
      if (!pairs.hasNode(target)) {
        // A project file that is not scanned (JSON, build output) has no prefix.
        const prefix = project.files.has(target) ? undefined : target.slice(0, target.indexOf(":"));
        pairs.addNode(target, prefix === undefined ? INTERNAL : KINDS[prefix]!);
      }
      pairs.addEdge(file, target, kinds);
    }
  }

  if (project.skippedBuild.size) {
    const count = [...project.skippedBuild.values()].reduce((sum, item) => sum + item, 0);
    warnings.push(
      `skipped ${count} file${count === 1 ? "" : "s"} in build output (${few(sortText(project.skippedBuild.keys()))});` +
        " add a folder back with --source=<path> if it holds source code",
    );
  }
  if (recovered.length) {
    warnings.push(
      `${recovered.length} file${recovered.length === 1 ? " has" : "s have"} syntax errors; the imports the parser` +
        ` could still read are kept: ${few(recovered, "; ")}`,
    );
  }
  if (assets.size) {
    const count = [...assets.values()].reduce((sum, item) => sum + item, 0);
    const list = [...assets].sort((a, b) => b[1] - a[1] || compareText(a[0], b[0])).map(([name, n]) => `${name} ${n}`);
    warnings.push(
      `${count} import${count === 1 ? "" : "s"} of non-code files gave no edge (${list.join(", ")})`,
    );
  }
  if (project.nodeModules.size === 0 && resolver.unresolvedBare.size) {
    warnings.push(
      `no node_modules folder, so imports of ${few(sortText(resolver.unresolvedBare), ", ", 5)} could only be` +
        " matched against declared dependencies by name, and show as unresolved; install the project's" +
        " dependencies first for a complete picture",
    );
  }
  return { pairs, warnings };
}

/** The first few items of a list, then how many more. */
function few(items: string[], separator = ", ", limit = 3): string {
  const shown = items.slice(0, limit).join(separator);
  return items.length > limit ? `${shown}${separator}and ${items.length - limit} more` : shown;
}
