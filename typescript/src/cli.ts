// SPDX-License-Identifier: MIT
// `untangled <command> [options]`. The command and option names are shared by every Untangled
// library: `scan`, `analyze` and `report`.

import { readFileSync, statSync, writeFileSync } from "node:fs";
import { basename, join, resolve } from "node:path";

import { AnalysisError, analyze } from "./analysis/analyzer.js";
import { Clustering } from "./analysis/clustering.js";
import { DependentsError, findDependents, renderDependentsText } from "./analysis/dependents.js";
import { Filter } from "./analysis/filter.js";
import { DocumentError, encode, PairsDocument } from "./graph.js";
import { renderDot, STYLES } from "./report/dot.js";
import { renderHtml } from "./report/html.js";
import { Report } from "./report/report.js";
import { ProjectError } from "./scanner/project.js";
import { scan, type ScanOptions } from "./scanner/scanner.js";
import { decode } from "./text.js";
import { NAME, VERSION } from "./version.js";

export const USAGE = `\
Usage: untangled scan [<path>] [--dev] [--source=<path>]... [--aliases=<file.json>]...
                      [--format=json|snakefood] [--output=<file>]
       untangled analyze [<path>|<pairs.json>] [scan options] [--cluster=<strategy>]
                         [--include=<glob>]... [--exclude=<glob>]... [--output=<file>]
       untangled report [<path>|<pairs.json>] [--format=html|dot] [--style=classic]
                         [--title=<text>] [analyze options]
       untangled dependents [<path>|<pairs.json>] <file-or-symbol>... [--transitive]
                            [--format=text|json] [analyze options]

Commands:
  scan       Write the dependency pairs of a JavaScript/TypeScript project (default path: .)
  analyze    Write cycles and coupling metrics for a project or a pairs document
  report     Write a readable HTML report (or a Graphviz DOT graph) of the analysis
  dependents List the files that depend on files or declared symbols

Options:
  --dev              Also scan tests (*.test.*, *.spec.*, and __tests__, __mocks__, test and
                     tests folders)
  --source=PATH      Scan the code files in PATH, a folder or file relative to the project, even
                     when they are build output (dist, build, coverage, outDir) or tests (repeatable)
  --aliases=FILE     Read import aliases from FILE, a JSON object shaped like tsconfig's paths
                     with paths relative to the project, for aliases set in bundler configuration
                     (repeatable)
  --format=FORMAT    scan: json (default, the Untangled pairs document) or snakefood
                     report: html (default) or dot
                     dependents: text (default) or json
  --transitive       dependents: also the files that depend on a dependent, with their depth
  --style=STYLE      report --format=dot only: default, or classic for snakefood's
                     black and white sfood-graph look
  --title=TEXT       report only: the report's title (default: the name in package.json)
  --cluster=STRATEGY analyze, report: namespace:N, folder:N or rules:<file>
                     (JavaScript has no namespaces, so namespace:N groups by folder)
  --include=GLOB     analyze, report: keep files matching GLOB (repeatable, last match wins)
  --exclude=GLOB     analyze, report: drop files matching GLOB (repeatable, last match wins)
  --output=FILE      Write to FILE instead of standard output
  -h, --help         Show this help
  -V, --version      Show the version
`;

const SCAN = ["dev", "source", "aliases"];
const COMMANDS: Record<string, Set<string>> = {
  scan: new Set([...SCAN, "format", "output"]),
  analyze: new Set([...SCAN, "cluster", "include", "exclude", "output"]),
  report: new Set([...SCAN, "cluster", "include", "exclude", "output", "format", "style", "title"]),
  dependents: new Set([...SCAN, "transitive", "include", "exclude", "output", "format"]),
};
const REPEATABLE = new Set(["source", "aliases"]);

export interface Writer {
  write(text: string): unknown;
}

class Usage extends Error {}
class Failure extends Error {}

