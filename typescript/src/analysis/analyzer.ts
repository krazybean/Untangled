// SPDX-License-Identifier: MIT
// Computes the analysis document of spec/metrics.md from a filtered file-level pairs document:
// per-unit coupling, Ca / Ce for clusters, cycles, and the project summary.

import { CLUSTER, EXTERNAL, INTERNAL, number, UNRESOLVED, type PairsDocument } from "../graph.js";
import { compareText } from "../text.js";
import { NAME, SPEC, VERSION } from "../version.js";
import type { Clustering } from "./clustering.js";
import { findCycles, type Cycle } from "./cycles.js";

export interface Unit {
  id: string;
  fan_in: number;
  fan_out: number;
  ca?: number;
  ce?: number;
  external: number;
  unresolved: number;
  instability: number | null;
  members?: string[];
}

export interface Summary {
  units: number;
  edges: number;
  cycles: number;
  largest_cycle: number;
  units_in_cycles: number;
  units_in_cycles_ratio: number;
  mean_fan_out: number;
  external_packages: number;
  unresolved_references: number;
}

export interface Analysis {
  format: "untangled-analysis";
  version: string;
  language: string;
  generator: { name: string; version: string };
  clustering: string | null;
  summary: Summary;
  units: Unit[];
  cycles: Cycle[];
}

/** Thrown when the document is already clustered. */
export class AnalysisError extends Error {}

export function analyze(files: PairsDocument, clustering?: Clustering): Analysis {
  if (files.nodes().some((node) => node.kind === CLUSTER)) {
    throw new AnalysisError(
      "the pairs document is already clustered; analyze the file-level document and choose a clustering instead",
    );
  }
  const clustered = clustering?.apply(files);
  const graph = clustered?.document ?? files;
  const clusterOf = clustered?.clusterOf;

  const unitKind = clustering === undefined ? INTERNAL : CLUSTER;
  const successors = new Map<string, string[]>();
  const predecessors = new Map<string, string[]>();
  const external = new Map<string, Set<string>>();
  const unresolved = new Map<string, Set<string>>();
  const members = new Map<string, string[]>();
  for (const node of graph.nodes()) {
    if (node.kind === unitKind) {
      successors.set(node.id, []);
      predecessors.set(node.id, []);
      external.set(node.id, new Set());
      unresolved.set(node.id, new Set());
      members.set(node.id, (node.members as string[] | undefined) ?? []);
    }
  }

  let edges = 0;
  const externalUsed = new Set<string>();
  const unresolvedUsed = new Set<string>();
  for (const { from, to } of graph.edges()) {
    const kind = graph.node(to)?.kind;
    if (kind === unitKind) {
      successors.get(from)?.push(to);
      predecessors.get(to)?.push(from);
      edges++;
    } else if (kind === EXTERNAL) {
      external.get(from)?.add(to);
      externalUsed.add(to);
    } else if (kind === UNRESOLVED) {
      unresolved.get(from)?.add(to);
      unresolvedUsed.add(to);
    }
  }

  // Ca / Ce of a cluster count the distinct files outside it, on the file graph.
  const ca = new Map<string, Set<string>>();
  const ce = new Map<string, Set<string>>();
  if (clusterOf !== undefined) {
    for (const edge of files.edges()) {
      const from = clusterOf.get(edge.from);
      const to = clusterOf.get(edge.to);
      if (from === undefined || to === undefined || from === to) {
        continue;
      }
      ce.set(from, (ce.get(from) ?? new Set()).add(edge.to));
      ca.set(to, (ca.get(to) ?? new Set()).add(edge.from));
    }
  }

  const units: Unit[] = [];
  let fanOutTotal = 0;
  for (const [id, targets] of successors) {
    const fanIn = predecessors.get(id)!.length;
    const fanOut = targets.length;
    fanOutTotal += fanOut;
    const unit: Unit = { id, fan_in: fanIn, fan_out: fanOut } as Unit;
    let afferent = fanIn;
    let efferent = fanOut;
    if (clusterOf !== undefined) {
      afferent = ca.get(id)?.size ?? 0;
      efferent = ce.get(id)?.size ?? 0;
      unit.ca = afferent;
      unit.ce = efferent;
    }
    unit.external = external.get(id)!.size;
    unit.unresolved = unresolved.get(id)!.size;
    unit.instability = afferent + efferent === 0 ? null : number(efferent / (afferent + efferent));
    if (clusterOf !== undefined) {
      unit.members = members.get(id)!;
    }
    units.push(unit);
  }
  units.sort((a, b) => compareText(a.id, b.id));

  const cycles = findCycles(successors);
  const inCycles = cycles.reduce((sum, cycle) => sum + cycle.size, 0);
  const count = units.length;

  return {
    format: "untangled-analysis",
    version: SPEC,
    language: files.language,
    generator: { name: NAME, version: VERSION },
    clustering: clustering?.name() ?? null,
    summary: {
      units: count,
      edges,
      cycles: cycles.length,
      largest_cycle: cycles[0]?.size ?? 0,
      units_in_cycles: inCycles,
      units_in_cycles_ratio: count === 0 ? 0 : number(inCycles / count),
      mean_fan_out: count === 0 ? 0 : number(fanOutTotal / count),
      external_packages: externalUsed.size,
      unresolved_references: unresolvedUsed.size,
    },
    units,
    cycles,
  };
}
