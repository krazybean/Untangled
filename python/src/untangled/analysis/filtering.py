# SPDX-License-Identifier: GPL-2.0-only
"""The filtering step of spec/clustering.md: drops builtin nodes (unless kept), then applies
ordered include / exclude globs to internal ids, where the last matching pattern wins."""

import re

from untangled.graph import BUILTIN, CLUSTER, INTERNAL, PairsDocument


class Glob:
    """`*` and `?` stay within one path segment, `**` matches across `/`, and `**` followed
    by `/` also matches no directory at all."""

    def __init__(self, pattern: str) -> None:
        self.pattern = pattern
        regex = ""
        i = 0
        while i < len(pattern):
            char = pattern[i]
            if pattern.startswith("**/", i):
                regex += "(?:.*/)?"
                i += 3
                continue
            if pattern.startswith("**", i):
                regex += ".*"
                i += 2
                continue
            regex += "[^/]*" if char == "*" else "[^/]" if char == "?" else re.escape(char)
            i += 1
        self._regex = re.compile(regex, re.DOTALL)

    def matches(self, node_id: str) -> bool:
        return self._regex.fullmatch(node_id) is not None


class Filter:
    def __init__(self, keep_builtins: bool = False) -> None:
        self.keep_builtins = keep_builtins
        self._patterns: list[tuple[bool, Glob]] = []

    def include(self, pattern: str) -> "Filter":
        self._patterns.append((True, Glob(pattern)))
        return self

    def exclude(self, pattern: str) -> "Filter":
        self._patterns.append((False, Glob(pattern)))
        return self

    def keeps(self, internal_id: str) -> bool:
        keep = True
        for include, glob in self._patterns:
            if glob.matches(internal_id):
                keep = include
        return keep

    def apply(self, document: PairsDocument) -> PairsDocument:
        """Returns the filtered document. Removing a node removes its edges, and a non-internal
        node that no remaining edge points to is removed with them."""
        kept = {}
        for node in document.nodes():
            if node["kind"] == BUILTIN and not self.keep_builtins:
                continue
            if node["kind"] == INTERNAL and not self.keeps(node["id"]):
                continue
            kept[node["id"]] = node
        edges = [edge for edge in document.edges() if edge["from"] in kept and edge["to"] in kept]
        targets = {edge["to"] for edge in edges}
        filtered = PairsDocument(document.language)
        for node_id, node in kept.items():
            # Cluster nodes pass through so that the analyzer can refuse an already clustered document.
            if node["kind"] in (INTERNAL, CLUSTER) or node_id in targets:
                filtered.add_node(node_id, node["kind"], **{k: v for k, v in node.items() if k not in ("id", "kind")})
        for edge in edges:
            filtered.add_edge(edge["from"], edge["to"], edge["kinds"], edge["count"])
        return filtered
