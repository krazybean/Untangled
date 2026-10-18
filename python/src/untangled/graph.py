# SPDX-License-Identifier: GPL-2.0-only
"""The pairs document from spec/pairs-format.md: nodes plus merged (from, to) edges."""

import json
from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from untangled import version

INTERNAL = "internal"
EXTERNAL = "external"
BUILTIN = "builtin"
UNRESOLVED = "unresolved"
CLUSTER = "cluster"


class DocumentError(Exception):
    pass


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

    @classmethod
    def from_dict(cls, data: Any, warnings: list[str] | None = None) -> "PairsDocument":
        """Reads a pairs document, such as one written by `untangled scan` or by another library.
        A document with an unknown minor version is read with a warning."""
        if not isinstance(data, dict) or data.get("format") != "untangled-pairs":
            raise DocumentError('not an Untangled pairs document (expected "format": "untangled-pairs")')
        found = data.get("version") if isinstance(data.get("version"), str) else ""
        major, _, minor = found.partition(".")
        known_major, _, known_minor = version.SPEC.partition(".")
        if major != known_major:
            raise DocumentError(f'unsupported pairs document version "{found}" (this library reads {version.SPEC})')
        if minor != known_minor and warnings is not None:
            warnings.append(f"pairs document version {found} is newer or older than {version.SPEC}; reading it anyway")
        language, nodes, edges = data.get("language"), data.get("nodes"), data.get("edges")
        if not isinstance(language, str) or not isinstance(nodes, list) or not isinstance(edges, list):
            raise DocumentError('pairs document needs "language", "nodes" and "edges"')
        document = cls(language)
        for node in nodes:
            if not _has_strings(node, "id", "kind"):
                raise DocumentError('every node needs a string "id" and "kind"')
            document.add_node(node["id"], node["kind"], **{k: v for k, v in node.items() if k not in ("id", "kind")})
        for edge in edges:
            if not _has_strings(edge, "from", "to"):
                raise DocumentError('every edge needs a string "from" and "to"')
            if not document.has_node(edge["from"]) or not document.has_node(edge["to"]):
                raise DocumentError(f"edge {edge['from']} -> {edge['to']} names a node that is not in the document")
            kinds = edge.get("kinds", [])
            kinds = [kind for kind in (kinds if isinstance(kinds, list) else [kinds]) if isinstance(kind, str)]
            count = edge.get("count", 1)
            count = int(count) if isinstance(count, (int, float)) and not isinstance(count, bool) else 1
            document.add_edge(edge["from"], edge["to"], kinds, max(1, count))
        return document

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


def _has_strings(item: Any, *keys: str) -> bool:
    return isinstance(item, dict) and all(isinstance(item.get(key), str) for key in keys)


def number(value: float) -> int | float:
    """Rounds to 4 decimal places, half away from zero as the spec's other libraries do, and
    makes whole numbers integers so they are written without ".0"."""
    rounded = float(round_half_up(value, 4))
    return int(rounded) if rounded.is_integer() else rounded


def round_half_up(value: float, places: int) -> Decimal:
    # Through the shortest decimal form of the float, so 0.125 rounds to 0.13 as people expect.
    return Decimal(repr(float(value))).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def encode(document: dict[str, Any]) -> str:
    """Writes a document the way the spec asks: two-space indentation and a trailing newline."""
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"
