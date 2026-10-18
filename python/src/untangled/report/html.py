# SPDX-License-Identifier: GPL-2.0-only
"""Renders a report as one self-contained HTML page (spec/report.md): the summary, plain-language
explanations, an interactive map of the unit graph, cycles, hotspots and the full metrics table.
Styles, script and data are inlined, so the file can be emailed or opened offline. The page is
the same as the PHP library's; its styles and script are shared copies (assets/)."""

import datetime
import json
import re
from importlib import resources
from typing import Any

from untangled import version
from untangled.graph import EXTERNAL, UNRESOLVED, round_half_up
from untangled.report import dot
from untangled.report.report import Report

PLAIN = {
    "fan_out": "How many other parts of the code this one relies on.",
    "fan_in": "How many other parts of the code rely on this one.",
    "external": "How many third-party packages this part uses directly.",
    "unresolved": "References we could not trace; the real coupling may be higher.",
    "instability": "How much this part is pushed around by changes elsewhere, from 0 (others lean on it)"
    " to 1 (it leans on others).",
    "ca": "How many files outside this group rely on it.",
    "ce": "How many files outside this group it relies on.",
    "cycle": "These parts all depend on each other, so none of them can be changed, tested or reused alone.",
}
"""The plain-language lines of spec/metrics.md, which reports must use verbatim."""

TOP = 5
"""How many units the hotspot lists show."""

MAP_LIMIT = 300
"""How many units the map draws at most; beyond this a force layout is a slow, unreadable hairball."""

LIST_LIMIT = 15
"""How many packages and untraced references are listed before the rest fold away."""

_MONTHS = "January February March April May June July August September October November December".split()


def render(report: Report, generated_at: datetime.date | None = None) -> str:
    analysis = report.analysis
    units = analysis["units"]
    cycle_of = report.cycle_of()
    drawn = report.map_units(MAP_LIMIT)
    clustered = report.is_clustered()
    data = {
        "clustered": clustered,
        "plain": PLAIN,
        "units": [{**unit, "cycle": cycle_of.get(unit["id"])} for unit in units],
        "edges": report.unit_edges(),
        "cycles": analysis["cycles"],
        "drawn": drawn if len(drawn) < len(units) else None,
        "dot": dot.render(report),
    }
    day = generated_at or datetime.date.today()
    page = _Page(
        report=report,
        generated_at=f"{day.day} {_MONTHS[day.month - 1]} {day.year}",
        generator=f"{version.NAME} {version.VERSION}",
        grouping=describe_grouping(analysis["clustering"], analysis["language"]),
        cycle_of=cycle_of,
        drawn_count=len(drawn),
        data=data,
    )
    return page.render()


def count(value: int, singular: str, plural: str | None = None) -> str:
    """ "3 files", "1 group": counts with the right noun."""
    return f"{number(value)} {singular if value == 1 else (plural or singular + 's')}"


def number(value: int) -> str:
    """A whole number as shown to readers, with thousands separated: "6,426"."""
    return f"{value:,}"


def instability(value: float | None) -> str:
    """The instability value as shown to readers: two decimals, or "none" when undefined."""
    return "none" if value is None else f"{round_half_up(value, 2):,.2f}"


def unresolved_name(node_id: str) -> str:
    """A readable name for an unresolved node id such as `unresolved:module:shop.missing`."""
    parts = node_id.split(":", 2)
    return f"{parts[2]} ({parts[1]})" if len(parts) == 3 else node_id


def describe_grouping(clustering: str | None, language: str = "php") -> str:
    if clustering is None:
        return "Each part is one file."
    if clustering == "rules":
        return "Each part is a group of files, as set by a rules file."
    strategy, depth = clustering.split(":")
    levels = count(int(depth), "level")
    if strategy == "namespace":
        # Python has packages where PHP has namespaces.
        kind = _NAMESPACE.get(language, "namespace")
        return f"Each part is a group of files that share the first {levels} of their {kind}."
    return f"Each part is a group of files that share the first {levels} of their folder path."


_NAMESPACE = {"python": "package path"}


