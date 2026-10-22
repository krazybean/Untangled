// SPDX-License-Identifier: MIT
// Writes the unit graph as Graphviz DOT, byte for byte as spec/report.md describes, so it can be
// rendered with `dot -Tsvg` or opened in any Graphviz viewer. Two styles: the default one, and
// `classic`, the black and white look of snakefood's sfood-graph.

import type { Unit } from "../analysis/analyzer.js";
import { EXTERNAL, UNRESOLVED } from "../graph.js";
import type { Report } from "./report.js";

/** The status colour for cycles, shared with the HTML report. */
export const CYCLE_COLOR = "#d03b3b";

export const STYLES = ["default", "classic"];

export function renderDot(report: Report, style = "default"): string {
  if (style === "classic") {
    return classic(report);
  }
  const clustered = report.isClustered();
  const cycleOf = report.cycleOf();
  const lines = [
    "digraph untangled {",
    '  graph [layout=dot, rankdir=LR, fontname="Helvetica"];',
    '  node [shape=box, style=rounded, fontname="Helvetica"];',
    '  edge [color="#898781"];',
  ];
  if (report.analysis.units.length) {
    lines.push("");
  }
  const highlight = `color="${CYCLE_COLOR}", penwidth=2`;
  for (const unit of report.analysis.units) {
    const attributes: string[] = [];
    if (clustered) {
      attributes.push(label(unit));
    }
    if (cycleOf.has(unit.id)) {
      attributes.push(highlight);
    }
    lines.push(`  ${quote(unit.id)}${list(attributes)};`);
  }
  const edges = report.unitEdges();
  if (edges.length) {
    lines.push("");
  }
  for (const edge of edges) {
    lines.push(`  ${quote(edge.from)} -> ${quote(edge.to)}${list(edge.cycle ? [highlight] : [])};`);
  }
  lines.push("}");
  return lines.join("\n") + "\n";
}

/**
 * sfood-graph's look: grey ellipses for the project's units, white ones for the external packages
 * and unresolved references they use, plain black edges, small serif labels.
 */
function classic(report: Report): string {
  const clustered = report.isClustered();
  const lines = [
    "digraph untangled {",
    "  graph [layout=dot, rankdir=LR];",
    '  node [shape=ellipse, style=filled, fillcolor=lightgrey, fontname="Times-Roman", fontsize=7];',
    "  edge [color=black];",
  ];
  const units = new Set<string>();
  const nodes: string[] = [];
  for (const unit of report.analysis.units) {
    units.add(unit.id);
    nodes.push(`  ${quote(unit.id)}${clustered ? ` [${label(unit)}]` : ""};`);
  }
  const outside = new Map<string, boolean>();
  for (const node of report.graph.nodes()) {
    if (node.kind === EXTERNAL || node.kind === UNRESOLVED) {
      outside.set(node.id, false);
    }
  }
  const edges: string[] = [];
  for (const edge of report.graph.edges()) {
    if (!units.has(edge.from) || !(units.has(edge.to) || outside.has(edge.to))) {
      continue;
    }
    if (outside.has(edge.to)) {
      outside.set(edge.to, true);
    }
    edges.push(`  ${quote(edge.from)} -> ${quote(edge.to)};`);
  }
  for (const [id, used] of outside) {
    if (used) {
      nodes.push(`  ${quote(id)} [fillcolor=white];`);
    }
  }
  for (const block of [nodes, edges]) {
    if (block.length) {
      lines.push("", ...block);
    }
  }
  lines.push("}");
  return lines.join("\n") + "\n";
}

/**
 * A DOT quoted string. Backslashes are doubled so namespace separators survive as ids and as
 * labels; a newline becomes DOT's centred line break.
 */
export function quote(text: string): string {
  return `"${text.replaceAll("\\", "\\\\").replaceAll('"', '\\"').replaceAll("\n", "\\n")}"`;
}

function label(unit: Unit): string {
  const files = unit.members?.length ?? 0;
  return `label=${quote(`${unit.id}\n${files}${files === 1 ? " file" : " files"}`)}`;
}

function list(attributes: string[]): string {
  return attributes.length ? ` [${attributes.join(", ")}]` : "";
}
