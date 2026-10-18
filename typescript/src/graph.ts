// SPDX-License-Identifier: MIT
// The pairs document from spec/pairs-format.md: nodes plus merged (from, to) edges.

import { compareText } from "./text.js";
import { NAME, SPEC, VERSION } from "./version.js";

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
