# SPDX-License-Identifier: GPL-2.0-only
"""The HTML report of spec/report.md."""

import datetime
import json
import re
from pathlib import Path
from typing import Any

import pytest
from builders import build, demo

from untangled.analysis.clustering import Clustering
from untangled.analysis.filtering import Filter
from untangled.graph import PairsDocument
from untangled.report import dot, html
from untangled.report.report import Report
from untangled.scanner.scanner import Scanner

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "conformance" / "cases"


def demo_page() -> str:
    return html.render(Report.build("Demo <app>", demo()), datetime.date(2026, 10, 17))


def data(page: str) -> dict[str, Any]:
    """The data embedded for the page's script."""
    match = re.search(r'<script type="application/json" id="untangled-data">(.*?)</script>', page, re.DOTALL)
    assert match is not None
    return json.loads(match.group(1))


def scanned(case: str, clustering: Clustering | None = None) -> Report:
    pairs = Scanner().scan(str(CASES / case / "python" / "project")).pairs
    return Report.build(case, Filter().apply(pairs), clustering)


def grouped() -> Report:
    return scanned("layers", Clustering.from_string("namespace:2"))


def test_is_one_self_contained_page() -> None:
    page = demo_page()
    assert page.startswith("<!doctype html>")
    assert page.endswith("</html>\n")
    assert not re.search(r"<(?:script|link|img)[^>]+(?:src|href)=[\"']?(?:https?:)?//", page, re.IGNORECASE)
    assert not re.search(r"<(?:script|link)[^>]+(?:src|href)=", page, re.IGNORECASE)
    assert "@import" not in page


def test_escapes_names_in_markup_and_data() -> None:
    page = demo_page()
    assert "<title>Dependencies: Demo &lt;app&gt;</title>" in page
    assert "<h1>Demo &lt;app&gt;</h1>" in page
    assert "</script><b>" not in page
    # The two closing tags are the inline script and the embedded data, nothing injected.
    assert page.count("</script>") == 2
    assert data(page)["units"][2]["id"] == "c.py"


def test_escape() -> None:
    assert html.escape("<a href=\"x\">'&'</a>") == "&lt;a href=&quot;x&quot;&gt;&#039;&amp;&#039;&lt;/a&gt;"


def test_sections_come_in_the_specified_order() -> None:
    page = html.render(grouped())
    sections = ["summary", "why", "map", "cycles", "hotspots", "parts", "outside", "groups", "glossary"]
    positions = [page.find(f'<section id="{section}"') for section in sections]
    assert -1 not in positions
    assert positions == sorted(positions)


def test_states_the_cycles() -> None:
    page = demo_page()
    assert "1 dependency cycle found." in page
    assert "2 parts of 3 (67%) are caught in a loop" in page


def test_lists_each_cycle_with_its_example_loop() -> None:
    page = html.render(Report.build("x", build(["a.py -> b.py", "b.py -> a.py"])))
    assert "2 parts of 2 (100%) are caught in a loop, so they cannot be changed" in page
    assert "<h3>Cycle 1: 2 parts</h3>" in page
    assert '<span class="step mono">a.py</span><span class="arrow" aria-label="relies on">&rarr;</span>' in page


def test_says_when_there_are_no_cycles() -> None:
    page = html.render(scanned("src-layout"))
    assert "No dependency cycles." in page
    assert 'id="groups"' not in page


@pytest.mark.parametrize("key", [key for key in html.PLAIN if key not in ("ca", "ce")])
def test_uses_the_plain_language_lines_verbatim(key: str) -> None:
    assert html.escape(html.PLAIN[key]) in demo_page()


def test_plain_language_lines_match_the_spec() -> None:
    # The spec wraps long lines, so compare with runs of whitespace collapsed.
    spec = re.sub(r"\s+", " ", (ROOT / "spec" / "metrics.md").read_text(encoding="utf-8"))
    for key in ["fan_out", "fan_in", "external", "unresolved", "instability", "cycle"]:
        assert html.PLAIN[key] in spec, f"spec/metrics.md must contain the {key} line"


def test_shows_the_generation_date() -> None:
    assert "Generated 17 October 2026" in demo_page()


