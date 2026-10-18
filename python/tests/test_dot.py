# SPDX-License-Identifier: GPL-2.0-only
"""The DOT format of spec/report.md, byte for byte."""

import pytest
from builders import build

from untangled.analysis.clustering import Clustering
from untangled.analysis.filtering import Filter
from untangled.graph import PairsDocument
from untangled.report import dot
from untangled.report.report import Report

HEADER = (
    "digraph untangled {\n"
    '  graph [rankdir=LR, fontname="Helvetica"];\n'
    '  node [shape=box, style=rounded, fontname="Helvetica"];\n'
    '  edge [color="#898781"];\n'
)

CLASSIC_HEADER = (
    "digraph untangled {\n"
    "  graph [rankdir=LR];\n"
    '  node [shape=ellipse, style=filled, fillcolor=lightgrey, fontname="Times-Roman", fontsize=7];\n'
    "  edge [color=black];\n"
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param("src/a.py", '"src/a.py"', id="plain"),
        pytest.param("App\\X", '"App\\\\X"', id="backslash"),
        pytest.param('say "hi"', '"say \\"hi\\""', id="quote"),
        pytest.param("a\nb", '"a\\nb"', id="newline"),
        pytest.param('App\\X "y"\nz', '"App\\\\X \\"y\\"\\nz"', id="everything"),
        pytest.param("", '""', id="empty"),
    ],
)
def test_quote(text: str, expected: str) -> None:
    assert dot.quote(text) == expected


def test_the_spec_example() -> None:
    report = Report.build("x", build(["src/a.py -> src/b.py", "src/b.py -> src/a.py", "src/b.py -> src/c.py"]))
    assert dot.render(report) == HEADER + (
        "\n"
        '  "src/a.py" [color="#d03b3b", penwidth=2];\n'
        '  "src/b.py" [color="#d03b3b", penwidth=2];\n'
        '  "src/c.py";\n'
        "\n"
        '  "src/a.py" -> "src/b.py" [color="#d03b3b", penwidth=2];\n'
        '  "src/b.py" -> "src/a.py" [color="#d03b3b", penwidth=2];\n'
        '  "src/b.py" -> "src/c.py";\n'
        "}\n"
    )


def test_the_default_style_is_named_default() -> None:
    report = Report.build("x", build(["a.py -> b.py"]))
    assert dot.render(report, "default") == dot.render(report)
    assert dot.STYLES == ("default", "classic")


def test_an_empty_graph_is_just_the_header() -> None:
    assert dot.render(Report.build("x", PairsDocument("python"))) == HEADER + "}\n"


def test_units_without_edges_have_no_edge_block() -> None:
    assert dot.render(Report.build("x", build([], isolated=["a.py"]))) == HEADER + '\n  "a.py";\n}\n'


def test_external_and_unresolved_nodes_are_left_out() -> None:
    report = Report.build("x", build(["a.py -> pypi:x", "a.py -> unresolved:module:q"]))
    assert dot.render(report) == HEADER + '\n  "a.py";\n}\n'


def test_cluster_units_are_labelled_with_their_file_count() -> None:
    report = Report.build(
        "x", build(["app/a.py -> lib/b.py", "app/c.py -> lib/b.py"]), Clustering.from_string("folder:1")
    )
    text = dot.render(report)
    assert '  "app" [label="app\\n2 files"];\n' in text
    assert '  "lib" [label="lib\\n1 file"];\n' in text
    assert '  "app" -> "lib";\n' in text


def test_the_cycle_highlight_comes_after_the_label() -> None:
    report = Report.build("x", build(["a/1.py -> b/1.py", "b/1.py -> a/1.py"]), Clustering.from_string("folder:1"))
    assert '  "a" [label="a\\n1 file", color="#d03b3b", penwidth=2];' in dot.render(report)


def test_namespace_ids_keep_their_backslashes() -> None:
    document = build(["a.php -> b.php"], modules={"a.php": "App\\Http", "b.php": "App\\Domain"}, language="php")
    report = Report.build("x", document, Clustering.from_string("namespace:2"))
    assert '  "App\\\\Http" -> "App\\\\Domain";' in dot.render(report)


def test_python_package_ids_keep_their_dots() -> None:
    document = build(["a.py -> b.py"], modules={"a.py": "shop.http.views", "b.py": "shop.domain.order"})
    report = Report.build("x", document, Clustering.from_string("namespace:2"))
    assert '  "shop.http" -> "shop.domain";' in dot.render(report)


def test_classic_draws_units_grey_and_what_they_use_white_with_no_cycle_colour() -> None:
    document = build(
        [
            "src/a.py -> src/b.py",
            "src/b.py -> src/a.py",
            "src/a.py -> pypi:x",
            "src/b.py -> builtin:os",
            "src/b.py -> unresolved:module:q",
            "src/b.py -> pypi:x",
        ]
    )
    assert dot.render(Report.build("x", document), "classic") == CLASSIC_HEADER + (
        "\n"
        '  "src/a.py";\n'
        '  "src/b.py";\n'
        '  "pypi:x" [fillcolor=white];\n'
        '  "unresolved:module:q" [fillcolor=white];\n'
        "\n"
        '  "src/a.py" -> "pypi:x";\n'
        '  "src/a.py" -> "src/b.py";\n'
        '  "src/b.py" -> "pypi:x";\n'
        '  "src/b.py" -> "src/a.py";\n'
        '  "src/b.py" -> "unresolved:module:q";\n'
        "}\n"
    )


def test_classic_of_an_empty_graph_is_just_the_header() -> None:
    assert dot.render(Report.build("x", PairsDocument("python")), "classic") == CLASSIC_HEADER + "}\n"


def test_classic_leaves_out_what_filtered_units_use() -> None:
    document = build(["a.py -> b.py", "b.py -> pypi:x"])
    report = Report.build("x", Filter().exclude("b.py").apply(document))
    assert dot.render(report, "classic") == CLASSIC_HEADER + '\n  "a.py";\n}\n'


def test_classic_labels_clusters_and_keeps_their_external_edges() -> None:
    document = build(["app/a.py -> lib/b.py", "app/c.py -> pypi:x"])
    text = dot.render(Report.build("x", document, Clustering.from_string("folder:1")), "classic")
    assert '  "app" [label="app\\n2 files"];\n' in text
    assert '  "app" -> "pypi:x";\n' in text
    assert '  "pypi:x" [fillcolor=white];\n' in text
