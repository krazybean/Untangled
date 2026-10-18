# SPDX-License-Identifier: GPL-2.0-only
"""A clustering strategy from spec/clustering.md (`namespace:N`, `folder:N` or `rules`) and the
step that applies it: one node per cluster, edges merged per (cluster, target), and edges
inside a cluster dropped."""

import re
from dataclasses import dataclass, field
from typing import Any

from untangled.graph import CLUSTER, INTERNAL, PairsDocument


@dataclass
class Clustered:
    document: PairsDocument
    cluster_of: dict[str, str]
    """Each internal id's cluster."""
    dropped: dict[str, int] = field(default_factory=dict)
    """Per cluster, how many file edges fell inside it and were dropped."""


class Clustering:
    def __init__(self, strategy: str, depth: int = 0, rules: list[tuple[str, str]] | None = None) -> None:
        if strategy in ("namespace", "folder") and depth < 1:
            raise ValueError("clustering depth must be at least 1")
        self.strategy = strategy
        self.depth = depth
        self.rules = rules or []

    @classmethod
    def from_string(cls, strategy: str) -> "Clustering":
        """A strategy as written on the command line: `namespace:N` or `folder:N`.
        (`rules` needs a rules file, so it is built with parse_rules().)"""
        match = re.fullmatch(r"(namespace|folder):([1-9][0-9]*)", strategy)
        if match is None:
            raise ValueError(f'unknown clustering "{strategy}" (use namespace:N, folder:N or rules:<file>)')
        return cls(match.group(1), int(match.group(2)))

    @classmethod
    def parse_rules(cls, text: str) -> "Clustering":
        """One `prefix cluster` pair per line, `#` starts a comment."""
        rules = []
        for number, line in enumerate(text.splitlines(), start=1):
            fields = line.split("#", 1)[0].split()
            if not fields:
                continue
            if len(fields) != 2:
                raise ValueError(f'rules line {number} must be "<prefix> <cluster>"')
            rules.append((fields[0], fields[1]))
        return cls("rules", rules=rules)

    def name(self) -> str:
        """The name written in the analysis document's `clustering` field."""
        return "rules" if self.strategy == "rules" else f"{self.strategy}:{self.depth}"

    def cluster_of(self, node: dict[str, Any]) -> str:
        node_id = node["id"]
        if self.strategy == "rules":
            for prefix, cluster in self.rules:
                if node_id.startswith(prefix):
                    return cluster
            return node_id
        module = node.get("module")
        if self.strategy == "namespace" and isinstance(module, str) and module:
            # Segments are separated by `\\` (PHP namespaces) or `.` (Python modules); the
            # separators are kept, so the cluster id reads like the module it shortens.
            parts = re.split(r"([\\\\.])", module)
            return "".join(parts[: 2 * self.depth - 1])
        folders = node_id.split("/")[:-1]
        return "/".join(folders[: self.depth]) if folders else "."

    def apply(self, files: PairsDocument) -> Clustered:
        cluster_of: dict[str, str] = {}
        members: dict[str, list[str]] = {}
        others = []
        for node in files.nodes():
            if node["kind"] == INTERNAL:
                cluster = self.cluster_of(node)
                cluster_of[node["id"]] = cluster
                members.setdefault(cluster, []).append(node["id"])
            else:
                others.append(node)
        document = PairsDocument(files.language)
        for cluster, ids in members.items():
            document.add_node(cluster, CLUSTER, members=sorted(ids))
        for node in others:
            document.add_node(node["id"], node["kind"], **{k: v for k, v in node.items() if k not in ("id", "kind")})
        dropped: dict[str, int] = {}
        for edge in files.edges():
            source = cluster_of.get(edge["from"], edge["from"])
            target = cluster_of.get(edge["to"], edge["to"])
            if source == target:
                dropped[source] = dropped.get(source, 0) + 1
                continue
            document.add_edge(source, target, edge["kinds"], edge["count"])
        return Clustered(document, cluster_of, dict(sorted(dropped.items())))
