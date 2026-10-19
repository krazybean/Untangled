// SPDX-License-Identifier: MIT
// The filtering step of spec/clustering.md: drops builtin nodes (unless kept), then applies
// ordered include / exclude globs to internal ids, where the last matching pattern wins.

import { BUILTIN, CLUSTER, INTERNAL, PairsDocument, type Node } from "../graph.js";
import { Glob } from "./glob.js";

export class Filter {
  private readonly patterns: { include: boolean; glob: Glob }[] = [];

  constructor(private readonly keepBuiltins = false) {}

  include(pattern: string): this {
    this.patterns.push({ include: true, glob: new Glob(pattern) });
    return this;
  }

  exclude(pattern: string): this {
    this.patterns.push({ include: false, glob: new Glob(pattern) });
    return this;
  }

  keeps(internalId: string): boolean {
    let keep = true;
    for (const pattern of this.patterns) {
      if (pattern.glob.matches(internalId)) {
        keep = pattern.include;
      }
    }
    return keep;
  }

  /**
   * The filtered document. Removing a node removes its edges, and a node that is not internal
   * and that no remaining edge points to is removed with them.
   */
  apply(document: PairsDocument): PairsDocument {
    const kept = new Map<string, Node>();
    for (const node of document.nodes()) {
      if (node.kind === BUILTIN && !this.keepBuiltins) {
        continue;
      }
      if (node.kind === INTERNAL && !this.keeps(node.id)) {
        continue;
      }
      kept.set(node.id, node);
    }

    const edges = document.edges().filter((edge) => kept.has(edge.from) && kept.has(edge.to));
    const targets = new Set(edges.map((edge) => edge.to));

    const filtered = new PairsDocument(document.language);
    for (const [id, node] of kept) {
      // Cluster nodes pass through so that the analyzer can refuse an already clustered document.
      if (node.kind === INTERNAL || node.kind === CLUSTER || targets.has(id)) {
        const { id: _id, kind, ...extra } = node;
        filtered.addNode(id, kind, extra);
      }
    }
    for (const edge of edges) {
      filtered.addEdge(edge.from, edge.to, edge.kinds, edge.count);
    }
    return filtered;
  }
}
