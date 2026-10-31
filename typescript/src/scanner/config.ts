// SPDX-License-Identifier: MIT
// What the scanner reads from package.json, tsconfig.json or jsconfig.json, and --aliases
// files (spec/languages/typescript.md, "Resolving an import", steps 2, 3 and 5).

import { existsSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import { decode } from "../text.js";
import { parseJsonc } from "./jsonc.js";
import { folderOf, joinPath } from "./paths.js";
import { warningDiagnostic, type Diagnostic } from "../diagnostics.js";

/** One key of `paths` or `imports`: exact, or with one `*`. */
export interface Pattern {
  prefix: string;
  /** Text after the `*`, or undefined for an exact key. */
  suffix: string | undefined;
  targets: string[];
}

/** A set of aliases whose targets are project-relative paths (with `*` where the key has one). */
export interface AliasSource {
  patterns: Pattern[];
}

/** What the scanner reads from one package.json. */
export interface Package {
  /** Names declared in its dependency fields. */
  declared: Set<string>;
  /** Its `imports`, targets as written (`./src/x.js` or a package specifier). */
  imports: Pattern[];
}

export interface Config {
  aliases: AliasSource[];
  /** compilerOptions.baseUrl as a project-relative folder. */
  baseUrl: string | undefined;
  /** compilerOptions.outDir as a project-relative folder. */
  outDir: string | undefined;
  diagnostics: Diagnostic[];
}

const DEPENDENCY_FIELDS = ["dependencies", "devDependencies", "peerDependencies", "optionalDependencies"];

export function loadConfig(root: string, aliasFiles: string[]): Config {
  const diagnostics: Diagnostic[] = [];
  const config: Config = { aliases: [], baseUrl: undefined, outDir: undefined, diagnostics };

  for (const file of aliasFiles) {
    // The file is named on the command line, so relative to the working folder; its targets
    // are relative to the project root.
    const data = readJson("", file, diagnostics, true);
    if (data === undefined) {
      continue;
    }
    if (!isObject(data)) {
      diagnostics.push(warningDiagnostic("aliases-ignored", `--aliases=${file}: not a JSON object of aliases; ignored`));
      continue;
    }
    config.aliases.push({ patterns: patterns(data, (target) => targetList(target), (path) => joinPath("", path)) });
  }

  const tsconfig = existsSync(join(root, "tsconfig.json")) ? "tsconfig.json" : "jsconfig.json";
  if (existsSync(join(root, tsconfig))) {
    const options = compilerOptions(root, tsconfig, diagnostics, new Set());
    if (options.baseUrl !== undefined) {
      config.baseUrl = options.baseUrl;
    }
    if (options.outDir !== undefined) {
      config.outDir = options.outDir;
    }
    if (options.paths !== undefined) {
      const base = options.baseUrl ?? options.pathsFolder ?? "";
      config.aliases.push({
        patterns: patterns(options.paths, (target) => targetList(target), (path) => joinPath(base, path)),
      });
    }
  }
  return config;
}

/** A package.json of the project, by id; undefined when it cannot be read. */
export function readPackage(root: string, id: string, diagnostics: Diagnostic[]): Package | undefined {
  const manifest = readJson(root, id, diagnostics);
  if (!isObject(manifest)) {
    return undefined;
  }
  const result: Package = { declared: new Set(), imports: [] };
  for (const field of DEPENDENCY_FIELDS) {
    const dependencies = manifest[field];
    if (isObject(dependencies)) {
      for (const name of Object.keys(dependencies)) {
        result.declared.add(name);
      }
    }
  }
  if (isObject(manifest.imports)) {
    result.imports = patterns(manifest.imports, (target) => firstString(target));
  }
  return result;
}

interface CompilerOptions {
  paths?: Record<string, unknown>;
  /** The folder of the file that declares `paths`. */
  pathsFolder?: string;
  baseUrl?: string;
  outDir?: string;
}

/** compilerOptions after following `extends` to files in the project; the extending file wins. */
function compilerOptions(root: string, file: string, diagnostics: Diagnostic[], seen: Set<string>): CompilerOptions {
  if (seen.has(file)) {
    return {};
  }
  seen.add(file);
  const data = readJson(root, file, diagnostics);
  if (!isObject(data)) {
    return {};
  }
  let options: CompilerOptions = {};
  const bases = typeof data.extends === "string" ? [data.extends] : Array.isArray(data.extends) ? data.extends : [];
  for (const base of bases) {
    // Only files in the project: a package such as @tsconfig/node22 holds no paths of the project.
    if (typeof base !== "string" || !(base.startsWith("./") || base.startsWith("../"))) {
      continue;
    }
    let path = joinPath(folderOf(file), base);
    if (path !== undefined && !isFile(join(root, path)) && isFile(join(root, path + ".json"))) {
      path += ".json";
    }
    if (path !== undefined && isFile(join(root, path))) {
      options = { ...options, ...compilerOptions(root, path, diagnostics, seen) };
    }
  }
  const own = isObject(data.compilerOptions) ? data.compilerOptions : {};
  const folder = folderOf(file);
  if (isObject(own.paths)) {
    options.paths = own.paths;
    options.pathsFolder = folder;
  }
  for (const key of ["baseUrl", "outDir"] as const) {
    const value = own[key];
    if (typeof value === "string") {
      const path = joinPath(folder, value);
      if (path !== undefined) {
        options[key] = path;
      }
    }
  }
  return options;
}

function patterns(
  data: Record<string, unknown>,
  targets: (value: unknown) => string[],
  map: (path: string) => string | undefined = (path) => path,
): Pattern[] {
  const result: Pattern[] = [];
  for (const [key, value] of Object.entries(data)) {
    const star = key.indexOf("*");
    if (star !== key.lastIndexOf("*")) {
      continue;
    }
    const mapped = targets(value)
      .map((target) => map(target))
      .filter((target): target is string => target !== undefined);
    result.push({
      prefix: star === -1 ? key : key.slice(0, star),
      suffix: star === -1 ? undefined : key.slice(star + 1),
      targets: mapped,
    });
  }
  return result;
}

/** The text a pattern's `*` matched in a specifier, "" for an exact key, or undefined. */
export function match(pattern: Pattern, specifier: string): string | undefined {
  if (pattern.suffix === undefined) {
    return specifier === pattern.prefix ? "" : undefined;
  }
  if (
    specifier.length >= pattern.prefix.length + pattern.suffix.length &&
    specifier.startsWith(pattern.prefix) &&
    specifier.endsWith(pattern.suffix)
  ) {
    return specifier.slice(pattern.prefix.length, specifier.length - pattern.suffix.length);
  }
  return undefined;
}

/** The matching pattern with the longest text before its `*` (an exact key first). */
export function bestMatch(list: Pattern[], specifier: string): [Pattern, string] | undefined {
  let best: [Pattern, string] | undefined;
  for (const pattern of list) {
    const star = match(pattern, specifier);
    if (star === undefined) {
      continue;
    }
    const length = pattern.suffix === undefined ? Infinity : pattern.prefix.length;
    const bestLength = best === undefined ? -1 : best[0].suffix === undefined ? Infinity : best[0].prefix.length;
    if (length > bestLength) {
      best = [pattern, star];
    }
  }
  return best;
}

function targetList(value: unknown): string[] {
  if (typeof value === "string") {
    return [value];
  }
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

/** The first string in a package.json conditions object, depth first in the order written. */
function firstString(value: unknown): string[] {
  if (typeof value === "string") {
    return [value];
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      const found = firstString(item);
      if (found.length) {
        return found;
      }
    }
  } else if (isObject(value)) {
    for (const item of Object.values(value)) {
      const found = firstString(item);
      if (found.length) {
        return found;
      }
    }
  }
  return [];
}

function readJson(root: string, file: string, diagnostics: Diagnostic[], required = false): unknown {
  const path = root ? join(root, file) : file;
  if (!existsSync(path)) {
    if (required) {
      diagnostics.push(warningDiagnostic("aliases-ignored", `--aliases=${file}: no such file`));
    }
    return undefined;
  }
  try {
    return parseJsonc(decode(readFileSync(path)));
  } catch (error) {
    const message = `${file}: cannot read it (${(error as Error).message}); ignoring it`;
    // An --aliases file is named relative to the working folder, not the project.
    diagnostics.push(root ? warningDiagnostic("config-unreadable", message, [file]) : warningDiagnostic("aliases-ignored", message));
    return undefined;
  }
}

function isFile(path: string): boolean {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