def test_embeds_the_graph_and_the_dot_file() -> None:
    report = Report.build("Demo", demo())
    embedded = data(html.render(report))
    assert len(embedded["units"]) == 3
    assert embedded["units"][0]["cycle"] == 1
    assert embedded["units"][2]["cycle"] is None
    assert embedded["dot"] == dot.render(report)
    assert embedded["clustered"] is False
    assert embedded["plain"] == html.PLAIN


def test_clustered_reports_explain_the_grouping() -> None:
    page = html.render(grouped())
    assert "share the first 2 levels of their package path" in page
    assert 'id="groups"' in page
    assert html.escape(html.PLAIN["ca"]) in page
    assert html.escape(html.PLAIN["ce"]) in page


def test_describes_each_grouping() -> None:
    document = build(["a/1.py -> b/1.py"])
    assert "Each part is one file." in html.render(Report.build("x", document))
    folder = html.render(Report.build("x", document, Clustering.from_string("folder:1")))
    assert "share the first 1 level of their folder path" in folder
    assert "as set by a rules file" in html.render(Report.build("x", document, Clustering.parse_rules("a/ A")))


def test_php_namespaces_and_python_package_paths() -> None:
    assert html.describe_grouping("namespace:1", "python") == (
        "Each part is a group of files that share the first 1 level of their package path."
    )
    assert html.describe_grouping("namespace:3", "php") == (
        "Each part is a group of files that share the first 3 levels of their namespace."
    )


def test_python_modules_are_grouped_by_package_path() -> None:
    document = build([], modules={"shop/cart.py": "shop.cart"}, isolated=["shop/cart.py"])
    page = html.render(Report.build("x", document, Clustering.from_string("namespace:1")))
    assert "share the first 1 level of their package path" in page


def test_an_empty_project_still_renders() -> None:
    assert "nothing to report yet" in html.render(Report.build("Empty", PairsDocument("python")))


def test_instability() -> None:
    assert html.instability(None) == "none"
    assert html.instability(0) == "0.00"
    assert html.instability(0.3333) == "0.33"
    assert html.instability(0.125) == "0.13"
    assert html.instability(1) == "1.00"


def test_count() -> None:
    assert html.count(1, "file") == "1 file"
    assert html.count(0, "file") == "0 files"
    assert html.count(2, "dependency", "dependencies") == "2 dependencies"
    assert html.count(6426, "part") == "6,426 parts"


def test_unresolved_name() -> None:
    assert html.unresolved_name("unresolved:module:shop.missing") == "shop.missing (module)"
    assert html.unresolved_name("unresolved:class:App\\Gone") == "App\\Gone (class)"
    assert html.unresolved_name("unresolved:include:$a . 'x.php'") == "$a . 'x.php' (include)"
    assert html.unresolved_name("weird") == "weird"


def test_lists_packages_and_unresolved_references() -> None:
    page = html.render(scanned("stdlib-and-packages"))
    for package in ["django", "pyyaml", "google-auth"]:
        assert f'<span class="mono">{package}</span>' in page
    assert "pypi:django" not in page.split('<script type="application/json"')[0]
    assert "requests (module)" in page


def test_small_maps_draw_every_part() -> None:
    page = demo_page()
    assert data(page)["drawn"] is None
    assert "<strong>The map shows" not in page


def test_large_maps_draw_the_most_connected_parts_and_say_so() -> None:
    edges = [f"f{n}.py -> hub.py" for n in range(1, html.MAP_LIMIT + 11)]
    page = html.render(Report.build("Big", build(edges)))
    embedded = data(page)
    assert len(embedded["drawn"]) == html.MAP_LIMIT
    assert "hub.py" in embedded["drawn"]
    assert len(embedded["units"]) == html.MAP_LIMIT + 11
    assert "The map shows the 300 parts with the most connections</strong>, out of 311" in page
    assert "a report grouped by namespace or folder shows the whole project" in page


def test_long_lists_of_packages_and_references_fold_away() -> None:
    edges = []
    for n in range(1, html.LIST_LIMIT + 3):
        edges += [f"a.py -> pypi:p{n}", f"a.py -> unresolved:module:u{n}"]
    page = html.render(Report.build("Lists", build(edges)))
    assert "<summary>2 more packages</summary>" in page
    assert "<summary>2 more references</summary>" in page
