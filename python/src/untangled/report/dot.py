# SPDX-License-Identifier: GPL-2.0-only
"""Writes the unit graph as Graphviz DOT, byte for byte as spec/report.md describes. Two styles:
the default one, and `classic`, the black and white look of snakefood's sfood-graph."""

from typing import Any

from untangled.graph import EXTERNAL, UNRESOLVED
from untangled.report.report import Report

CYCLE_COLOR = "#d03b3b"
"""The status colour for cycles, shared with the HTML report."""

STYLES = ("default", "classic")


def render(report: Report, style: str = "default") -> str:
    if style == "classic":
        return _classic(report)
    clustered = report.is_clustered()
    cycle_of = report.cycle_of()
    lines = [
        "digraph untangled {",
        '  graph [layout=dot, rankdir=LR, fontname="Helvetica"];',
        '  node [shape=box, style=rounded, fontname="Helvetica"];',
        '  edge [color="#898781"];',
    ]
    if report.analysis["units"]:
        lines.append("")
    highlight = f'color="{CYCLE_COLOR}", penwidth=2'
    for unit in report.analysis["units"]:
        attributes = []
        if clustered:
            attributes.append(_label(unit))
        if unit["id"] in cycle_of:
            attributes.append(highlight)
        lines.append(f"  {quote(unit['id'])}{_attributes(attributes)};")
    edges = report.unit_edges()
    if edges:
        lines.append("")
    for edge in edges:
        lines.append(
            f"  {quote(edge['from'])} -> {quote(edge['to'])}{_attributes([highlight] if edge['cycle'] else [])};"
        )
    lines.append("}")
    return "\n".join(lines) + "\n"


def _classic(report: Report) -> str:
    """sfood-graph's look: grey ellipses for the project's units, white ones for the external
    packages and unresolved references they use, plain black edges, small serif labels."""
    clustered = report.is_clustered()
    lines = [
        "digraph untangled {",
        "  graph [layout=dot, rankdir=LR];",
        '  node [shape=ellipse, style=filled, fillcolor=lightgrey, fontname="Times-Roman", fontsize=7];',
        "  edge [color=black];",
    ]
    units = set()
    nodes = []
    for unit in report.analysis["units"]:
        units.add(unit["id"])
        nodes.append(f"  {quote(unit['id'])}{f' [{_label(unit)}]' if clustered else ''};")
    outside = {node["id"]: False for node in report.graph.nodes() if node["kind"] in (EXTERNAL, UNRESOLVED)}
    edges = []
    for edge in report.graph.edges():
        if edge["from"] not in units or (edge["to"] not in units and edge["to"] not in outside):
            continue
        if edge["to"] in outside:
            outside[edge["to"]] = True
        edges.append(f"  {quote(edge['from'])} -> {quote(edge['to'])};")
    nodes += [f"  {quote(node_id)} [fillcolor=white];" for node_id, used in outside.items() if used]
    for block in (nodes, edges):
        if block:
            lines += ["", *block]
    lines.append("}")
    return "\n".join(lines) + "\n"


def quote(text: str) -> str:
    """A DOT quoted string. Backslashes are doubled so namespace separators survive as ids and
    as labels; a newline becomes DOT's centred line break."""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def _label(unit: dict[str, Any]) -> str:
    files = len(unit["members"])
    return "label=" + quote(f"{unit['id']}\n{files} {'file' if files == 1 else 'files'}")


def _attributes(attributes: list[str]) -> str:
    return f" [{', '.join(attributes)}]" if attributes else ""