export function main(argv: string[], out: Writer = process.stdout, err: Writer = process.stderr): number {
  try {
    return run(argv, out, err);
  } catch (error) {
    if (error instanceof Usage) {
      err.write(`${error.message}\n`);
      return 2;
    }
    if (error instanceof Failure) {
      err.write(`error: ${error.message}\n`);
      return 1;
    }
    throw error;
  }
}

function run(args: string[], out: Writer, err: Writer): number {
  const positional: string[] = [];
  const options = new Map<string, string | true>();
  const repeated: Record<string, string[]> = { source: [], aliases: [] };
  // Order matters for these, so they are kept as a list rather than by name.
  const patterns: ["include" | "exclude", string][] = [];
  for (const arg of args) {
    if (arg === "-h" || arg === "--help") {
      out.write(USAGE);
      return 0;
    }
    if (arg === "-V" || arg === "--version") {
      out.write(`${NAME} ${VERSION}\n`);
      return 0;
    }
    if (arg.startsWith("--")) {
      const equals = arg.indexOf("=");
      const name = equals === -1 ? arg.slice(2) : arg.slice(2, equals);
      const value = equals === -1 ? true : arg.slice(equals + 1);
      options.set(name, value);
      if (typeof value === "string" && REPEATABLE.has(name)) {
        repeated[name]!.push(value);
      } else if (typeof value === "string" && (name === "include" || name === "exclude")) {
        patterns.push([name, value]);
      }
      continue;
    }
    positional.push(arg);
  }

  const command = positional.shift();
  const allowed = command === undefined ? undefined : COMMANDS[command];
  if (allowed === undefined) {
    throw new Usage(command === undefined ? USAGE.trimEnd() : `Unknown command: ${command}\n\n${USAGE.trimEnd()}`);
  }
  for (const [name, value] of options) {
    if (!allowed.has(name)) {
      throw new Usage(`Unknown option for ${command}: --${name}`);
    }
    if (name === "dev" && value !== true) {
      throw new Usage("Option --dev takes no value");
    }
    if (name === "transitive" && value !== true) {
      throw new Usage("Option --transitive takes no value");
    }
    if (name !== "dev" && name !== "transitive" && typeof value !== "string") {
      throw new Usage(`Option --${name} needs a value, as in --${name}=...`);
    }
  }

  const path = positional[0] ?? ".";
  const scanOptions: ScanOptions = { dev: options.has("dev"), sources: repeated.source!, aliases: repeated.aliases! };
  const output = options.get("output");
  const write = (text: string): number => {
    if (typeof output !== "string") {
      out.write(text);
      return 0;
    }
    try {
      writeFileSync(output, text, "utf8");
    } catch {
      throw new Failure(`cannot write ${output}`);
    }
    return 0;
  };

  if (command === "scan") {
    const format = options.get("format") ?? "json";
    if (format !== "json" && format !== "snakefood") {
      throw new Usage(`Unknown format: ${String(format)}`);
    }
    const pairs = scanProject(path, scanOptions, err);
    return write(format === "json" ? pairs.toJson() : pairs.toSnakefood(path));
  }

  if (command === "dependents") {
    return dependents(positional, options, patterns, scanOptions, write, err);
  }

  const format = options.get("format") ?? "html";
  if (command === "report" && format !== "html" && format !== "dot") {
    throw new Usage(`Unknown format: ${String(format)}`);
  }
  const style = options.get("style") ?? "default";
  if (typeof style !== "string" || !STYLES.includes(style)) {
    throw new Usage(`Unknown style: ${String(style)}`);
  }
  if (options.has("style") && format !== "dot") {
    throw new Usage("--style only applies to --format=dot");
  }
  const clustering = parseClustering(options.get("cluster"));

  const pairs = loadPairs(path, scanOptions, err);

  const filter = new Filter();
  for (const [kind, glob] of patterns) {
    if (kind === "include") {
      filter.include(glob);
    } else {
      filter.exclude(glob);
    }
  }
  try {
    if (command === "analyze") {
      return write(encode(analyze(filter.apply(pairs), clustering)));
    }
    const title = options.get("title");
    const report = Report.build(typeof title === "string" ? title : defaultTitle(path), filter.apply(pairs), clustering);
    return write(format === "dot" ? renderDot(report, style) : renderHtml(report));
  } catch (error) {
    throw error instanceof AnalysisError ? new Failure(error.message) : error;
  }
}

