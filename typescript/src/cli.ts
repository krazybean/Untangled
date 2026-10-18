// SPDX-License-Identifier: MIT
// `untangled <command> [options]`. The command and option names are shared by every Untangled
// library: `scan`, `analyze` and `report`.

import { writeFileSync } from "node:fs";

import { ProjectError } from "./scanner/project.js";
import { scan } from "./scanner/scanner.js";
import { NAME, VERSION } from "./version.js";

export const USAGE = `\
Usage: untangled scan [<path>] [--dev] [--source=<path>]... [--aliases=<file.json>]...
                      [--format=json|snakefood] [--output=<file>]

Commands:
  scan       Write the dependency pairs of a JavaScript/TypeScript project (default path: .)
  analyze    Not in the TypeScript library yet: use the PHP or Python library on a pairs document
  report     Not in the TypeScript library yet: use the PHP or Python library on a pairs document

Options:
  --dev              Also scan tests (*.test.*, *.spec.*, and __tests__, __mocks__, test and
                     tests folders)
  --source=PATH      Scan the code files in PATH, a folder or file relative to the project, even
                     when they are build output (dist, build, coverage, outDir) or tests (repeatable)
  --aliases=FILE     Read import aliases from FILE, a JSON object shaped like tsconfig's paths
                     with paths relative to the project, for aliases set in bundler configuration
                     (repeatable)
  --format=FORMAT    json (default, the Untangled pairs document) or snakefood
  --output=FILE      Write to FILE instead of standard output
  -h, --help         Show this help
  -V, --version      Show the version
`;

const COMMANDS: Record<string, Set<string>> = {
  scan: new Set(["dev", "source", "aliases", "format", "output"]),
};
const LATER = new Set(["analyze", "report"]);
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
      }
      continue;
    }
    positional.push(arg);
  }

  const command = positional.shift();
  if (command !== undefined && LATER.has(command)) {
    throw new Usage(
      `untangled ${command} is not in the TypeScript library yet; run \`untangled scan --output=pairs.json\` here,` +
        ` then \`untangled ${command} pairs.json\` with the PHP or Python library`,
    );
  }
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
    if (name !== "dev" && typeof value !== "string") {
      throw new Usage(`Option --${name} needs a value, as in --${name}=...`);
    }
  }

  const format = options.get("format") ?? "json";
  if (format !== "json" && format !== "snakefood") {
    throw new Usage(`Unknown format: ${String(format)}`);
  }
  const path = positional[0] ?? ".";
  let result;
  try {
    result = scan(path, { dev: options.has("dev"), sources: repeated.source!, aliases: repeated.aliases! });
  } catch (error) {
    if (error instanceof ProjectError) {
      throw new Failure(error.message);
    }
    throw error;
  }
  for (const warning of result.warnings) {
    err.write(`warning: ${warning}\n`);
  }
  const text = format === "json" ? result.pairs.toJson() : result.pairs.toSnakefood(path);
  const output = options.get("output");
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
}
