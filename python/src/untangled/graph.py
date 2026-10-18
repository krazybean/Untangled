# SPDX-License-Identifier: GPL-2.0-only
"""The pairs document from spec/pairs-format.md: nodes plus merged (from, to) edges."""

import json
from collections.abc import Iterable
from typing import Any

from untangled import version

INTERNAL = "internal"
EXTERNAL = "external"
BUILTIN = "builtin"
UNRESOLVED = "unresolved"
CLUSTER = "cluster"


class PairsDocument:
    def __init__(self, language: str) -> None:
        self.language = language
        self._nodes: dict[str, dict[str, Any]] = {}
        self._edges: dict[tuple[str, str], tuple[set[str], int]] = {}

    def add_node(self, node_id: str, kind: str, **extra: Any) -> None:
        """Adds a node unless one with that id exists. Extra fields (module, symbols) follow id and kind."""
        self._nodes.setdefault(node_id, {"id": node_id, "kind": kind, **extra})

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    def node(self, node_id: str) -> dict[str, Any] | None:
        return self._nodes.get(node_id)

    def add_edge(self, source: str, target: str, kinds: Iterable[str], count: int = 1) -> None:
        """Records references; repeated ones merge their kinds and add up. Self-edges are dropped."""
        if source == target:
            return
        merged, total = self._edges.get((source, target), (set(), 0))
        merged.update(kinds)
        self._edges[(source, target)] = (merged, total + count)

    def nodes(self) -> list[dict[str, Any]]:
        # Python compares strings by code point, which is the byte order of their UTF-8.
        return [self._nodes[node_id] for node_id in sorted(self._nodes)]

    def edges(self) -> list[dict[str, Any]]:
        return [
            {"from": source, "to": target, "kinds": sorted(kinds), "count": count}
            for (source, target), (kinds, count) in sorted(self._edges.items())
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "untangled-pairs",
            "version": version.SPEC,
            "language": self.language,
            "generator": {"name": version.NAME, "version": version.VERSION},
            "nodes": self.nodes(),
            "edges": self.edges(),
        }

    def to_json(self) -> str:
        return encode(self.to_dict())

    def to_snakefood(self, root: str) -> str:
        """snakefood's line format: ((root, from), (root, to)), and ((root, file), (None, None))
        for files without internal dependencies. Only internal nodes (or clusters) are written."""

        def is_unit(node_id: str) -> bool:
            return self._nodes.get(node_id, {}).get("kind") in (INTERNAL, CLUSTER)

        def quote(text: str) -> str:
            return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"

        lines = []
        has_deps = set()
        for edge in self.edges():
            if not is_unit(edge["to"]):
                continue
            has_deps.add(edge["from"])
            lines.append(f"(({quote(root)}, {quote(edge['from'])}), ({quote(root)}, {quote(edge['to'])}))")
        for node in self.nodes():
            if is_unit(node["id"]) and node["id"] not in has_deps:
                lines.append(f"(({quote(root)}, {quote(node['id'])}), (None, None))")
        lines.sort(key=lambda line: line.encode())
        return "".join(line + "\n" for line in lines)


def encode(document: dict[str, Any]) -> str:
    """Writes a document the way the spec asks: two-space indentation and a trailing newline."""
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"
