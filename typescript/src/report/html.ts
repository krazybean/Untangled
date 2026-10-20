// SPDX-License-Identifier: MIT
// Renders a report as one self-contained HTML page (spec/report.md): the summary,
// plain-language explanations, an interactive map of the unit graph, cycles, hotspots and the
// full metrics table. Styles, script and data are inlined, so the file can be emailed or opened
// offline. The page is the same as the PHP library's (php/resources/report/report.html.php).

import { readFileSync } from "node:fs";

import type { Unit } from "../analysis/analyzer.js";
import { EXTERNAL, UNRESOLVED } from "../graph.js";
import { compareText } from "../text.js";
import { NAME, VERSION } from "../version.js";
import { renderDot } from "./dot.js";
import type { Report } from "./report.js";

/** The plain-language lines of spec/metrics.md, which reports must use verbatim. */
export const PLAIN = {
  fan_out: "How many other parts of the code this one relies on.",
  fan_in: "How many other parts of the code rely on this one.",
  external: "How many third-party packages this part uses directly.",
  unresolved: "References we could not trace; the real coupling may be higher.",
  instability:
    "How much this part is pushed around by changes elsewhere, from 0 (others lean on it) to 1 (it leans on others).",
  ca: "How many files outside this group rely on it.",
  ce: "How many files outside this group it relies on.",
  cycle: "These parts all depend on each other, so none of them can be changed, tested or reused alone.",
};

/** What a file's `error` (spec/pairs-format.md) says, in the report. */
export const UNREAD: Record<string, string> = { parse: "does not parse", read: "cannot be read" };

export const UNREAD_LINE = "Any dependencies these files have are missing from every number in this report.";

/** How many units the hotspot lists show. */
const TOP = 5;

/** How many units the map draws at most; beyond this a force layout is a slow, unreadable hairball. */
export const MAP_LIMIT = 300;

/** How many packages and untraced references are listed before the rest fold away. */
export const LIST_LIMIT = 15;

const MONTHS = [
  "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December",
];

