// SPDX-License-Identifier: MIT
// The pairs document from spec/pairs-format.md: nodes plus merged (from, to) edges.

import { compareText } from "./text.js";
import { NAME, SPEC, VERSION } from "./version.js";
import { warningDiagnostic, type Diagnostic } from "./diagnostics.js";

export const INTERNAL = "internal";
export const EXTERNAL = "external";
export const BUILTIN = "builtin";
export const UNRESOLVED = "unresolved";
export const CLUSTER = "cluster";

export interface Node {
  id: string;
  kind: string;
  [extra: string]: unknown;
}

export interface Edge {
  from: string;
  to: string;
  kinds: string[];
  count: number;
}

/** A pairs document that cannot be read. */
export class DocumentError extends Error {}

export class PairsDocument {
  private readonly nodeMap = new Map<string, Node>();
  private readonly edgeMap = new Map<string, { from: string; to: string; kinds: Set<string>; count: number }>();

  constructor(readonly language: string) {}

  /** Adds a node unless one with that id exists. Extra fields (module, symbols) follow id and kind. */
  addNode(id: string, kind: string, extra: Record<string, unknown> = {}): void {
    if (!this.nodeMap.has(id)) {
      this.nodeMap.set(id, { id, kind, ...extra });
    }
  }

  /**
   * Reads a pairs document, such as one written by `untangled scan` or by another library.
   * A different minor version is read with a warning; a different major version is an error.
   */
  static fromObject(data: unknown, warnings: string[] = [], diagnostics: Diagnostic[] = []): PairsDocument {
    const object = isObject(data) ? data : {};
    if (object.format !== "untangled-pairs") {
      throw new DocumentError('not an Untangled pairs document (expected "format": "untangled-pairs")');
    }
    const version = typeof object.version === "string" ? object.version : "";
    const [major, minor = ""] = splitOnce(version);
    const [knownMajor, knownMinor] = splitOnce(SPEC);
    if (major !== knownMajor) {
      throw new DocumentError(`unsupported pairs document version "${version}" (this library reads ${SPEC})`);
    }
    if (minor !== knownMinor) {
      const message = `pairs document version ${version} is newer or older than ${SPEC}; reading it anyway`;
      warnings.push(message);
      diagnostics.push(warningDiagnostic("document-version", message));
    }
    if (typeof object.language !== "string" || !Array.isArray(object.nodes) || !Array.isArray(object.edges)) {
      throw new DocumentError('pairs document needs "language", "nodes" and "edges"');
    }
    const document = new PairsDocument(object.language);
    for (const node of object.nodes as unknown[]) {
      if (!isObject(node) || typeof node.id !== "string" || typeof node.kind !== "string") {
        throw new DocumentError('every node needs a string "id" and "kind"');
      }
      const { id, kind, ...extra } = node;
      document.addNode(id, kind, extra);
    }
    for (const edge of object.edges as unknown[]) {
      if (!isObject(edge) || typeof edge.from !== "string" || typeof edge.to !== "string") {
        throw new DocumentError('every edge needs a string "from" and "to"');
      }
      if (!document.hasNode(edge.from) || !document.hasNode(edge.to)) {
        throw new DocumentError(`edge ${edge.from} -> ${edge.to} names a node that is not in the document`);
      }
      const kinds = (Array.isArray(edge.kinds) ? edge.kinds : [edge.kinds]).filter((kind): kind is string => typeof kind === "string");
      const count = Math.trunc(Number(edge.count ?? 1));
      document.addEdge(edge.from, edge.to, kinds, Number.isFinite(count) ? Math.max(1, count) : 1);
    }
    return document;
  }

  hasNode(id: string): boolean {
    return this.nodeMap.has(id);
  }

  node(id: string): Node | undefined {
    return this.nodeMap.get(id);
  }

  /** Records references; repeated ones merge their kinds and add up. Self-edges are dropped. */
  addEdge(from: string, to: string, kinds: Iterable<string>, count = 1): void {
    if (from === to) {
      return;
    }
    const key = JSON.stringify([from, to]);
    const edge = this.edgeMap.get(key) ?? { from, to, kinds: new Set<string>(), count: 0 };
    for (const kind of kinds) {
      edge.kinds.add(kind);
    }
    edge.count += count;
    this.edgeMap.set(key, edge);
  }

  nodes(): Node[] {
    return [...this.nodeMap.values()].sort((a, b) => compareText(a.id, b.id));
  }

  edges(): Edge[] {
    return [...this.edgeMap.values()]
      .sort((a, b) => compareText(a.from, b.from) || compareText(a.to, b.to))
      .map((edge) => ({ from: edge.from, to: edge.to, kinds: [...edge.kinds].sort(compareText), count: edge.count }));
  }

  toObject(): Record<string, unknown> {
    return {
      format: "untangled-pairs",
      version: SPEC,
      language: this.language,
      generator: { name: NAME, version: VERSION },
      nodes: this.nodes(),
      edges: this.edges(),
    };
  }

  toJson(): string {
    return encode(this.toObject());
  }

  /**
   * snakefood's line format: ((root, from), (root, to)), and ((root, file), (None, None)) for
   * files without internal dependencies. Only internal nodes (or clusters) are written.
   */
  toSnakefood(root: string): string {
    const isUnit = (id: string): boolean => {
      const kind = this.nodeMap.get(id)?.kind;
      return kind === INTERNAL || kind === CLUSTER;
    };
    const quote = (text: string): string => `'${text.replaceAll("\\", "\\\\").replaceAll("'", "\\'")}'`;
    const lines: string[] = [];
    const hasDependencies = new Set<string>();
    for (const edge of this.edges()) {
      if (!isUnit(edge.to)) {
        continue;
      }
      hasDependencies.add(edge.from);
      lines.push(`((${quote(root)}, ${quote(edge.from)}), (${quote(root)}, ${quote(edge.to)}))`);
    }
    for (const node of this.nodes()) {
      if (isUnit(node.id) && !hasDependencies.has(node.id)) {
        lines.push(`((${quote(root)}, ${quote(node.id)}), (None, None))`);
      }
    }
    lines.sort(compareText);
    return lines.map((line) => line + "\n").join("");
  }
}

/** Writes a document the way the spec asks: two-space indentation and a trailing newline. */
export function encode(document: unknown): string {
  return JSON.stringify(document, null, 2) + "\n";
}

/**
 * Rounds a metric to 4 decimal places, half away from zero on its shortest decimal form (so
 * 0.12345 is 0.1235, as in the other libraries). Metrics are never negative.
 */
export function number(value: number): number {
  const text = String(value);
  if (text.includes("e")) {
    // Below 1e-6, or a whole number beyond 1e21.
    return value < 1 ? 0 : value;
  }
  return Number(`${Math.round(Number(`${text}e4`))}e-4`);
}

function splitOnce(version: string): [string, string?] {
  const dot = version.indexOf(".");
  return dot === -1 ? [version] : [version.slice(0, dot), version.slice(dot + 1)];
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