def escape(text: Any) -> str:
    """Escapes text for HTML, as PHP's htmlspecialchars(ENT_QUOTES) does."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )


def _top(units: list[dict[str, Any]], metric: str) -> list[dict[str, Any]]:
    """The units with the highest non-zero metric, highest first."""
    ranked = sorted((unit for unit in units if unit[metric] > 0), key=lambda unit: (-unit[metric], unit["id"]))
    return ranked[:TOP]


def _asset(name: str) -> str:
    return resources.files("untangled.report").joinpath("assets", name).read_text(encoding="utf-8")


def _script_json(data: Any) -> str:
    """JSON that is safe inside a <script> element: <, > and & are escaped, as PHP's
    JSON_HEX_TAG and JSON_HEX_AMP do."""
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return text.replace("<", "\\u003C").replace(">", "\\u003E").replace("&", "\\u0026")


class _Page:
    def __init__(self, **values: Any) -> None:
        self.report: Report = values["report"]
        self.generated_at: str = values["generated_at"]
        self.generator: str = values["generator"]
        self.grouping: str = values["grouping"]
        self.cycle_of: dict[str, int] = values["cycle_of"]
        self.drawn_count: int = values["drawn_count"]
        self.data: dict[str, Any] = values["data"]
        self.analysis = self.report.analysis
        self.units: list[dict[str, Any]] = self.analysis["units"]
        self.clustered = self.report.is_clustered()

    def render(self) -> str:
        e = escape
        title = e(self.report.title)
        return "\n".join(
            [
                "<!doctype html>",
                '<html lang="en">',
                "<head>",
                '<meta charset="utf-8">',
                '<meta name="viewport" content="width=device-width, initial-scale=1">',
                f'<meta name="generator" content="{e(self.generator)}">',
                f"<title>Dependencies: {title}</title>",
                "<style>",
                _asset("report.css"),
                "</style>",
                "</head>",
                "<body>",
                "<main>",
                "",
                "<header>",
                '  <p class="eyebrow">Untangled dependency report</p>',
                f"  <h1>{title}</h1>",
                f'  <p class="meta">Generated {e(self.generated_at)} by {e(self.generator)}. {e(self.grouping)}</p>',
                "</header>",
                "",
                self.summary(),
                self.why(),
                self.map(),
                self.cycles(),
                self.hotspots(),
                self.parts(),
                self.outside(),
                self.groups(),
                self.glossary(),
                "<footer>",
                f"  <p>Made with {e(self.generator)}, an open-source tool following the ideas of"
                " Martin Blais's snakefood."
                " The map can also be opened in Graphviz with the .dot download.</p>",
                "</footer>",
                "",
                "</main>",
                f'<script type="application/json" id="untangled-data">{_script_json(self.data)}</script>',
                "<script>",
                _asset("report.js"),
                "</script>",
                "</body>",
                "</html>",
                "",
            ]
        )

    def summary(self) -> str:
        e = escape
        s = self.analysis["summary"]
        percent = int(round_half_up(s["units_in_cycles_ratio"] * 100, 0))
        out = ['<section id="summary" aria-labelledby="summary-title" style="margin-top: 28px">']
        out.append('  <h2 id="summary-title">At a glance</h2>')
        if s["units"] == 0:
            out.append(
                '  <div class="headline"><p>No source files were found to analyze, so there is nothing to report'
                " yet.</p></div>"
            )
        elif s["cycles"] == 0:
            out += [
                '  <div class="headline status-good">',
                '    <span class="status-icon" aria-hidden="true">&#10003;</span>',
                "    <div>",
                "      <p><strong>No dependency cycles.</strong> Every part can, in principle, be changed and tested"
                " without dragging others along in a loop.</p>",
                f'      <p class="sub">{e(count(s["units"], "part"))} with'
                f" {e(count(s['edges'], 'dependency', 'dependencies'))} between them.</p>",
                "    </div>",
                "  </div>",
            ]
        else:
            one = s["units_in_cycles"] == 1
            out += [
                '  <div class="headline status-critical">',
                '    <span class="status-icon" aria-hidden="true">!</span>',
                "    <div>",
                f"      <p><strong>{e(count(s['cycles'], 'dependency cycle'))} found.</strong>",
                f"        {e(count(s['units_in_cycles'], 'part'))} of {e(number(s['units']))} ({e(percent)}%)"
                f" {'is' if one else 'are'} caught in a loop, so {'it' if one else 'they'} cannot be changed, tested"
                " or reused alone.</p>",
                f'      <p class="sub">The largest cycle ties {e(count(s["largest_cycle"], "part"))} together.'
                ' <a href="#cycles">See the cycles</a>.</p>',
                "    </div>",
                "  </div>",
            ]

        def tile(value: str, label: str, alert: bool = False) -> str:
            return (
                f'    <div class="card tile{" alert" if alert else ""}"><div class="value">{e(value)}</div>'
                f'<div class="label">{label}</div></div>'
            )

        out.append('  <div class="tiles">')
        out.append(tile(number(s["units"]), "parts of the code"))
        out.append(tile(number(s["edges"]), "dependencies between them"))
        cycles_label = "cycle" if s["cycles"] == 1 else "cycles"
        out.append(tile(number(s["cycles"]), f"{cycles_label} (loops of dependencies)", s["cycles"] > 0))
        out.append(tile(f"{percent}%", "of parts are in a cycle", s["units_in_cycles"] > 0))
        mean = f"{round_half_up(s['mean_fan_out'], 1):,.1f}"
        out.append(tile(mean, "other parts each one relies on, on average"))
        packages = "package" if s["external_packages"] == 1 else "packages"
        out.append(tile(number(s["external_packages"]), f"third-party {packages} used"))
        if s["unresolved_references"] > 0:
            references = "reference" if s["unresolved_references"] == 1 else "references"
            out.append(tile(number(s["unresolved_references"]), f"{references} we could not trace"))
        out += ["  </div>", "</section>", ""]
        return "\n".join(out)

    def why(self) -> str:
        return "\n".join(
            [
                '<section id="why" aria-labelledby="why-title">',
                '  <h2 id="why-title">Why this matters</h2>',
                '  <div class="two-col">',
                '    <div class="card">',
                "      <h3>Coupling: how tightly parts are tied together</h3>",
                "      <p>Whenever one part of the code relies on another, a change in one can ripple into the other."
                " Some of this is normal and necessary.</p>",
                "      <p>Parts that many others rely on are risky to change, because a mistake spreads to everything"
                " that uses them. Parts that rely on many others break easily, because any of those can change under"
                " them. Fewer connections, all pointing the same way, make code cheaper to change, test and hand"
                " over.</p>",
                "    </div>",
                '    <div class="card">',
                "      <h3>Cycles: parts that depend on each other in a loop</h3>",
                "      <p>A cycle is a loop: A relies on B, and B, directly or through others, relies back on A."
                f" {escape(PLAIN['cycle'])}</p>",
                "      <p>Work on any part of a loop tends to drag in all of it, and a bug in one part can surface in"
                " all of them. Breaking a loop is usually the first thing worth fixing, because it makes every part in"
                " it easier to work with.</p>",
                "    </div>",
                "  </div>",
                "</section>",
                "",
            ]
        )

    def map(self) -> str:
        e = escape
        total = len(self.units)
        lead = (
            '  <p class="lead">Each circle is a part of the code; each arrow points from a part to something it relies'
            " on. Click a circle to see its numbers and connections, drag to move around, and scroll or pinch to zoom."
        )
        if self.drawn_count < total:
            lead += (
                f'</p>\n  <p class="lead"><strong>The map shows the {e(number(self.drawn_count))} parts with the most'
                f" connections</strong>, out of {e(number(total))}, because more would not be readable. Every part is"
                " still in the tables below"
            )
            if not self.clustered:
                lead += ", and a report grouped by namespace or folder shows the whole project on one map"
            lead += "."
        elif not self.clustered and total > 150:
            lead += (
                f" With {e(number(total))} files the map is dense; a report grouped by namespace or folder gives a"
                " clearer overview."
            )
        lead += "</p>"
        return "\n".join(
            [
                '<section id="map" aria-labelledby="map-title">',
                '  <h2 id="map-title">Map of dependencies</h2>',
                lead,
                '  <div class="toolbar">',
                '    <input type="search" id="map-search" list="map-names" placeholder="Find a part by name"'
                ' aria-label="Find a part by name">',
                '    <datalist id="map-names"></datalist>',
                '    <button type="button" id="map-labels" aria-pressed="false">Show all names</button>',
                '    <button type="button" id="map-reset">Reset view</button>',
                '    <button type="button" id="map-dot">Download Graphviz (.dot)</button>',
                "  </div>",
                '  <div class="map-layout">',
                '    <div class="card map" id="map-canvas">',
                '      <noscript><div class="map-empty">The map needs JavaScript. Everything it shows is also in the'
                " tables below.</div></noscript>",
                "    </div>",
                '    <aside class="card details" id="map-details" aria-live="polite">',
                "      <h3>Pick a part</h3>",
                '      <p class="muted">Click a circle on the map, or a name in the tables below, to see what it relies'
                " on and what relies on it.</p>",
                "    </aside>",
                "  </div>",
                '  <div class="legend" aria-label="Legend">',
                '    <span class="item"><span class="ramp" aria-hidden="true"></span> Instability: from 0 (others lean'
                " on it) to 1 (it leans on others)</span>",
                '    <span class="item"><span class="swatch none" aria-hidden="true"></span> Not connected to other'
                " parts</span>",
                '    <span class="item"><span class="swatch cycle" aria-hidden="true"></span> Red ring and arrows: part'
                " of a cycle</span>",
                '    <span class="item">Bigger circle: more parts rely on it</span>',
                "  </div>",
                "</section>",
                "",
            ]
        )

    def cycles(self) -> str:
        e = escape
        cycles = self.analysis["cycles"]
        out = ['<section id="cycles" aria-labelledby="cycles-title">', '  <h2 id="cycles-title">Cycles</h2>']
        if not cycles:
            out.append('  <p class="lead">None. No group of parts depends on each other in a loop.</p>')
        else:
            out.append(
                f'  <p class="lead">{e(PLAIN["cycle"])} Each cycle below shows one concrete loop as an example;'
                " breaking any one arrow in a loop is the place to start.</p>"
            )
            out.append('  <ol class="cycle-list">')
            for index, cycle in enumerate(cycles, 1):
                steps = "".join(
                    ('<span class="arrow" aria-label="relies on">&rarr;</span>' if i else "")
                    + f'<span class="step mono">{e(step)}</span>'
                    for i, step in enumerate(cycle["example"])
                )
                out += [
                    '    <li class="card">',
                    f"      <h3>Cycle {index}: {e(count(cycle['size'], 'part'))}</h3>",
                    f'      <div class="loop" aria-label="Example loop">{steps}</div>',
                ]
                if cycle["size"] > len(cycle["example"]) - 1:
                    members = "".join(f'<li class="mono">{e(member)}</li>' for member in cycle["members"])
                    out += [
                        "      <details>",
                        f"        <summary>All {e(cycle['size'])} parts in this cycle</summary>",
                        f"        <ul>{members}</ul>",
                        "      </details>",
                    ]
                out.append("    </li>")
            out.append("  </ol>")
        out += ["</section>", ""]
        return "\n".join(out)

    def hotspots(self) -> str:
        e = escape

        def ranking(units: list[dict[str, Any]], metric: str, empty: str) -> list[str]:
            if not units:
                return [f'      <p class="muted">{empty}</p>']
            rows = [
                f'          <li><button type="button" class="link-button mono" data-unit="{e(unit["id"])}">'
                f'{e(unit["id"])}</button><span class="count">{e(count(unit[metric], "part"))}</span></li>'
                for unit in units
            ]
            return ['        <ol class="rank">', *rows, "        </ol>"]

        return "\n".join(
            [
                '<section id="hotspots" aria-labelledby="hotspots-title">',
                '  <h2 id="hotspots-title">Where to look first</h2>',
                '  <div class="two-col">',
                '    <div class="card">',
                "      <h3>Most relied upon</h3>",
                f'      <p class="muted small">{e(PLAIN["fan_in"])} Changes here ripple the furthest, so change them'
                " carefully and keep them well tested.</p>",
                *ranking(_top(self.units, "fan_in"), "fan_in", "Nothing relies on any other part."),
                "    </div>",
                '    <div class="card">',
                "      <h3>Relies on the most</h3>",
                f'      <p class="muted small">{e(PLAIN["fan_out"])} These break most easily when something they rely'
                " on changes.</p>",
                *ranking(_top(self.units, "fan_out"), "fan_out", "No part relies on another."),
                "    </div>",
                "  </div>",
                "</section>",
                "",
            ]
        )

    def parts(self) -> str:
        e = escape

        def heading(key: str, label: str, numeric: bool = True, plain: str | None = None) -> str:
            css = ' class="num"' if numeric else ""
            hint = f' title="{e(PLAIN[plain])}"' if plain else ""
            return f'          <th scope="col"{css} data-key="{key}"{hint}><button type="button">{label}</button></th>'

        headings = [heading("id", "Part", False), heading("fan_in", "Relied on by", plain="fan_in")]
        headings.append(heading("fan_out", "Relies on", plain="fan_out"))
        if self.clustered:
            headings.append(heading("ca", "Files relying on it", plain="ca"))
            headings.append(heading("ce", "Files it relies on", plain="ce"))
        headings.append(heading("instability", "Instability", plain="instability"))
        headings.append(heading("external", "Packages", plain="external"))
        headings.append(heading("unresolved", "Untraced", plain="unresolved"))
        headings.append(heading("cycle", "Cycle", False))

        rows = []
        for unit in self.units:
            name = (
                f'<button type="button" class="link-button mono" data-unit="{e(unit["id"])}">{e(unit["id"])}</button>'
            )
            if self.clustered:
                name += f'<div class="muted small">{e(count(len(unit["members"]), "file"))}</div>'
            cells = [f"            <td>{name}</td>"]
            cells.append(f'            <td class="num">{e(unit["fan_in"])}</td>')
            cells.append(f'            <td class="num">{e(unit["fan_out"])}</td>')
            if self.clustered:
                cells.append(f'            <td class="num">{e(unit["ca"])}</td>')
                cells.append(f'            <td class="num">{e(unit["ce"])}</td>')
            value = "-1" if unit["instability"] is None else e(unit["instability"])
            cells.append(f'            <td class="num" data-value="{value}">{e(instability(unit["instability"]))}</td>')
            cells.append(f'            <td class="num">{e(unit["external"])}</td>')
            cells.append(f'            <td class="num">{e(unit["unresolved"])}</td>')
            cycle = self.cycle_of.get(unit["id"])
            flag = f'<span class="flag">Cycle {e(cycle)}</span>' if cycle is not None else ""
            cells.append(f'            <td data-value="{e(cycle or 0)}">{flag}</td>')
            rows += ["          <tr>", *cells, "          </tr>"]

        return "\n".join(
            [
                '<section id="parts" aria-labelledby="parts-title">',
                '  <h2 id="parts-title">Every part</h2>',
                '  <p class="lead">All the numbers, one row per part. Click a column heading to sort, or a name to find'
                " it on the map.</p>",
                '  <div class="card table-wrap">',
                '    <table id="parts-table">',
                "      <thead>",
                "        <tr>",
                *headings,
                "        </tr>",
                "      </thead>",
                "      <tbody>",
                *rows,
                "      </tbody>",
                "    </table>",
                "  </div>",
                "</section>",
                "",
            ]
        )

    def outside(self) -> str:
        e = escape

        def listing(targets: dict[str, list[str]], item: Any, empty: str, more: str) -> list[str]:
            if not targets:
                return [f'      <p class="muted">{empty}</p>']
            entries = list(targets.items())
            out = ['      <ul class="rank">', "".join(item(i, u) for i, u in entries[:LIST_LIMIT]), "      </ul>"]
            if len(entries) > LIST_LIMIT:
                rest = "".join(item(i, u) for i, u in entries[LIST_LIMIT:])
                out += [
                    "      <details>",
                    f"        <summary>{e(count(len(entries) - LIST_LIMIT, more))}</summary>",
                    f'        <ul class="rank">{rest}</ul>',
                    "      </details>",
                ]
            return out

        def package(node_id: str, users: list[str]) -> str:
            name = re.sub(r"^[a-z]+:", "", node_id)
            return (
                f'<li><span class="mono">{e(name)}</span>'
                f'<span class="count">used by {e(count(len(users), "part"))}</span></li>'
            )

        def reference(node_id: str, users: list[str]) -> str:
            return (
                f'<li><span class="mono">{e(unresolved_name(node_id))}</span>'
                f'<span class="count">in {e(count(len(users), "part"))}</span></li>'
            )

        return "\n".join(
            [
                '<section id="outside" aria-labelledby="outside-title">',
                '  <h2 id="outside-title">Outside the project</h2>',
                '  <div class="two-col">',
                '    <div class="card">',
                "      <h3>Third-party packages</h3>",
                '      <p class="muted small">Code the project uses but does not own. Each package is a dependency on'
                " someone else's release schedule.</p>",
                *listing(self.report.targets(EXTERNAL), package, "None used directly.", "more package"),
                "    </div>",
                '    <div class="card">',
                "      <h3>References we could not trace</h3>",
                f'      <p class="muted small">{e(PLAIN["unresolved"])}</p>',
                *listing(
                    self.report.targets(UNRESOLVED), reference, "None. Every reference was traced.", "more reference"
                ),
                "    </div>",
                "  </div>",
                "</section>",
                "",
            ]
        )

    def groups(self) -> str:
        if not self.clustered:
            return ""
        e = escape
        rows = []
        for unit in self.units:
            members = "".join(f'<li class="mono">{e(member)}</li>' for member in unit["members"])
            rows += [
                "          <tr>",
                f'            <td class="mono">{e(unit["id"])}</td>',
                f'            <td class="num">{e(len(unit["members"]))}</td>',
                f'            <td class="num">{e(self.report.dropped.get(unit["id"], 0))}</td>',
                f"            <td><details><summary>{e(count(len(unit['members']), 'file'))}</summary>"
                f"<ul>{members}</ul></details></td>",
                "          </tr>",
            ]
        return "\n".join(
            [
                '<section id="groups" aria-labelledby="groups-title">',
                '  <h2 id="groups-title">What is in each group</h2>',
                '  <p class="lead">Dependencies between files of the same group are not drawn on the map or counted'
                " above; this shows how many there are.</p>",
                '  <div class="card table-wrap">',
                "    <table>",
                '      <thead><tr><th scope="col">Group</th><th scope="col" class="num">Files</th>'
                '<th scope="col" class="num">Dependencies inside</th><th scope="col">Files in it</th></tr></thead>',
                "      <tbody>",
                *rows,
                "      </tbody>",
                "    </table>",
                "  </div>",
                "</section>",
                "",
            ]
        )

    def glossary(self) -> str:
        e = escape
        terms = [
            ("Part", e(self.grouping)),
            ("Relied on by (fan-in)", e(PLAIN["fan_in"])),
            ("Relies on (fan-out)", e(PLAIN["fan_out"])),
        ]
        if self.clustered:
            terms += [("Files relying on it (Ca)", e(PLAIN["ca"])), ("Files it relies on (Ce)", e(PLAIN["ce"]))]
        terms += [
            (
                "Instability",
                f"{e(PLAIN['instability'])} Neither end is bad in itself: what matters is that parts others lean on"
                ' stay stable, and that unstable parts are the ones you expect to change. "None" means the'
                " part has no connections to other parts.",
            ),
            ("Packages", e(PLAIN["external"])),
            ("Untraced", e(PLAIN["unresolved"])),
            ("Cycle", e(PLAIN["cycle"])),
        ]
        return "\n".join(
            [
                '<section id="glossary" aria-labelledby="glossary-title">',
                '  <h2 id="glossary-title">How to read the numbers</h2>',
                '  <dl class="glossary">',
                *(f"    <dt>{term}</dt><dd>{text}</dd>" for term, text in terms),
                "  </dl>",
                "</section>",
                "",
            ]
        )
