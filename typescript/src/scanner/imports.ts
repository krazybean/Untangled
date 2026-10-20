// SPDX-License-Identifier: MIT
// Reads one file's imports with @babel/parser (spec/languages/typescript.md, "Edge kinds"
// and "Parsing").

import { parse, type ParserOptions, type ParserPlugin } from "@babel/parser";

import { collapse } from "../text.js";

export const IMPORT = "import";
export const EXPORT = "export";
export const REQUIRE = "require";
export const DYNAMIC = "dynamic";
export const TYPE = "type";

/**
 * One import, export from, require or import() call. `specifier` is the string it names;
 * a dynamic one whose argument is not a string literal has none and keeps its source text.
 */
export interface Reference {
  kind: string;
  type: boolean;
  specifier?: string;
  text?: string;
}

export interface FileImports {
  references: Reference[];
  /** Why the file has no references: it could not be parsed at all. */
  error?: string;
  /** With `error`, the pairs document's `error` for the file. */
  unread?: "parse" | "read";
  /** The first syntax error the parser recovered from, if any. */
  recovered?: string;
}

interface AstNode {
  type: string;
  start?: number | null;
  end?: number | null;
  [key: string]: unknown;
}

const SKIPPED_KEYS = new Set([
  "loc", "start", "end", "range", "extra", "comments", "leadingComments", "trailingComments", "innerComments", "errors",
  "tokens",
]);

export function collect(source: string, id: string): FileImports {
  // The parse with the fewest recovered errors wins; one with none ends the search.
  let parsed: { program: unknown; errors: Error[] } | undefined;
  let lastError: unknown;
  for (const options of parserOptions(id)) {
    let attempt;
    try {
      attempt = parse(source, options) as unknown as { program: unknown; errors?: Error[] };
    } catch (error) {
      lastError = error;
      continue;
    }
    const errors = attempt.errors ?? [];
    if (parsed === undefined || errors.length < parsed.errors.length) {
      parsed = { program: attempt.program, errors };
    }
    if (!errors.length) {
      break;
    }
  }
  if (parsed === undefined) {
    return { references: [], error: `cannot parse: ${(lastError as Error).message}`, unread: "parse" };
  }
  const result: FileImports = { references: new Collector(source).run(parsed.program as AstNode) };
  if (parsed.errors.length) {
    result.recovered = parsed.errors[0]!.message;
  }
  return result;
}

function parserOptions(id: string): ParserOptions[] {
  const base: ParserOptions = {
    sourceType: /\.m[jt]s$/.test(id) ? "module" : "unambiguous",
    errorRecovery: true,
    allowReturnOutsideFunction: true,
    allowAwaitOutsideFunction: true,
    allowImportExportEverywhere: true,
    allowNewTargetOutsideFunction: true,
    allowSuperOutsideMethod: true,
    allowUndeclaredExports: true,
  };
  const withPlugins = (plugins: ParserPlugin[], decorators: ParserPlugin = "decorators"): ParserOptions => ({
    ...base,
    plugins: [...plugins, decorators],
  });
  // TypeScript code often uses parameter decorators (`constructor(@inject(x) y)`), which only
  // the legacy proposal allows; `export @dec class` needs the current one.
  const typescript = (plugins: ParserPlugin[]): ParserOptions[] => [
    withPlugins(plugins, "decorators-legacy"),
    withPlugins(plugins),
  ];
  if (/\.d\.[mc]?ts$/.test(id)) {
    return [withPlugins([["typescript", { dts: true }]])];
  }
  if (/\.[mc]?ts$/.test(id)) {
    return typescript(["typescript"]);
  }
  if (id.endsWith(".tsx")) {
    return typescript(["typescript", "jsx"]);
  }
  return [withPlugins(["jsx"]), withPlugins(["jsx", "flow"])];
}

class Collector {
  private readonly references: Reference[] = [];

  constructor(private readonly source: string) {}

  run(program: AstNode): Reference[] {
    // An explicit stack instead of recursion: generated code can nest very deep.
    const stack: AstNode[] = [program];
    while (stack.length) {
      const node = stack.pop()!;
      this.visit(node);
      const children: AstNode[] = [];
      for (const key of Object.keys(node)) {
        if (SKIPPED_KEYS.has(key)) {
          continue;
        }
        const value = node[key];
        if (Array.isArray(value)) {
          for (const item of value) {
            if (isNode(item)) {
              children.push(item);
            }
          }
        } else if (isNode(value)) {
          children.push(value);
        }
      }
      for (let index = children.length - 1; index >= 0; index--) {
        stack.push(children[index]!);
      }
    }
    return this.references;
  }

  private visit(node: AstNode): void {
    switch (node.type) {
      case "ImportDeclaration": {
        const specifiers = (node.specifiers as AstNode[] | undefined) ?? [];
        const typeOnly =
          isTypeKind(node.importKind) || (specifiers.length > 0 && specifiers.every((item) => isTypeKind(item.importKind)));
        this.add(IMPORT, typeOnly, node.source);
        break;
      }
      case "ExportNamedDeclaration":
      case "ExportAllDeclaration": {
        if (!node.source) {
          break;
        }
        const specifiers = (node.specifiers as AstNode[] | undefined) ?? [];
        const typeOnly =
          isTypeKind(node.exportKind) || (specifiers.length > 0 && specifiers.every((item) => isTypeKind(item.exportKind)));
        this.add(EXPORT, typeOnly, node.source);
        break;
      }
      case "TSImportEqualsDeclaration": {
        const reference = node.moduleReference as AstNode | undefined;
        if (reference?.type === "TSExternalModuleReference") {
          this.add(REQUIRE, isTypeKind(node.importKind), reference.expression);
        }
        break;
      }
      case "ImportExpression":
        this.add(DYNAMIC, false, node.source);
        break;
      case "CallExpression": {
        const callee = node.callee as AstNode;
        const args = node.arguments as AstNode[];
        if (callee.type === "Import" && args.length) {
          this.add(DYNAMIC, false, args[0]);
        } else if (callee.type === "Identifier" && callee.name === "require" && args.length) {
          this.add(REQUIRE, false, args[0]);
        }
        break;
      }
      case "TSImportType": {
        // Babel 8 names it source; older versions wrapped it in a TSLiteralType argument.
        const argument = (node.source ?? node.argument) as AstNode | undefined;
        this.add(IMPORT, true, argument?.type === "TSLiteralType" ? argument.literal : argument);
        break;
      }
    }
  }

  private add(kind: string, type: boolean, argument: unknown): void {
    if (!isNode(argument) || argument.type === "SpreadElement") {
      return;
    }
    const specifier = literal(argument);
    if (specifier !== undefined) {
      this.references.push({ kind, type, specifier });
    } else if (kind === DYNAMIC || kind === REQUIRE) {
      const text = this.source.slice(argument.start ?? 0, argument.end ?? 0);
      this.references.push({ kind, type, text: collapse(text) });
    }
  }
}

function literal(node: AstNode): string | undefined {
  if (node.type === "StringLiteral" && typeof node.value === "string") {
    return node.value;
  }
  if (node.type === "TemplateLiteral" && (node.expressions as unknown[]).length === 0) {
    const quasi = (node.quasis as AstNode[])[0];
    const cooked = (quasi?.value as { cooked?: string } | undefined)?.cooked;
    return typeof cooked === "string" ? cooked : undefined;
  }
  return undefined;
}

function isTypeKind(kind: unknown): boolean {
  return kind === "type" || kind === "typeof";
}

function isNode(value: unknown): value is AstNode {
  return typeof value === "object" && value !== null && typeof (value as AstNode).type === "string";
}
