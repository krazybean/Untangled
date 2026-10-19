// SPDX-License-Identifier: MIT

import { describe, expect, test } from "vitest";

import { collect, type Reference } from "../src/scanner/imports.js";

function refs(source: string, id = "a.ts"): Reference[] {
  const result = collect(source, id);
  expect(result.error).toBeUndefined();
  return result.references;
}

describe("kinds", () => {
  test("import, export and side effects", () => {
    expect(
      refs('import a from "a"; import "b"; import * as c from "c"; export { d } from "d"; export * from "e"; export * as f from "f";'),
    ).toEqual([
      { kind: "import", type: false, specifier: "a" },
      { kind: "import", type: false, specifier: "b" },
      { kind: "import", type: false, specifier: "c" },
      { kind: "export", type: false, specifier: "d" },
      { kind: "export", type: false, specifier: "e" },
      { kind: "export", type: false, specifier: "f" },
    ]);
  });

  test("type-only imports and exports", () => {
    expect(
      refs(
        'import type A from "a"; import { type B, type C } from "b"; import { type D, e } from "c";' +
          ' export type { F } from "d"; export { type G } from "e"; import type * as H from "f";',
      ).map((item) => [item.specifier, item.type]),
    ).toEqual([
      ["a", true],
      ["b", true],
      ["c", false],
      ["d", true],
      ["e", true],
      ["f", true],
    ]);
  });

  test("an export without a source is not a reference", () => {
    expect(refs("const a = 1; export { a }; export default a;")).toEqual([]);
  });

  test("require, import = require, and import()", () => {
    expect(refs('const a = require("a"); import b = require("b"); import type c = require("c"); import("d");')).toEqual([
      { kind: "require", type: false, specifier: "a" },
      { kind: "require", type: false, specifier: "b" },
      { kind: "require", type: true, specifier: "c" },
      { kind: "dynamic", type: false, specifier: "d" },
    ]);
  });

  test("type-level imports", () => {
    expect(refs('type A = typeof import("a"); let b: import("b").B;')).toEqual([
      { kind: "import", type: true, specifier: "a" },
      { kind: "import", type: true, specifier: "b" },
    ]);
  });

  test("require needs an argument, and the name require", () => {
    expect(refs('require(); req("a"); obj.require("b"); require.resolve("c");')).toEqual([]);
  });

  test("template literals: resolvable without expressions, dynamic text with them", () => {
    expect(refs("import(`./a`); import(`./p/${name}`); require(base +\n   '/x');")).toEqual([
      { kind: "dynamic", type: false, specifier: "./a" },
      { kind: "dynamic", type: false, text: "`./p/${name}`" },
      { kind: "require", type: false, text: "base + '/x'" },
    ]);
  });

  test("references nested anywhere are found, in source order", () => {
    expect(
      refs('function f() { if (x) { return import("a"); } } class C { m() { require("b"); } }').map((item) => item.specifier),
    ).toEqual(["a", "b"]);
  });

  test("decorators", () => {
    expect(refs('import { dec } from "a";\n@dec class A {}\nexport @dec class B {}')).toHaveLength(1);
  });

  test("parameter decorators in TypeScript", () => {
    const source = 'import { inject } from "a";\nclass A { constructor(@inject("x") private x: X) {} }';
    for (const id of ["a.ts", "a.tsx"]) {
      expect(collect(source, id)).toEqual({ references: [{ kind: "import", type: false, specifier: "a" }] });
    }
  });
});

describe("parsing", () => {
  test("JSX in .js and .tsx files", () => {
    expect(refs('import a from "a"; export const x = <div>{a}</div>;', "a.js")).toHaveLength(1);
    expect(refs('import a from "a"; export const x = <div>{a as number}</div>;', "a.tsx")).toHaveLength(1);
  });

  test("TypeScript generics with arrow functions in .ts files", () => {
    expect(refs('import a from "a"; const f = <T,>(x: T): T => x; const y = <number>a;', "a.ts")).toHaveLength(1);
  });

  test("Flow types in .js files", () => {
    expect(refs('// @flow\nimport type { A } from "a";\nfunction f(x: ?A): A { return x; }', "a.js")).toEqual([
      { kind: "import", type: true, specifier: "a" },
    ]);
  });

  test("CommonJS scripts and modules", () => {
    expect(refs('return require("a");', "a.cjs")).toHaveLength(1);
    expect(refs('await import("a");', "a.mjs")).toHaveLength(1);
    expect(refs('with (x) { require("a"); }', "a.js")).toHaveLength(1);
  });

  test("declaration files", () => {
    expect(refs('import { A } from "a"; export declare function f(): A;', "a.d.ts")).toHaveLength(1);
  });

  test("a recovered syntax error keeps the imports", () => {
    const result = collect('import a from "a"; let x = 1; let x = 2;', "a.ts");
    expect(result.references).toHaveLength(1);
    expect(result.recovered).toContain("already been declared");
  });

  test("a file that does not parse has an error and no references", () => {
    const result = collect('import a from "a"; const = {{;', "a.ts");
    expect(result.references).toEqual([]);
    expect(result.error).toMatch(/^cannot parse: /);
  });
});