export function renderHtml(report: Report, generatedAt: Date = new Date()): string {
  const analysis = report.analysis;
  const units = analysis.units;
  const cycleOf = report.cycleOf();
  const drawn = report.mapUnits(MAP_LIMIT);
  const clustered = report.isClustered();
  const s = analysis.summary;
  const percent = Math.round(s.units_in_cycles_ratio * 100);
  const title = report.title;
  const generator = `${NAME} ${VERSION}`;
  const grouping = describeGrouping(analysis.clustering, analysis.language);
  const cycles = analysis.cycles;
  const reliedOn = top(units, "fan_in");
  const leaning = top(units, "fan_out");
  const packages = [...report.targets(EXTERNAL)];
  const unresolved = [...report.targets(UNRESOLVED)];
  const dropped = report.dropped;
  const p = PLAIN;
  const date = `${generatedAt.getDate()} ${MONTHS[generatedAt.getMonth()]} ${generatedAt.getFullYear()}`;

  const data = {
    clustered,
    plain: PLAIN,
    units: units.map((unit) => ({ ...unit, cycle: cycleOf.get(unit.id) ?? null })),
    edges: report.unitEdges(),
    cycles,
    drawn: drawn.length < units.length ? drawn : null,
    dot: renderDot(report),
  };

  const unitButton = (id: string): string =>
    `<button type="button" class="link-button mono" data-unit="${e(id)}">${e(id)}</button>`;
  const rank = (list: Unit[], metric: "fan_in" | "fan_out"): string =>
    `
        <ol class="rank">
${list.map((unit) => `          <li>${unitButton(unit.id)}<span class="count">${e(count(unit[metric], "part"))}</span></li>`).join("\n")}
        </ol>`;
  const folding = (
    entries: [string, string[]][],
    item: (id: string, users: string[]) => string,
    more: string,
  ): string => {
    let html = `
        <ul class="rank">
          ${entries.slice(0, LIST_LIMIT).map(([id, users]) => item(id, users)).join("")}
        </ul>`;
    if (entries.length > LIST_LIMIT) {
      html += `
          <details>
            <summary>${e(count(entries.length - LIST_LIMIT, more))}</summary>
            <ul class="rank">${entries.slice(LIST_LIMIT).map(([id, users]) => item(id, users)).join("")}</ul>
          </details>`;
    }
    return html;
  };
  const packageItem = (id: string, users: string[]): string =>
    `<li><span class="mono">${e(id.replace(/^[a-z]+:/, ""))}</span><span class="count">used by ${e(count(users.length, "part"))}</span></li>`;
  const unread = [...report.unread].map(([id, error]): [string, string[]] => [id, [error]]);
  const unreadItem = (id: string, [error]: string[]): string =>
    `<li><span class="mono">${e(id)}</span><span class="count">${e(UNREAD[error!] ?? error!)}</span></li>`;
  const referenceItem = (id: string, users: string[]): string =>
    `<li><span class="mono">${e(unresolvedName(id))}</span><span class="count">in ${e(count(users.length, "part"))}</span></li>`;

  let headline: string;
  if (s.units === 0) {
    headline = `<div class="headline"><p>No source files were found to analyze, so there is nothing to report yet.</p></div>`;
  } else if (s.cycles === 0) {
    headline = `<div class="headline status-good">
      <span class="status-icon" aria-hidden="true">&#10003;</span>
      <div>
        <p><strong>No dependency cycles.</strong> Every part can, in principle, be changed and tested without dragging others along in a loop.</p>
        <p class="sub">${e(count(s.units, "part"))} with ${e(count(s.edges, "dependency", "dependencies"))} between them.</p>
      </div>
    </div>`;
  } else {
    const one = s.units_in_cycles === 1;
    headline = `<div class="headline status-critical">
      <span class="status-icon" aria-hidden="true">!</span>
      <div>
        <p><strong>${e(count(s.cycles, "dependency cycle"))} found.</strong>
          ${e(count(s.units_in_cycles, "part"))} of ${e(formatNumber(s.units))} (${e(percent)}%) ${one ? "is" : "are"} caught in a loop, so ${one ? "it" : "they"} cannot be changed, tested or reused alone.</p>
        <p class="sub">The largest cycle ties ${e(count(s.largest_cycle, "part"))} together. <a href="#cycles">See the cycles</a>.</p>
      </div>
    </div>`;
  }

  let mapNote = "";
  if (drawn.length < units.length) {
    mapNote = `</p>
  <p class="lead"><strong>The map shows the ${e(formatNumber(drawn.length))} parts with the most connections</strong>, out of ${e(formatNumber(units.length))}, because more would not be readable. Every part is still in the tables below${clustered ? "" : ", and a report grouped by namespace or folder shows the whole project on one map"}.`;
  } else if (!clustered && units.length > 150) {
    mapNote = ` With ${e(formatNumber(units.length))} files the map is dense; a report grouped by namespace or folder gives a clearer overview.`;
  }

  const cycleSection =
    cycles.length === 0
      ? `<p class="lead">None. No group of parts depends on each other in a loop.</p>`
      : `<p class="lead">${e(p.cycle)} Each cycle below shows one concrete loop as an example; breaking any one arrow in a loop is the place to start.</p>
    <ol class="cycle-list">
${cycles
  .map(
    (cycle, number) => `        <li class="card">
          <h3>Cycle ${e(number + 1)}: ${e(count(cycle.size, "part"))}</h3>
          <div class="loop" aria-label="Example loop">
${cycle.example
  .map(
    (step, index) =>
      `              ${index > 0 ? `<span class="arrow" aria-label="relies on">&rarr;</span>` : ""}
              <span class="step mono">${e(step)}</span>`,
  )
  .join("\n")}
          </div>${
            cycle.size > cycle.example.length - 1
              ? `
            <details>
              <summary>All ${e(cycle.size)} parts in this cycle</summary>
              <ul>${cycle.members.map((member) => `<li class="mono">${e(member)}</li>`).join("")}</ul>
            </details>`
              : ""
          }
        </li>`,
  )
  .join("\n")}
    </ol>`;

  const clusterHeadings = clustered
    ? `
          <th scope="col" class="num" data-key="ca" title="${e(p.ca)}"><button type="button">Files relying on it</button></th>
          <th scope="col" class="num" data-key="ce" title="${e(p.ce)}"><button type="button">Files it relies on</button></th>`
    : "";
  const rows = units
    .map((unit) => {
      const cycle = cycleOf.get(unit.id);
      return `          <tr>
            <td>${unitButton(unit.id)}${clustered ? `<div class="muted small">${e(count(unit.members?.length ?? 0, "file"))}</div>` : ""}</td>
            <td class="num">${e(unit.fan_in)}</td>
            <td class="num">${e(unit.fan_out)}</td>${
              clustered
                ? `
              <td class="num">${e(unit.ca ?? 0)}</td>
              <td class="num">${e(unit.ce ?? 0)}</td>`
                : ""
            }
            <td class="num" data-value="${unit.instability === null ? "-1" : e(unit.instability)}">${e(formatInstability(unit.instability))}</td>
            <td class="num">${e(unit.external)}</td>
            <td class="num">${e(unit.unresolved)}</td>
            <td data-value="${e(cycle ?? 0)}">${cycle === undefined ? "" : `<span class="flag">Cycle ${e(cycle)}</span>`}</td>
          </tr>`;
    })
    .join("\n");

  const groups = clustered
    ? `
<section id="groups" aria-labelledby="groups-title">
  <h2 id="groups-title">What is in each group</h2>
  <p class="lead">Dependencies between files of the same group are not drawn on the map or counted above; this shows how many there are.</p>
  <div class="card table-wrap">
    <table>
      <thead><tr><th scope="col">Group</th><th scope="col" class="num">Files</th><th scope="col" class="num">Dependencies inside</th><th scope="col">Files in it</th></tr></thead>
      <tbody>
${units
  .map((unit) => {
    const members = unit.members ?? [];
    return `          <tr>
            <td class="mono">${e(unit.id)}</td>
            <td class="num">${e(members.length)}</td>
            <td class="num">${e(dropped.get(unit.id) ?? 0)}</td>
            <td><details><summary>${e(count(members.length, "file"))}</summary><ul>${members.map((member) => `<li class="mono">${e(member)}</li>`).join("")}</ul></details></td>
          </tr>`;
  })
  .join("\n")}
      </tbody>
    </table>
  </div>
</section>
`
    : "";

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="${e(generator)}">
<title>Dependencies: ${e(title)}</title>
<style>
${asset("report.css")}
</style>
</head>
<body>
<main>

<header>
  <p class="eyebrow">Untangled dependency report</p>
  <h1>${e(title)}</h1>
  <p class="meta">Generated ${e(date)} by ${e(generator)}. ${e(grouping)}</p>
</header>

<section id="summary" aria-labelledby="summary-title" style="margin-top: 28px">
  <h2 id="summary-title">At a glance</h2>
  ${headline}

  <div class="tiles">
    <div class="card tile"><div class="value">${e(formatNumber(s.units))}</div><div class="label">parts of the code</div></div>
    <div class="card tile"><div class="value">${e(formatNumber(s.edges))}</div><div class="label">dependencies between them</div></div>
    <div class="card tile${s.cycles > 0 ? " alert" : ""}"><div class="value">${e(formatNumber(s.cycles))}</div><div class="label">${s.cycles === 1 ? "cycle" : "cycles"} (loops of dependencies)</div></div>
    <div class="card tile${s.units_in_cycles > 0 ? " alert" : ""}"><div class="value">${e(percent)}%</div><div class="label">of parts are in a cycle</div></div>
    <div class="card tile"><div class="value">${e(formatFixed(s.mean_fan_out, 1))}</div><div class="label">other parts each one relies on, on average</div></div>
    <div class="card tile"><div class="value">${e(formatNumber(s.external_packages))}</div><div class="label">third-party ${s.external_packages === 1 ? "package" : "packages"} used</div></div>${
      s.unresolved_references > 0
        ? `
      <div class="card tile"><div class="value">${e(formatNumber(s.unresolved_references))}</div><div class="label">${s.unresolved_references === 1 ? "reference" : "references"} we could not trace</div></div>`
        : ""
    }${
      unread.length > 0
        ? `
      <div class="card tile alert"><div class="value">${e(formatNumber(unread.length))}</div><div class="label">${unread.length === 1 ? "file" : "files"} we could not read</div></div>`
        : ""
    }
  </div>${
    unread.length > 0
      ? `
  <div class="card" style="margin-top: 16px">
    <h3>Files we could not read</h3>
    <p class="muted small">${e(UNREAD_LINE)}</p>${folding(unread, unreadItem, "more file")}
  </div>`
      : ""
  }
</section>

<section id="why" aria-labelledby="why-title">
  <h2 id="why-title">Why this matters</h2>
  <div class="two-col">
    <div class="card">
      <h3>Coupling: how tightly parts are tied together</h3>
      <p>Whenever one part of the code relies on another, a change in one can ripple into the other. Some of this is normal and necessary.</p>
      <p>Parts that many others rely on are risky to change, because a mistake spreads to everything that uses them. Parts that rely on many others break easily, because any of those can change under them. Fewer connections, all pointing the same way, make code cheaper to change, test and hand over.</p>
    </div>
    <div class="card">
      <h3>Cycles: parts that depend on each other in a loop</h3>
      <p>A cycle is a loop: A relies on B, and B, directly or through others, relies back on A. ${e(p.cycle)}</p>
      <p>Work on any part of a loop tends to drag in all of it, and a bug in one part can surface in all of them. Breaking a loop is usually the first thing worth fixing, because it makes every part in it easier to work with.</p>
    </div>
  </div>
</section>

<section id="map" aria-labelledby="map-title">
  <h2 id="map-title">Map of dependencies</h2>
  <p class="lead">Each circle is a part of the code; each arrow points from a part to something it relies on. Click a circle to see its numbers and connections, drag to move around, and scroll or pinch to zoom.${mapNote}</p>
  <div class="toolbar">
    <input type="search" id="map-search" list="map-names" placeholder="Find a part by name" aria-label="Find a part by name">
    <datalist id="map-names"></datalist>
    <button type="button" id="map-labels" aria-pressed="false">Show all names</button>
    <button type="button" id="map-reset">Reset view</button>
    <button type="button" id="map-dot">Download Graphviz (.dot)</button>
  </div>
  <div class="map-layout">
    <div class="card map" id="map-canvas">
      <noscript><div class="map-empty">The map needs JavaScript. Everything it shows is also in the tables below.</div></noscript>
    </div>
    <aside class="card details" id="map-details" aria-live="polite">
      <h3>Pick a part</h3>
      <p class="muted">Click a circle on the map, or a name in the tables below, to see what it relies on and what relies on it.</p>
    </aside>
  </div>
  <div class="legend" aria-label="Legend">
    <span class="item"><span class="ramp" aria-hidden="true"></span> Instability: from 0 (others lean on it) to 1 (it leans on others)</span>
    <span class="item"><span class="swatch none" aria-hidden="true"></span> Not connected to other parts</span>
    <span class="item"><span class="swatch cycle" aria-hidden="true"></span> Red ring and arrows: part of a cycle</span>
    <span class="item">Bigger circle: more parts rely on it</span>
  </div>
</section>

<section id="cycles" aria-labelledby="cycles-title">
  <h2 id="cycles-title">Cycles</h2>
  ${cycleSection}
</section>

<section id="hotspots" aria-labelledby="hotspots-title">
  <h2 id="hotspots-title">Where to look first</h2>
  <div class="two-col">
    <div class="card">
      <h3>Most relied upon</h3>
      <p class="muted small">${e(p.fan_in)} Changes here ripple the furthest, so change them carefully and keep them well tested.</p>
      ${reliedOn.length === 0 ? `<p class="muted">Nothing relies on any other part.</p>` : rank(reliedOn, "fan_in")}
    </div>
    <div class="card">
      <h3>Relies on the most</h3>
      <p class="muted small">${e(p.fan_out)} These break most easily when something they rely on changes.</p>
      ${leaning.length === 0 ? `<p class="muted">No part relies on another.</p>` : rank(leaning, "fan_out")}
    </div>
  </div>
</section>

<section id="parts" aria-labelledby="parts-title">
  <h2 id="parts-title">Every part</h2>
  <p class="lead">All the numbers, one row per part. Click a column heading to sort, or a name to find it on the map.</p>
  <div class="card table-wrap">
    <table id="parts-table">
      <thead>
        <tr>
          <th scope="col" data-key="id"><button type="button">Part</button></th>
          <th scope="col" class="num" data-key="fan_in" title="${e(p.fan_in)}"><button type="button">Relied on by</button></th>
          <th scope="col" class="num" data-key="fan_out" title="${e(p.fan_out)}"><button type="button">Relies on</button></th>${clusterHeadings}
          <th scope="col" class="num" data-key="instability" title="${e(p.instability)}"><button type="button">Instability</button></th>
          <th scope="col" class="num" data-key="external" title="${e(p.external)}"><button type="button">Packages</button></th>
          <th scope="col" class="num" data-key="unresolved" title="${e(p.unresolved)}"><button type="button">Untraced</button></th>
          <th scope="col" data-key="cycle"><button type="button">Cycle</button></th>
        </tr>
      </thead>
      <tbody>
${rows}
      </tbody>
    </table>
  </div>
</section>

<section id="outside" aria-labelledby="outside-title">
  <h2 id="outside-title">Outside the project</h2>
  <div class="two-col">
    <div class="card">
      <h3>Third-party packages</h3>
      <p class="muted small">Code the project uses but does not own. Each package is a dependency on someone else's release schedule.</p>
      ${packages.length === 0 ? `<p class="muted">None used directly.</p>` : folding(packages, packageItem, "more package")}
    </div>
    <div class="card">
      <h3>References we could not trace</h3>
      <p class="muted small">${e(p.unresolved)}</p>
      ${unresolved.length === 0 ? `<p class="muted">None. Every reference was traced.</p>` : folding(unresolved, referenceItem, "more reference")}
    </div>
  </div>
</section>
${groups}
<section id="glossary" aria-labelledby="glossary-title">
  <h2 id="glossary-title">How to read the numbers</h2>
  <dl class="glossary">
    <dt>Part</dt><dd>${e(grouping)}</dd>
    <dt>Relied on by (fan-in)</dt><dd>${e(p.fan_in)}</dd>
    <dt>Relies on (fan-out)</dt><dd>${e(p.fan_out)}</dd>${
      clustered
        ? `
      <dt>Files relying on it (Ca)</dt><dd>${e(p.ca)}</dd>
      <dt>Files it relies on (Ce)</dt><dd>${e(p.ce)}</dd>`
        : ""
    }
    <dt>Instability</dt><dd>${e(p.instability)} Neither end is bad in itself: what matters is that parts others lean on stay stable, and that unstable parts are the ones you expect to change. "None" means the part has no connections to other parts.</dd>
    <dt>Packages</dt><dd>${e(p.external)}</dd>
    <dt>Untraced</dt><dd>${e(p.unresolved)}</dd>
    <dt>Cycle</dt><dd>${e(p.cycle)}</dd>
  </dl>
</section>

<footer>
  <p>Made with ${e(generator)}, an open-source tool following the ideas of Martin Blais's snakefood. The map can also be opened in Graphviz with the .dot download.</p>
</footer>

</main>
<script type="application/json" id="untangled-data">${scriptJson(data)}</script>
<script>
${asset("report.js")}
</script>
</body>
</html>
`;
}

/** Escapes text for HTML, quotes included. */
export function e(text: string | number): string {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

/** "3 files", "1 group": counts with the right noun. */
export function count(value: number, singular: string, plural?: string): string {
  return `${formatNumber(value)} ${value === 1 ? singular : (plural ?? `${singular}s`)}`;
}

/** A whole number as shown to readers, with thousands separated: "6,426". */
export function formatNumber(value: number): string {
  return formatFixed(value, 0);
}

/** The instability value as shown to readers: two decimals, or "none" when undefined. */
export function formatInstability(value: number | null): string {
  return value === null ? "none" : formatFixed(value, 2);
}

/** A readable name for an unresolved node id such as `unresolved:module:left-pad`. */
export function unresolvedName(id: string): string {
  const first = id.indexOf(":");
  const second = first === -1 ? -1 : id.indexOf(":", first + 1);
  return second === -1 ? id : `${id.slice(second + 1)} (${id.slice(first + 1, second)})`;
}

/** A number with `digits` decimals, rounded half away from zero, and thousands separated by commas. */
export function formatFixed(value: number, digits: number): string {
  const text = String(Math.abs(value));
  const rounded = text.includes("e") ? Math.abs(value) : Number(`${Math.round(Number(`${text}e${digits}`))}e-${digits}`);
  const [whole, fraction] = rounded.toFixed(digits).split(".");
  const grouped = whole!.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${value < 0 && rounded !== 0 ? "-" : ""}${grouped}${fraction === undefined ? "" : `.${fraction}`}`;
}

