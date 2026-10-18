# SPDX-License-Identifier: GPL-2.0-only
"""Everything a report shows (spec/report.md): the analysis document plus the unit graph it was
computed on, so renderers can draw edges and name the packages and references behind the counts."""

from dataclasses import dataclass, field
from typing import Any

from untangled.analysis.analyzer import analyze
from untangled.analysis.clustering import Clustering
from untangled.graph import PairsDocument


@dataclass
class Report:
    title: str
    analysis: dict[str, Any]
    graph: PairsDocument
    """The unit graph: the filtered file graph, or its clustered form."""
    dropped: dict[str, int] = field(default_factory=dict)
    """Per cluster, how many file edges fell inside it."""

    @classmethod
    def build(cls, title: str, files: PairsDocument, clustering: Clustering | None = None) -> "Report":
        """`files` is a filtered file-level pairs document. Raises ValueError when it is already clustered."""
        analysis = analyze(files, clustering)
        if clustering is None:
            return cls(title, analysis, files)
        clustered = clustering.apply(files)
        return cls(title, analysis, clustered.document, clustered.dropped)

    def is_clustered(self) -> bool:
        return self.analysis["clustering"] is not None

    def cycle_of(self) -> dict[str, int]:
        """Each unit in a cycle, mapped to the cycle's position (from 1)."""
        return {
            member: number for number, cycle in enumerate(self.analysis["cycles"], 1) for member in cycle["members"]
        }

    def unit_edges(self) -> list[dict[str, Any]]:
        """Edges between two units, in document order. `cycle` is true when both ends are in the
        same cycle, so the edge is part of the loop."""
        units = {unit["id"] for unit in self.analysis["units"]}
        cycle_of = self.cycle_of()
        return [
            {
                "from": edge["from"],
                "to": edge["to"],
                "count": edge["count"],
                "cycle": edge["from"] in cycle_of and cycle_of.get(edge["to"]) == cycle_of[edge["from"]],
            }
            for edge in self.graph.edges()
            if edge["from"] in units and edge["to"] in units
        ]

    def map_units(self, limit: int) -> list[str]:
        """The units the map draws: all of them up to `limit`, else the `limit` with the most
        connections (fan-in plus fan-out, ties by id), in the order of the analysis."""
        units = self.analysis["units"]
        if len(units) <= limit:
            return [unit["id"] for unit in units]
        ranked = sorted(units, key=lambda unit: (-(unit["fan_in"] + unit["fan_out"]), unit["id"]))
        keep = {unit["id"] for unit in ranked[:limit]}
        return [unit["id"] for unit in units if unit["id"] in keep]

    def targets(self, kind: str) -> dict[str, list[str]]:
        """The external or unresolved nodes the units depend on, each with the sorted units that
        use it, the most used first, ties by node id."""
        users: dict[str, list[str]] = {node["id"]: [] for node in self.graph.nodes() if node["kind"] == kind}
        for edge in self.graph.edges():
            if edge["to"] in users:
                users[edge["to"]].append(edge["from"])
        ranked = sorted(users, key=lambda node_id: (-len(users[node_id]), node_id))
        return {node_id: sorted(users[node_id]) for node_id in ranked}
