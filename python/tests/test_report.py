# SPDX-License-Identifier: GPL-2.0-only
import pytest
from builders import build, demo

from untangled.analysis.analyzer import analyze
from untangled.analysis.clustering import Clustering
from untangled.graph import EXTERNAL, UNRESOLVED
from untangled.report.report import Report


def marked(report: Report) -> list[str]:
    return [f"{e['from']}>{e['to']}{'*' if e['cycle'] else ''}" for e in report.unit_edges()]


def test_carries_the_analysis() -> None:
    document = demo()
    report = Report.build("Demo", document)
    assert report.title == "Demo"
    assert report.analysis == analyze(document)
    assert not report.is_clustered()
    assert report.dropped == {}


def test_marks_edges_inside_a_cycle() -> None:
    assert marked(Report.build("Demo", demo())) == ["a.py>b.py*", "b.py>a.py*", "b.py>c.py"]


def test_an_edge_between_two_different_cycles_is_not_a_cycle_edge() -> None:
    report = Report.build(
        "Two", build(["a.py -> b.py", "b.py -> a.py", "b.py -> c.py", "c.py -> d.py", "d.py -> c.py"])
    )
    edges = {f"{e['from']}>{e['to']}": e["cycle"] for e in report.unit_edges()}
    assert edges["b.py>c.py"] is False
    assert edges["c.py>d.py"] is True


def test_unit_edges_keep_their_count_and_leave_out_other_nodes() -> None:
    document = demo()
    document.add_edge("b.py", "c.py", ["from"])
    edges = Report.build("Demo", document).unit_edges()
    assert edges[2] == {"from": "b.py", "to": "c.py", "count": 2, "cycle": False}
    assert len(edges) == 3


def test_cycle_of_numbers_cycles_from_one() -> None:
    report = Report.build(
        "Two", build(["a.py -> b.py", "b.py -> c.py", "c.py -> a.py", "x.py -> y.py", "y.py -> x.py"])
    )
    assert report.cycle_of() == {"a.py": 1, "b.py": 1, "c.py": 1, "x.py": 2, "y.py": 2}


def test_lists_who_uses_each_package_and_reference() -> None:
    report = Report.build("Demo", demo())
    assert report.targets(EXTERNAL) == {"pypi:x": ["a.py", "c.py"]}
    assert report.targets(UNRESOLVED) == {"unresolved:module:</script><b>x": ["c.py"]}


def test_targets_list_the_most_used_first() -> None:
    report = Report.build("Uses", build(["a.py -> pypi:z", "b.py -> pypi:z", "a.py -> pypi:a", "a.py -> pypi:m"]))
    assert list(report.targets(EXTERNAL)) == ["pypi:z", "pypi:a", "pypi:m"]


def test_the_map_draws_every_unit_up_to_the_limit() -> None:
    assert Report.build("Demo", demo()).map_units(3) == ["a.py", "b.py", "c.py"]


def test_beyond_the_limit_the_map_draws_the_most_connected_units() -> None:
    # d has 3 connections, c 2, and a, b and e 1 (a package is not a connection); a wins the tie by id.
    report = Report.build(
        "Big", build(["a.py -> d.py", "b.py -> d.py", "c.py -> d.py", "c.py -> e.py", "a.py -> pypi:x"])
    )
    assert report.map_units(2) == ["c.py", "d.py"]
    assert report.map_units(3) == ["a.py", "c.py", "d.py"]


def test_clustered_reports_use_the_cluster_graph() -> None:
    document = build(["a/1.py -> a/2.py", "a/1.py -> b/1.py", "a/2.py -> pypi:x", "b/1.py -> pypi:x"])
    report = Report.build("Grouped", document, Clustering.from_string("folder:1"))
    assert report.is_clustered()
    assert report.dropped == {"a": 1}
    assert report.unit_edges() == [{"from": "a", "to": "b", "count": 1, "cycle": False}]
    assert report.targets(EXTERNAL) == {"pypi:x": ["a", "b"]}


def test_refuses_an_already_clustered_document() -> None:
    clustered = Clustering.from_string("folder:1").apply(build(["a/1.py -> b/1.py"])).document
    with pytest.raises(ValueError, match="already clustered"):
        Report.build("x", clustered)
