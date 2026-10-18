# SPDX-License-Identifier: GPL-2.0-only
import json

from untangled.graph import BUILTIN, INTERNAL, UNRESOLVED, PairsDocument, encode


def sample() -> PairsDocument:
    pairs = PairsDocument("python")
    pairs.add_node("src/b.py", INTERNAL, module="b")
    pairs.add_node("src/a.py", INTERNAL, module="a")
    pairs.add_node("src/c.py", INTERNAL)
    pairs.add_node("builtin:os", BUILTIN)
    pairs.add_node("unresolved:module:x", UNRESOLVED)
    pairs.add_edge("src/a.py", "src/b.py", ["import"])
    pairs.add_edge("src/a.py", "src/b.py", ["from", "local"], 2)
    pairs.add_edge("src/a.py", "builtin:os", ["import"])
    pairs.add_edge("src/b.py", "unresolved:module:x", ["from"])
    return pairs


def test_nodes_are_sorted_and_keep_their_fields() -> None:
    assert sample().nodes() == [
        {"id": "builtin:os", "kind": "builtin"},
        {"id": "src/a.py", "kind": "internal", "module": "a"},
        {"id": "src/b.py", "kind": "internal", "module": "b"},
        {"id": "src/c.py", "kind": "internal"},
        {"id": "unresolved:module:x", "kind": "unresolved"},
    ]


def test_a_node_is_added_once() -> None:
    pairs = PairsDocument("python")
    pairs.add_node("a.py", INTERNAL, module="a")
    pairs.add_node("a.py", INTERNAL, module="other")
    assert pairs.node("a.py") == {"id": "a.py", "kind": "internal", "module": "a"}
    assert pairs.has_node("a.py") and not pairs.has_node("b.py")


def test_edges_merge_kinds_and_counts_and_are_sorted() -> None:
    assert sample().edges() == [
        {"from": "src/a.py", "to": "builtin:os", "kinds": ["import"], "count": 1},
        {"from": "src/a.py", "to": "src/b.py", "kinds": ["from", "import", "local"], "count": 3},
        {"from": "src/b.py", "to": "unresolved:module:x", "kinds": ["from"], "count": 1},
    ]


def test_self_edges_are_dropped() -> None:
    pairs = PairsDocument("python")
    pairs.add_node("a.py", INTERNAL)
    pairs.add_edge("a.py", "a.py", ["import"])
    assert pairs.edges() == []


def test_sorting_is_by_code_point_which_is_utf8_byte_order() -> None:
    pairs = PairsDocument("python")
    for node_id in ["é.py", "z.py", "Z.py", "€.py"]:
        pairs.add_node(node_id, INTERNAL)
    ids = [node["id"] for node in pairs.nodes()]
    assert ids == sorted(ids, key=str.encode) == ["Z.py", "z.py", "é.py", "€.py"]


def test_document_header() -> None:
    document = sample().to_dict()
    assert document["format"] == "untangled-pairs"
    assert document["version"] == "0.1"
    assert document["language"] == "python"
    assert document["generator"]["name"] == "untangled-python"


def test_json_has_two_space_indentation_unescaped_text_and_a_trailing_newline() -> None:
    text = encode({"id": "src/café.py", "list": [1]})
    assert text == '{\n  "id": "src/café.py",\n  "list": [\n    1\n  ]\n}\n'
    assert json.loads(sample().to_json())["edges"][1]["count"] == 3


def test_snakefood_format() -> None:
    assert sample().to_snakefood("/p") == (
        "(('/p', 'src/a.py'), ('/p', 'src/b.py'))\n"
        "(('/p', 'src/b.py'), (None, None))\n"
        "(('/p', 'src/c.py'), (None, None))\n"
    )


def test_snakefood_quotes_backslashes_and_quotes() -> None:
    pairs = PairsDocument("python")
    pairs.add_node("it's.py", INTERNAL)
    assert pairs.to_snakefood("C:\\p") == "(('C:\\\\p', 'it\\'s.py'), (None, None))\n"


def test_snakefood_of_an_empty_document_is_empty() -> None:
    assert PairsDocument("python").to_snakefood(".") == ""
