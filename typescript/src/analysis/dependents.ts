// SPDX-License-Identifier: MIT
// The dependents query of spec/dependents.md: which files depend on some nodes, directly or through
// other files, read from a file-level pairs document.

import { CLUSTER, INTERNAL, type PairsDocument } from "../graph.js";
import { compareText } from "../text.js";
import { NAME, SPEC, VERSION } from "../version.js";
import type { Filter } from "./filter.js";

export interface DependentsDocument {
  format: "untangled-dependents";
  version: string;
  language: string;
  generator: { name: string; version: string };
  transitive: boolean;
  targets: { target: string; nodes: string[] }[];
  dependents: { id: string; depth: number }[];
}

/** Thrown when the document is clustered or a target matches nothing. */
export class DependentsError extends Error {}

/** `filter` keeps only the dependents it keeps; the walk itself is not filtered. */
export function findDependents(files: PairsDocument, targets: string[], transitive: boolean, filter?: Filter): DependentsDocument {
  const symbols = new Map<string, string[]>();
  for (const node of files.nodes()) {
    if (node.kind === CLUSTER) {
      throw new DependentsError("the pairs document is already clustered; ask about the file-level document instead");
    }
    if (node.kind === INTERNAL && Array.isArray(node.symbols)) {
      for (const symbol of node.symbols as string[]) {
        symbols.set(symbol, [...(symbols.get(symbol) ?? []), node.id]);
      }
    }
  }

  const resolved: { target: string; nodes: string[] }[] = [];
  const start = new Set<string>();
  for (const target of targets) {
    const nodes = files.hasNode(target) ? [target] : (symbols.get(target) ?? []);
    if (nodes.length === 0) {
      throw new DependentsError(`no node or symbol "${target}" in the pairs document`);
    }
    resolved.push({ target, nodes: [...nodes].sort(compareText) });
    nodes.forEach((id) => start.add(id));
  }

  const dependentsOf = new Map<string, string[]>();
  for (const edge of files.edges()) {
    dependentsOf.set(edge.to, [...(dependentsOf.get(edge.to) ?? []), edge.from]);
  }

  // Breadth-first from the targets, so the first time a file is reached is its shortest distance.
  const depth = new Map<string, number>();
  let frontier = [...start];
  for (let level = 1; frontier.length > 0 && (transitive || level === 1); level++) {
    const reached: string[] = [];
    for (const id of frontier) {
      for (const from of dependentsOf.get(id) ?? []) {
        if (!start.has(from) && !depth.has(from)) {
          depth.set(from, level);
          reached.push(from);
        }
      }
    }
    frontier = reached;
  }

  const dependents = [...depth]
    .filter(([id]) => filter === undefined || filter.keeps(id))
    .map(([id, level]) => ({ id, depth: level }))
    .sort((a, b) => a.depth - b.depth || compareText(a.id, b.id));
  return {
    format: "untangled-dependents",
    version: SPEC,
    language: files.language,
    generator: { name: NAME, version: VERSION },
    transitive,
    targets: resolved,
    dependents,
  };
}

/** The text form for people: a count, then the dependents grouped by folder. */
export function renderDependentsText(document: DependentsDocument): string {
  const targets = document.targets.map((item) => item.target).join(", ");
  const count = document.dependents.length;
  if (count === 0) {
    return `No dependents of ${targets}\n`;
  }
  const folders = new Map<string, Map<string, number>>();
  for (const { id, depth } of document.dependents) {
    const slash = id.lastIndexOf("/");
    const folder = slash === -1 ? "./" : id.slice(0, slash + 1);
    const names = folders.get(folder) ?? new Map<string, number>();
    names.set(slash === -1 ? id : id.slice(slash + 1), depth);
    folders.set(folder, names);
  }
  let text = `${count} ${count === 1 ? "dependent" : "dependents"} of ${targets}\n`;
  for (const folder of [...folders.keys()].sort(compareText)) {
    text += `\n${folder}\n`;
    const names = folders.get(folder)!;
    for (const name of [...names.keys()].sort(compareText)) {
      text += `  ${name}${document.transitive ? `  (depth ${names.get(name)})` : ""}\n`;
    }
  }
  return text;
}
