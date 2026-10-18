# SPDX-License-Identifier: GPL-2.0-only
import json
from typing import Any

import pytest

from untangled import version
from untangled.graph import (
    BUILTIN,
    CLUSTER,
    INTERNAL,
    UNRESOLVED,
    DocumentError,
    PairsDocument,
    encode,
    number,
    round_half_up,
)


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


def minimal(**fields: Any) -> dict[str, Any]:
    return {
        "format": "untangled-pairs",
        "version": version.SPEC,
        "language": "python",
        "nodes": [],
        "edges": [],
    } | fields


def test_from_dict_round_trips() -> None:
    document = sample()
    assert PairsDocument.from_dict(document.to_dict()).to_dict() == document.to_dict()


def test_from_dict_keeps_cluster_nodes_and_their_members() -> None:
    data = minimal(nodes=[{"id": "app", "kind": CLUSTER, "members": ["a.py"]}])
    assert PairsDocument.from_dict(data).nodes() == [{"id": "app", "kind": "cluster", "members": ["a.py"]}]


def test_from_dict_defaults_a_missing_count_to_one() -> None:
    data = minimal(
        nodes=[{"id": "a.py", "kind": "internal"}, {"id": "b.py", "kind": "internal"}],
        edges=[{"from": "a.py", "to": "b.py", "kinds": ["import"]}],
    )
    assert PairsDocument.from_dict(data).edges()[0]["count"] == 1


def test_from_dict_merges_repeated_edges() -> None:
    data = minimal(
        nodes=[{"id": "a.py", "kind": "internal"}, {"id": "b.py", "kind": "internal"}],
        edges=[
            {"from": "a.py", "to": "b.py", "kinds": ["import"], "count": 2},
            {"from": "a.py", "to": "b.py", "kinds": ["from"], "count": 3},
        ],
    )
    assert PairsDocument.from_dict(data).edges() == [
        {"from": "a.py", "to": "b.py", "kinds": ["from", "import"], "count": 5}
    ]


def test_from_dict_warns_on_an_unknown_minor_version() -> None:
    warnings: list[str] = []
    PairsDocument.from_dict(minimal(version="0.99"), warnings)
    assert warnings == [f"pairs document version 0.99 is newer or older than {version.SPEC}; reading it anyway"]
    warnings = []
    PairsDocument.from_dict(minimal(), warnings)
    assert warnings == []


def test_from_dict_without_a_warnings_list_still_reads_an_unknown_minor_version() -> None:
    assert PairsDocument.from_dict(minimal(version="0.99")).language == "python"


def _without(key: str) -> dict[str, Any]:
    return {k: v for k, v in minimal().items() if k != key}


@pytest.mark.parametrize(
    ("data", "message"),
    [
        pytest.param(minimal(format="untangled-analysis"), "not an Untangled pairs document", id="another format"),
        pytest.param(_without("format"), "not an Untangled pairs document", id="no format"),
        pytest.param(["not", "a", "dict"], "not an Untangled pairs document", id="not an object"),
        pytest.param(minimal(version="1.0"), 'unsupported pairs document version "1.0"', id="unknown major version"),
        pytest.param(minimal(version=0.1), "unsupported pairs document version", id="version not a string"),
        pytest.param(_without("nodes"), 'needs "language", "nodes" and "edges"', id="no nodes"),
        pytest.param(_without("language"), 'needs "language", "nodes" and "edges"', id="no language"),
        pytest.param(
            minimal(nodes=[{"id": "a.py"}]), 'every node needs a string "id" and "kind"', id="node without kind"
        ),
        pytest.param(minimal(nodes=["a.py"]), "every node needs", id="node not an object"),
        pytest.param(
            minimal(nodes=[{"id": "a.py", "kind": "internal"}], edges=[{"from": "a.py"}]),
            'every edge needs a string "from" and "to"',
            id="edge without to",
        ),
        pytest.param(
            minimal(nodes=[{"id": "a.py", "kind": "internal"}], edges=[{"from": "a.py", "to": "b.py"}]),
            "edge a.py -> b.py names a node that is not in the document",
            id="edge to a missing node",
        ),
    ],
)
def test_from_dict_rejects(data: Any, message: str) -> None:
    with pytest.raises(DocumentError) as error:
        PairsDocument.from_dict(data)
    assert message in str(error.value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1 / 3, 0.3333),
        (2 / 3, 0.6667),
        (5 / 6, 0.8333),
        (0.5, 0.5),
        (0.00005, 0.0001),
        (-0.00005, -0.0001),
        (0.99995, 1),
        (1.0, 1),
        (0, 0),
    ],
)
def test_number_rounds_half_away_from_zero_to_four_places(value: float, expected: float) -> None:
    assert number(value) == expected


def test_number_writes_whole_numbers_as_integers() -> None:
    assert type(number(1.0)) is int and type(number(0.0)) is int and type(number(0.5)) is float
    assert encode({"x": number(2 / 2), "y": number(1 / 4)}) == '{\n  "x": 1,\n  "y": 0.25\n}\n'


def test_round_half_up_goes_through_the_shortest_decimal_form() -> None:
    # 0.125 and 2.675 are not exact in binary; rounding their written form gives what people expect.
    assert str(round_half_up(0.125, 2)) == "0.13"
    assert str(round_half_up(2.675, 2)) == "2.68"
    assert str(round_half_up(66.5, 0)) == "67"
