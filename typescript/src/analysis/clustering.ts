// SPDX-License-Identifier: MIT
// A clustering strategy from spec/clustering.md (`namespace:N`, `folder:N` or `rules`) and the
// step that applies it: one node per cluster, edges merged per (cluster, target), and edges
// inside a cluster dropped.

import { CLUSTER, INTERNAL, PairsDocument, type Node } from "../graph.js";
import { sortText } from "../text.js";

export interface Rule {
  prefix: string;
  cluster: string;
}

export interface Clustered {
  document: PairsDocument;
  /** Each internal id's cluster. */
  clusterOf: Map<string, string>;
  /** Per cluster, how many file edges fell inside it and were dropped, sorted by cluster. */
  dropped: Map<string, number>;
}

export class Clustering {
  private constructor(
    readonly strategy: "namespace" | "folder" | "rules",
    private readonly depth = 0,
    private readonly rules: Rule[] = [],
  ) {}

  static byNamespace(depth: number): Clustering {
    checkDepth(depth);
    return new Clustering("namespace", depth);
  }

  static byFolder(depth: number): Clustering {
    checkDepth(depth);
    return new Clustering("folder", depth);
  }

  /** Ordered rules: the first matching prefix wins. */
  static byRules(rules: Rule[]): Clustering {
    return new Clustering("rules", 0, rules);
  }

  /** Parses a rules file: one `prefix cluster` pair per line, `#` starts a comment. */
  static parseRules(text: string): Clustering {
    const rules: Rule[] = [];
    text.split(/\r\n|\n|\r/).forEach((raw, number) => {
      const line = raw.replace(/#.*/, "").trim();
      if (line === "") {
        return;
      }
      const fields = line.split(/\s+/);
      if (fields.length !== 2) {
        throw new Error(`rules line ${number + 1} must be "<prefix> <cluster>"`);
      }
      rules.push({ prefix: fields[0]!, cluster: fields[1]! });
    });
    return Clustering.byRules(rules);
  }

  /** A strategy as written on the command line: `namespace:N` or `folder:N`. */
  static fromString(strategy: string): Clustering {
    const match = /^(namespace|folder):([1-9][0-9]*)$/.exec(strategy);
    if (match === null) {
      throw new Error(`unknown clustering "${strategy}" (use namespace:N, folder:N or rules:<file>)`);
    }
    const depth = Number(match[2]);
    return match[1] === "namespace" ? Clustering.byNamespace(depth) : Clustering.byFolder(depth);
  }

  /** The name written in the analysis document's `clustering` field. */
  name(): string {
    return this.strategy === "rules" ? "rules" : `${this.strategy}:${this.depth}`;
  }

  clusterOf(node: Node): string {
    const id = node.id;
    if (this.strategy === "rules") {
      return this.rules.find((rule) => id.startsWith(rule.prefix))?.cluster ?? id;
    }
    if (this.strategy === "namespace" && typeof node.module === "string" && node.module !== "") {
      // Segments are separated by `\` (PHP namespaces) or `.` (Python modules); the separators
      // are kept, so the cluster id reads like the module it shortens.
      return node.module
        .split(/([\\.])/)
        .slice(0, 2 * this.depth - 1)
        .join("");
    }
    const folders = id.split("/").slice(0, -1);
    return folders.length === 0 ? "." : folders.slice(0, this.depth).join("/");
  }

  /** Applies the strategy. Nodes that are not internal pass through unchanged. */
  apply(files: PairsDocument): Clustered {
    const clusterOf = new Map<string, string>();
    const members = new Map<string, string[]>();
    const others: Node[] = [];
    for (const node of files.nodes()) {
      if (node.kind === INTERNAL) {
        const cluster = this.clusterOf(node);
        clusterOf.set(node.id, cluster);
        members.set(cluster, [...(members.get(cluster) ?? []), node.id]);
      } else {
        others.push(node);
      }
    }

    const document = new PairsDocument(files.language);
    for (const [cluster, ids] of members) {
      document.addNode(cluster, CLUSTER, { members: sortText(ids) });
    }
    for (const node of others) {
      const { id, kind, ...extra } = node;
      document.addNode(id, kind, extra);
    }

    const dropped = new Map<string, number>();
    for (const edge of files.edges()) {
      const from = clusterOf.get(edge.from) ?? edge.from;
      const to = clusterOf.get(edge.to) ?? edge.to;
      if (from === to) {
        dropped.set(from, (dropped.get(from) ?? 0) + 1);
        continue;
      }
      document.addEdge(from, to, edge.kinds, edge.count);
    }
    return { document, clusterOf, dropped: new Map(sortText(dropped.keys()).map((key) => [key, dropped.get(key)!])) };
  }
}

function checkDepth(depth: number): void {
  if (depth < 1) {
    throw new Error("clustering depth must be at least 1");
  }
}
