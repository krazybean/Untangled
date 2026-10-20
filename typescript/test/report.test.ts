// SPDX-License-Identifier: MIT

import { describe, expect, test } from "vitest";

import { Clustering } from "../src/analysis/clustering.js";
import { Filter } from "../src/analysis/filter.js";
import { PairsDocument } from "../src/graph.js";
import { renderDot, quote } from "../src/report/dot.js";
import { count, e, formatFixed, formatInstability, LIST_LIMIT, MAP_LIMIT, PLAIN, renderHtml, UNREAD_LINE, unresolvedName } from "../src/report/html.js";
import { Report } from "../src/report/report.js";
import { build } from "./helpers.js";

const cyclic = (): Report =>
  Report.build(
    "shop",
    new Filter().apply(
      build(["src/a.ts -> src/b.ts", "src/b.ts -> src/a.ts", "src/b.ts -> lib/c.ts", "src/a.ts -> npm:react", "lib/c.ts -> unresolved:module:x", "lib/c.ts -> builtin:fs", "d.ts"]),
    ),
  );

describe("report", () => {
  test("cycles, unit edges and targets", () => {
    const report = cyclic();
    expect([...report.cycleOf()]).toEqual([["src/a.ts", 1], ["src/b.ts", 1]]);
    expect(report.unitEdges()).toEqual([
      { from: "src/a.ts", to: "src/b.ts", count: 1, cycle: true },
      { from: "src/b.ts", to: "lib/c.ts", count: 1, cycle: false },
      { from: "src/b.ts", to: "src/a.ts", count: 1, cycle: true },
    ]);
    expect([...report.targets("external")]).toEqual([["npm:react", ["src/a.ts"]]]);
    expect([...report.targets("unresolved")]).toEqual([["unresolved:module:x", ["lib/c.ts"]]]);
  });

  test("the map keeps the most connected units, in analysis order", () => {
    const report = Report.build("x", build(["a.ts -> b.ts", "c.ts -> b.ts", "d.ts -> b.ts", "e.ts"]));
    expect(report.mapUnits(10)).toEqual(["a.ts", "b.ts", "c.ts", "d.ts", "e.ts"]);
    expect(report.mapUnits(2)).toEqual(["a.ts", "b.ts"]);
  });

  test("clustered reports count the edges inside each cluster", () => {
    const report = Report.build("x", build(["src/a.ts -> src/b.ts", "src/a.ts -> lib/c.ts"]), Clustering.byFolder(1));
    expect(report.isClustered()).toBe(true);
    expect([...report.dropped]).toEqual([["src", 1]]);
  });
});

describe("dot", () => {
  test("default style highlights cycles", () => {
    expect(renderDot(cyclic())).toBe(`digraph untangled {
  graph [rankdir=LR, fontname="Helvetica"];
  node [shape=box, style=rounded, fontname="Helvetica"];
  edge [color="#898781"];

  "d.ts";
  "lib/c.ts";
  "src/a.ts" [color="#d03b3b", penwidth=2];
  "src/b.ts" [color="#d03b3b", penwidth=2];

  "src/a.ts" -> "src/b.ts" [color="#d03b3b", penwidth=2];
  "src/b.ts" -> "lib/c.ts";
  "src/b.ts" -> "src/a.ts" [color="#d03b3b", penwidth=2];
}
`);
  });

  test("classic style draws packages and unresolved references in white, not builtins", () => {
    expect(renderDot(cyclic(), "classic")).toBe(`digraph untangled {
  graph [rankdir=LR];
  node [shape=ellipse, style=filled, fillcolor=lightgrey, fontname="Times-Roman", fontsize=7];
  edge [color=black];

  "d.ts";
  "lib/c.ts";
  "src/a.ts";
  "src/b.ts";
  "npm:react" [fillcolor=white];
  "unresolved:module:x" [fillcolor=white];

  "lib/c.ts" -> "unresolved:module:x";
  "src/a.ts" -> "npm:react";
  "src/a.ts" -> "src/b.ts";
  "src/b.ts" -> "lib/c.ts";
  "src/b.ts" -> "src/a.ts";
}
`);
  });

  test("clusters are labelled with their size", () => {
    const report = Report.build("x", build(["src/a.ts -> lib/c.ts", "src/b.ts"]), Clustering.byFolder(1));
    expect(renderDot(report)).toContain('  "src" [label="src\\n2 files"];\n');
    expect(renderDot(report, "classic")).toContain('  "lib" [label="lib\\n1 file"];\n');
  });

  test("an empty graph", () => {
    expect(renderDot(Report.build("x", build([])))).toBe(
      'digraph untangled {\n  graph [rankdir=LR, fontname="Helvetica"];\n  node [shape=box, style=rounded, fontname="Helvetica"];\n  edge [color="#898781"];\n}\n',
    );
  });

  test("quote", () => {
    expect(quote('App\\"x"\ny')).toBe('"App\\\\\\"x\\"\\ny"');
  });
});