function describeGrouping(clustering: string | null, language: string): string {
  if (clustering === null) {
    return "Each part is one file.";
  }
  if (clustering === "rules") {
    return "Each part is a group of files, as set by a rules file.";
  }
  const [strategy, depth] = clustering.split(":");
  const levels = count(Number(depth), "level");
  // Python has packages where PHP has namespaces; JavaScript has neither, so namespace:N
  // groups by folder.
  const namespace = language === "python" ? "package path" : language === "typescript" ? "folder path" : "namespace";
  return strategy === "namespace"
    ? `Each part is a group of files that share the first ${levels} of their ${namespace}.`
    : `Each part is a group of files that share the first ${levels} of their folder path.`;
}

/** The units with the highest non-zero metric, highest first. */
function top(units: Unit[], metric: "fan_in" | "fan_out"): Unit[] {
  return units
    .filter((unit) => unit[metric] > 0)
    .sort((a, b) => b[metric] - a[metric] || compareText(a.id, b.id))
    .slice(0, TOP);
}

/** JSON that is safe inside a script element, written as PHP's json_encode writes it. */
function scriptJson(data: unknown): string {
  return JSON.stringify(data)
    .replaceAll("<", "\\u003C")
    .replaceAll(">", "\\u003E")
    .replaceAll("&", "\\u0026")
    .replaceAll(" ", "\\u2028")
    .replaceAll(" ", "\\u2029");
}

function asset(name: string): string {
  return readFileSync(new URL(`../../assets/${name}`, import.meta.url), "utf8");
}
