// SPDX-License-Identifier: MIT
// Everything a report shows (spec/report.md): the analysis document plus the unit graph it was
// computed on, so renderers can draw edges and name the packages and references behind the counts.

import { analyze, type Analysis } from "../analysis/analyzer.js";
import type { Clustering } from "../analysis/clustering.js";
import { INTERNAL, type PairsDocument } from "../graph.js";
import { compareText, sortText } from "../text.js";

export interface UnitEdge {
  from: string;
  to: string;
  count: number;
  /** Both ends are in the same cycle, so the edge is part of the loop. */
  cycle: boolean;
}

export class Report {
  private constructor(
    readonly title: string,
    readonly analysis: Analysis,
    /** The unit graph: the filtered file graph, or its clustered form. */
    readonly graph: PairsDocument,
    /** Per cluster, how many file edges fell inside it. */
    readonly dropped: Map<string, number>,
    /** The files the scanner could not read, sorted, each with its `error` ("parse" or "read"). */
    readonly unread: Map<string, string>,
  ) {}

  /** `files` is a filtered file-level pairs document. */
  static build(title: string, files: PairsDocument, clustering?: Clustering): Report {
    const analysis = analyze(files, clustering);
    const clustered = clustering?.apply(files);
    const unread = new Map<string, string>();
    for (const node of files.nodes()) {
      if (node.kind === INTERNAL && typeof node.error === "string") {
        unread.set(node.id, node.error);
      }
    }
    return new Report(title, analysis, clustered?.document ?? files, clustered?.dropped ?? new Map(), unread);
  }

  isClustered(): boolean {
    return this.analysis.clustering !== null;
  }

  /** Each unit in a cycle, mapped to the cycle's position (from 1). */
  cycleOf(): Map<string, number> {
    const cycleOf = new Map<string, number>();
    this.analysis.cycles.forEach((cycle, index) => {
      for (const member of cycle.members) {
        cycleOf.set(member, index + 1);
      }
    });
    return cycleOf;
  }

  /** Edges between two units, in document order. */
  unitEdges(): UnitEdge[] {
    const units = new Set(this.analysis.units.map((unit) => unit.id));
    const cycleOf = this.cycleOf();
    return this.graph
      .edges()
      .filter((edge) => units.has(edge.from) && units.has(edge.to))
      .map((edge) => ({
        from: edge.from,
        to: edge.to,
        count: edge.count,
        cycle: cycleOf.has(edge.from) && cycleOf.get(edge.to) === cycleOf.get(edge.from),
      }));
  }

  /**
   * The units the map draws (spec/report.md): all of them up to `limit`, else the `limit` with
   * the most connections (fan-in plus fan-out, ties by id), in the order of the analysis.
   */
  mapUnits(limit: number): string[] {
    const units = this.analysis.units;
    if (units.length <= limit) {
      return units.map((unit) => unit.id);
    }
    const ranked = [...units].sort((a, b) => b.fan_in + b.fan_out - (a.fan_in + a.fan_out) || compareText(a.id, b.id));
    const keep = new Set(ranked.slice(0, limit).map((unit) => unit.id));
    return units.map((unit) => unit.id).filter((id) => keep.has(id));
  }

  /** The external or unresolved nodes the units depend on, the most used first (ties by id), with their sorted users. */
  targets(kind: string): Map<string, string[]> {
    const users = new Map<string, string[]>();
    for (const node of this.graph.nodes()) {
      if (node.kind === kind) {
        users.set(node.id, []);
      }
    }
    for (const edge of this.graph.edges()) {
      users.get(edge.to)?.push(edge.from);
    }
    const sorted = [...users].map(([id, ids]) => [id, sortText(ids)] as [string, string[]]);
    sorted.sort((a, b) => b[1].length - a[1].length || compareText(a[0], b[0]));
    return new Map(sorted);
  }
}
