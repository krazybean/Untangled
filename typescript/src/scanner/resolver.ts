// SPDX-License-Identifier: MIT
// Turns an import specifier into a target node (spec/languages/typescript.md, "Resolving an
// import").

import { existsSync } from "node:fs";
import { join } from "node:path";

import { builtinName } from "./builtins.js";
import { bestMatch, readPackage, type Config, type Package } from "./config.js";
import { folderOf, joinPath } from "./paths.js";
import { isCode, type Project } from "./project.js";

/** Where a reference points: a node id, or a non-code file that gives no edge. */
export type Target = { id: string } | { asset: string };

type Found = { file: string } | { asset: string };

const EXTENSIONS = [".ts", ".tsx", ".d.ts", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs", ".json"];
const SOURCES: Record<string, string[]> = {
  ".js": [".ts", ".tsx", ".d.ts"],
  ".jsx": [".tsx"],
  ".mjs": [".mts", ".d.mts"],
  ".cjs": [".cts", ".d.cts"],
};

export class Resolver {
  /** Bare specifiers that resolved to nothing, for the missing node_modules warning. */
  readonly unresolvedBare = new Set<string>();

  /** Per folder: the nearest package.json and its folder, if any. */
  private readonly nearest = new Map<string, [string, Package] | undefined>();
  /** Per folder: the names declared by every package.json from there up to the root. */
  private readonly declared = new Map<string, Set<string>>();

  constructor(
    private readonly project: Project,
    private readonly config: Config,
    private readonly warnings: string[],
  ) {}

  resolve(file: string, specifier: string): Target {
    if (isRelative(specifier)) {
      const query = specifier.indexOf("?");
      const written = query === -1 ? specifier : specifier.slice(0, query);
      const path = joinPath(folderOf(file), written);
      if (path === undefined) {
        return { id: `unresolved:module:${specifier}` };
      }
      return this.found(this.path(path)) ?? { id: `unresolved:module:${path}` };
    }
    if (specifier.startsWith("/")) {
      return { id: `unresolved:module:${specifier}` };
    }
    const folder = folderOf(file);
    return (
      (specifier.startsWith("#") ? this.packageImport(folder, specifier) : undefined) ??
      this.alias(specifier) ??
      this.bare(folder, specifier)
    );
  }

  /** Step 2: the `imports` of the nearest package.json. */
  private packageImport(folder: string, specifier: string): Target | undefined {
    const [base, manifest] = this.packageAt(folder) ?? ["", undefined];
    const best = manifest === undefined ? undefined : bestMatch(manifest.imports, specifier);
    const target = best?.[0].targets[0]?.replaceAll("*", best[1]);
    if (target === undefined) {
      return undefined;
    }
    if (target.startsWith("./")) {
      const path = joinPath(base, target);
      return (path === undefined ? undefined : this.found(this.path(path))) ?? { id: `unresolved:module:${path ?? target}` };
    }
    return this.bare(folder, target);
  }

  private alias(specifier: string): Target | undefined {
    for (const source of this.config.aliases) {
      const best = bestMatch(source.patterns, specifier);
      if (best === undefined) {
        continue;
      }
      for (const target of best[0].targets) {
        const path = joinPath("", target.replaceAll("*", best[1]));
        const found = path === undefined ? undefined : this.found(this.path(path));
        if (found !== undefined) {
          return found;
        }
      }
    }
    if (this.config.baseUrl !== undefined) {
      const path = joinPath(this.config.baseUrl, specifier);
      return path === undefined ? undefined : this.found(this.path(path));
    }
    return undefined;
  }

  /** Steps 4 to 6: a builtin, a package, or unresolved. */
  private bare(folder: string, specifier: string): Target {
    const declared = this.declaredAt(folder);
    const builtin = builtinName(specifier, declared);
    if (builtin !== undefined) {
      return { id: `builtin:${builtin}` };
    }
    const name = packageName(specifier);
    if (name !== undefined && (declared.has(name) || this.installed(folder, name))) {
      return { id: `npm:${name}` };
    }
    // A package with types only (`vscode`, provided at run time): the node is still the package.
    const types = name === undefined ? undefined : typesPackage(name);
    if (types !== undefined && (declared.has(types) || this.installed(folder, types))) {
      return { id: `npm:${name}` };
    }
    this.unresolvedBare.add(name ?? specifier);
    return { id: `unresolved:module:${specifier}` };
  }

  /** Whether a node_modules folder from this folder up to the root holds the package, as Node.js looks. */
  private installed(folder: string, name: string): boolean {
    for (let current: string | undefined = folder; current !== undefined; current = parent(current)) {
      if (this.project.nodeModules.has(current) && existsSync(join(this.project.root, current, "node_modules", name, "package.json"))) {
        return true;
      }
    }
    return false;
  }

  private packageAt(folder: string): [string, Package] | undefined {
    if (!this.nearest.has(folder)) {
      const id = folder ? `${folder}/package.json` : "package.json";
      const own = this.project.files.has(id) ? readPackage(this.project.root, id, this.warnings) : undefined;
      const up = parent(folder);
      this.nearest.set(folder, own !== undefined ? [folder, own] : up === undefined ? undefined : this.packageAt(up));
    }
    return this.nearest.get(folder);
  }

  private declaredAt(folder: string): Set<string> {
    let result = this.declared.get(folder);
    if (result === undefined) {
      const nearest = this.packageAt(folder);
      const up = nearest === undefined ? undefined : parent(nearest[0]);
      result = new Set([...(nearest?.[1].declared ?? []), ...(up === undefined ? [] : this.declaredAt(up))]);
      this.declared.set(folder, result);
    }
    return result;
  }

  private found(found: Found | undefined): Target | undefined {
    if (found === undefined) {
      return undefined;
    }
    return "file" in found ? { id: found.file } : found;
  }

  /** Step 1: the file a project-relative path names, trying extensions and index files. */
  private path(path: string): Found | undefined {
    const files = this.project;
    if (path !== "" && files.has(path)) {
      return isCode(path) || path.endsWith(".json") ? { file: path } : { asset: extension(path) };
    }
    const dot = path.lastIndexOf(".");
    const written = dot > path.lastIndexOf("/") ? path.slice(dot) : "";
    for (const source of SOURCES[written] ?? []) {
      const candidate = path.slice(0, -written.length) + source;
      if (files.has(candidate)) {
        return { file: candidate };
      }
    }
    for (const candidate of [
      ...EXTENSIONS.map((item) => (path === "" ? undefined : path + item)),
      ...EXTENSIONS.map((item) => (path === "" ? `index${item}` : `${path}/index${item}`)),
    ]) {
      if (candidate !== undefined && files.has(candidate)) {
        return { file: candidate };
      }
    }
    return undefined;
  }
}

/** The folder above a project folder, or undefined above the root. */
function parent(folder: string): string | undefined {
  return folder === "" ? undefined : folderOf(folder);
}

export function isRelative(specifier: string): boolean {
  return specifier === "." || specifier === ".." || specifier.startsWith("./") || specifier.startsWith("../");
}

/** The package a bare specifier names: its first segment, or two for a scoped name. */
export function packageName(specifier: string): string | undefined {
  const parts = specifier.split("/");
  if (specifier.startsWith("@")) {
    return parts.length >= 2 && parts[0]!.length > 1 && parts[1] ? `${parts[0]}/${parts[1]}` : undefined;
  }
  return parts[0] || undefined;
}

/** The DefinitelyTyped package of a package: `@types/node`, `@types/babel__core` for `@babel/core`. */
export function typesPackage(name: string): string | undefined {
  if (name.startsWith("@types/")) {
    return undefined;
  }
  return `@types/${name.startsWith("@") ? name.slice(1).replace("/", "__") : name}`;
}

/** A file's extension for the asset warning: `.css`, or the whole name when it has none. */
function extension(path: string): string {
  const name = path.slice(path.lastIndexOf("/") + 1);
  const dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(dot).toLowerCase() : "(no extension)";
}