/** The source is the first argument when it is a folder or a .json file, else the current folder; the rest are the targets. */
function dependents(
  positional: string[],
  options: Map<string, string | true>,
  patterns: ["include" | "exclude", string][],
  scanOptions: ScanOptions,
  write: (text: string) => number,
  err: Writer,
): number {
  const format = options.get("format") ?? "text";
  if (format !== "text" && format !== "json") {
    throw new Usage(`Unknown format: ${String(format)}`);
  }
  const first = positional[0];
  const hasSource = first !== undefined && (isDirectory(first) || (isFile(first) && first.toLowerCase().endsWith(".json")));
  const targets = hasSource ? positional.slice(1) : positional;
  if (targets.length === 0) {
    throw new Usage("dependents needs at least one file or symbol to look up");
  }
  const pairs = loadPairs(hasSource ? first : ".", scanOptions, err);
  const filter = new Filter();
  for (const [kind, glob] of patterns) {
    if (kind === "include") {
      filter.include(glob);
    } else {
      filter.exclude(glob);
    }
  }
  try {
    const document = findDependents(pairs, targets, options.has("transitive"), filter);
    return write(format === "json" ? encode(document) : renderDependentsText(document));
  } catch (error) {
    throw error instanceof DependentsError ? new Failure(error.message) : error;
  }
}

/** Reads a pairs document, or scans a project, and writes the warnings to standard error. */
function loadPairs(path: string, options: ScanOptions, err: Writer): PairsDocument {
  if (!isFile(path)) {
    return scanProject(path, options, err);
  }
  const warnings: string[] = [];
  let data: unknown;
  try {
    data = JSON.parse(decode(readFileSync(path)));
  } catch (error) {
    throw new Failure(error instanceof SyntaxError ? `${path} is not valid JSON: ${error.message}` : `cannot read ${path}`);
  }
  let pairs: PairsDocument;
  try {
    pairs = PairsDocument.fromObject(data, warnings);
  } catch (error) {
    throw error instanceof DocumentError ? new Failure(error.message) : error;
  }
  for (const warning of warnings) {
    err.write(`warning: ${warning}\n`);
  }
  return pairs;
}

function scanProject(path: string, options: ScanOptions, err: Writer): PairsDocument {
  let result;
  try {
    result = scan(path, options);
  } catch (error) {
    throw error instanceof ProjectError ? new Failure(error.message) : error;
  }
  for (const warning of result.warnings) {
    err.write(`warning: ${warning}\n`);
  }
  return result.pairs;
}

function parseClustering(strategy: string | true | undefined): Clustering | undefined {
  if (typeof strategy !== "string") {
    return undefined;
  }
  if (strategy.startsWith("rules:")) {
    const file = strategy.slice("rules:".length);
    let text: string;
    try {
      text = decode(readFileSync(file));
    } catch {
      throw new Failure(`cannot read rules file ${file}`);
    }
    try {
      return Clustering.parseRules(text);
    } catch (error) {
      throw new Usage(`error: ${(error as Error).message}`);
    }
  }
  try {
    return Clustering.fromString(strategy);
  } catch (error) {
    throw new Usage(`error: ${(error as Error).message}`);
  }
}

/** The default report title: the name in package.json, else the folder or file name. */
function defaultTitle(path: string): string {
  if (isFile(path)) {
    return basename(path);
  }
  try {
    const name = (JSON.parse(readFileSync(join(path, "package.json"), "utf8")) as { name?: unknown }).name;
    if (typeof name === "string" && name !== "") {
      return name;
    }
  } catch {
    // No package.json, or not a readable one: use the folder name.
  }
  return basename(resolve(path));
}

function isDirectory(path: string): boolean {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}

function isFile(path: string): boolean {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
}
