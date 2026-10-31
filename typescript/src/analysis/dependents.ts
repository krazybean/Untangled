// SPDX-License-Identifier: MIT
// The dependents query of spec/dependents.md: which files depend on some nodes, directly or through
// other files, read from a file-level pairs document.

import { realpathSync } from "node:fs";
import { posix } from "node:path";

import { CLUSTER, INTERNAL, type PairsDocument } from "../graph.js";
import { compareText } from "../text.js";
import { NAME, SPEC, VERSION } from "../version.js";
import type { Filter } from "./filter.js";
import { Glob } from "./glob.js";

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

/** What limits the walk, and how targets are spelled. */
export interface DependentsOptions {
  /** Globs: when there are any, the walk only goes into files matching one, so nothing is found by way of other files. */
  through?: string[];
  /** With `transitive`, the deepest dependents to find; at least 1. */
  maxDepth?: number;
  /** The absolute project folder, to accept absolute paths inside it as targets. */
  root?: string;
}

/**
 * `filter` keeps only the dependents it keeps once the walk is done. Throws DependentsError when the
 * document is clustered, a target matches nothing or is an absolute path outside `root`, or `maxDepth`
 * is below 1 or given without `transitive`.
 */
export function findDependents(
  files: PairsDocument,
  targets: string[],
  transitive: boolean,
  filter?: Filter,
  options: DependentsOptions = {},
): DependentsDocument {
  const { maxDepth, root } = options;
  if (maxDepth !== undefined && !(maxDepth >= 1)) {
    throw new DependentsError("the maximum depth must be a positive integer");
  }
  if (maxDepth !== undefined && !transitive) {
    throw new DependentsError("the maximum depth only applies to a transitive search");
  }
  const eligible = (options.through ?? []).map((pattern) => new Glob(pattern));
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
    let nodes = files.hasNode(target) ? [target] : (symbols.get(target) ?? []);
    if (nodes.length === 0) {
      nodes = respelled(files, target, root);
    }
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
  // A file the walk may not go into is never reached, so nothing is found by way of it.
  const deepest = transitive ? (maxDepth ?? Infinity) : 1;
  const depth = new Map<string, number>();
  let frontier = [...start];
  for (let level = 1; frontier.length > 0 && level <= deepest; level++) {
    const reached: string[] = [];
    for (const id of frontier) {
      for (const from of dependentsOf.get(id) ?? []) {
        if (!start.has(from) && !depth.has(from) && (eligible.length === 0 || eligible.some((glob) => glob.matches(from)))) {
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

const ABSOLUTE = /^(?:\/|[A-Za-z]:[/\\])/;
const DRIVE = /^([A-Za-z]):(?:\/|$)/;

/**
 * The nodes a target names when it is not an id or a symbol as written: a path spelled another way.
 * Empty when it names none. Throws for an absolute path outside the project folder.
 */
function respelled(files: PairsDocument, target: string, root: string | undefined): string[] {
  let path = target;
  if (root !== undefined && ABSOLUTE.test(target)) {
    const relative = insideProject(target, root);
    if (relative === undefined) {
      throw new DependentsError(`"${target}" is outside the project folder ${root}`);
    }
    path = relative;
  }
  path = normalizePath(path);
  return path !== "" && files.hasNode(path) ? [path] : [];
}

/** Separators as `/`, repeated ones and `.` and `..` segments collapsed, a drive letter in upper case. */
function normalizePath(path: string): string {
  let rest = path.replaceAll("\\", "/").replace(/\/+/g, "/");
  let drive = "";
  const match = DRIVE.exec(rest);
  if (match) {
    drive = `${match[1]!.toUpperCase()}:`;
    rest = `/${rest.slice(2).replace(/^\/+/, "")}`;
  }
  const normal = rest === "" ? "" : posix.normalize(rest);
  return drive + (normal === "." ? "" : normal);
}

function realpath(path: string): string {
  try {
    return realpathSync(path);
  } catch {
    return path;
  }
}

/**
 * The project-relative form of an absolute path, or undefined when it is not inside `root`. Symbolic
 * links are resolved on both sides as well, so either spelling of the folder works.
 */
function insideProject(path: string, root: string): string | undefined {
  const roots = new Set([normalizePath(root), normalizePath(realpath(root))]);
  const paths = new Set([normalizePath(path), normalizePath(realpath(path))]);
  for (const candidate of [...paths].sort(compareText)) {
    for (const base of [...roots].sort(compareText)) {
      const folder = base.replace(/\/+$/, "");
      if (candidate === folder) {
        return ".";
      }
      if (candidate.startsWith(`${folder}/`)) {
        return candidate.slice(folder.length + 1);
      }
    }
  }
  return undefined;
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