describe("html", () => {
  const html = renderHtml(cyclic(), new Date(2026, 9, 19));

  test("is one self-contained page", () => {
    expect(html.startsWith("<!doctype html>\n")).toBe(true);
    expect(html).not.toMatch(/<(script|link)[^>]+(src|href)=/);
    expect(html).toContain("<title>Dependencies: shop</title>");
    expect(html).toContain("Generated 19 October 2026 by untangled-typescript");
  });

  test("states the cycles and lists their loops", () => {
    expect(html).toContain("<strong>1 dependency cycle found.</strong>");
    expect(html).toContain("2 parts of 4 (50%) are caught in a loop");
    expect(html).toContain('<span class="step mono">src/a.ts</span>');
  });

  test("sections come in the specified order", () => {
    const order = ["summary", "why", "map", "cycles", "hotspots", "parts", "outside", "glossary"].map((id) => html.indexOf(`<section id="${id}"`));
    expect(order).toEqual([...order].sort((a, b) => a - b));
    expect(order.every((index) => index > 0)).toBe(true);
  });

  test("uses the plain-language lines", () => {
    for (const line of Object.values(PLAIN)) {
      if (!line.includes("group")) {
        expect(html).toContain(e(line));
      }
    }
  });

  test("embeds the data and the DOT graph as safe JSON", () => {
    const json = /<script type="application\/json" id="untangled-data">(.*)<\/script>/.exec(html)![1]!;
    const data = JSON.parse(json) as { units: { id: string; cycle: number | null }[]; dot: string; drawn: unknown };
    expect(data.units.map((unit) => [unit.id, unit.cycle])).toEqual([["d.ts", null], ["lib/c.ts", null], ["src/a.ts", 1], ["src/b.ts", 1]]);
    expect(data.dot).toBe(renderDot(cyclic()));
    expect(data.drawn).toBeNull();
    expect(json).not.toContain("<");
  });

  test("escapes names in markup and data", () => {
    const page = renderHtml(Report.build("<b>", build(["<x>.ts -> a&b.ts"])));
    expect(page).toContain("&lt;x&gt;.ts");
    expect(page).toContain("<title>Dependencies: &lt;b&gt;</title>");
    expect(page).toContain("\\u003Cx\\u003E.ts");
    expect(page).not.toContain("<x>");
  });

  test("lists the files that could not be read", () => {
    const files = build(["a.ts -> b.ts"]);
    files.addNode("broken.ts", "internal", { error: "parse" });
    files.addNode("locked.ts", "internal", { error: "read" });
    const page = renderHtml(Report.build("x", files));
    expect(page).toContain('<div class="value">2</div><div class="label">files we could not read</div>');
    expect(page).toContain('<li><span class="mono">broken.ts</span><span class="count">does not parse</span></li>');
    expect(page).toContain('<li><span class="mono">locked.ts</span><span class="count">cannot be read</span></li>');
    expect(page).toContain(UNREAD_LINE);
    expect(renderHtml(Report.build("x", build(["a.ts -> b.ts"])))).not.toContain("could not read");

    const many = new PairsDocument("typescript");
    for (let index = 0; index < LIST_LIMIT + 2; index++) {
      many.addNode(`f${String(index).padStart(2, "0")}.ts`, "internal", { error: "parse" });
    }
    expect(renderHtml(Report.build("x", many, Clustering.fromString("folder:1")))).toContain("<summary>2 more files</summary>");
  });

  test("lists packages and untraced references", () => {
    expect(html).toContain('<span class="mono">react</span><span class="count">used by 1 part</span>');
    expect(html).toContain('<span class="mono">x (module)</span><span class="count">in 1 part</span>');
  });

  test("no cycles, an empty project, clusters", () => {
    expect(renderHtml(Report.build("x", build(["a.ts -> b.ts"])))).toContain("<strong>No dependency cycles.</strong>");
    expect(renderHtml(Report.build("x", build([])))).toContain("No source files were found to analyze");
    const clustered = renderHtml(Report.build("x", build(["src/a.ts -> lib/b.ts"]), Clustering.fromString("namespace:1")));
    expect(clustered).toContain("Each part is a group of files that share the first 1 level of their folder path.");
    expect(clustered).toContain('<section id="groups"');
  });

  test("long lists fold away, big maps say what they leave out", () => {
    const lines = Array.from({ length: MAP_LIMIT + 1 }, (_, index) => `f${index}.ts -> npm:p${index % (LIST_LIMIT + 2)}`);
    const page = renderHtml(Report.build("x", build(lines)));
    expect(page).toContain("<summary>2 more packages</summary>");
    expect(page).toContain(`The map shows the ${MAP_LIMIT} parts with the most connections</strong>, out of ${MAP_LIMIT + 1}`);
  });
});

describe("formatting", () => {
  test("numbers", () => {
    expect(count(1, "part")).toBe("1 part");
    expect(count(6426, "dependency", "dependencies")).toBe("6,426 dependencies");
    expect(formatInstability(null)).toBe("none");
    expect(formatInstability(0.125)).toBe("0.13");
    expect(formatInstability(1)).toBe("1.00");
    expect(formatFixed(1.25, 1)).toBe("1.3");
    expect(formatFixed(1234567.891, 2)).toBe("1,234,567.89");
  });

  test("unresolved names", () => {
    expect(unresolvedName("unresolved:module:@/x")).toBe("@/x (module)");
    expect(unresolvedName("unresolved:dynamic:`./p/${a}`")).toBe("`./p/${a}` (dynamic)");
    expect(unresolvedName("plain")).toBe("plain");
  });

  test("escape", () => {
    expect(e(`<a href="x">'&'</a>`)).toBe("&lt;a href=&quot;x&quot;&gt;&#039;&amp;&#039;&lt;/a&gt;");
  });
});
