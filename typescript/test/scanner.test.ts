// SPDX-License-Identifier: MIT

import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, test } from "vitest";

import { scan, type ScanOptions } from "../src/scanner/scanner.js";
import { ProjectError } from "../src/scanner/project.js";
import { project } from "./helpers.js";

const H = "// SPDX-License-Identifier: MIT\n";

/** The edges of a scan as "from -> to" strings, and its warnings. */
function edges(files: Record<string, string | Uint8Array>, options: ScanOptions = {}): { edges: string[]; warnings: string[] } {
  const result = scan(project(files), options);
  return {
    edges: result.pairs.edges().map((edge) => `${edge.from} -> ${edge.to}`),
    warnings: result.warnings,
  };
}

function nodes(files: Record<string, string>, options: ScanOptions = {}): string[] {
  return scan(project(files), options)
    .pairs.nodes()
    .map((node) => `${node.kind} ${node.id}`);
}

describe("input", () => {
  test("a missing folder is an error", () => {
    expect(() => scan(join(project({}), "nope"))).toThrow(ProjectError);
  });

  test("node_modules, hidden folders and non-code files are not scanned", () => {
    expect(
      nodes({
        "a.ts": H,
        "node_modules/x/index.js": H,
        ".storybook/main.js": H,
        "README.md": "# x",
        "styles.css": "",
      }),
    ).toEqual(["internal a.ts"]);
  });

  test("every code extension is scanned; declaration files only when imported", () => {
    const files = Object.fromEntries(["a.ts", "b.tsx", "c.mts", "d.cts", "e.js", "f.jsx", "g.mjs", "h.cjs", "i.d.ts"].map((name) => [name, H]));
    expect(nodes(files)).toHaveLength(8);
  });

  test("tests are scanned with dev, or when a scanned file imports them", () => {
    const files = {
      "src/a.ts": 'import "./fixtures/data";',
      "src/a.test.ts": H,
      "src/b.spec.js": H,
      "src/__tests__/c.ts": H,
      "test/d.ts": H,
      "tests/e.ts": H,
      "src/fixtures/data.ts": 'import "../../test/helper";',
      "test/helper.ts": H,
      "src/latest.ts": H,
    };
    expect(nodes(files)).toEqual([
      "internal src/a.ts",
      "internal src/fixtures/data.ts",
      "internal src/latest.ts",
      "internal test/helper.ts",
    ]);
    expect(nodes(files, { dev: true })).toHaveLength(9);
  });

  test("build output is skipped with a warning, and --source adds it back", () => {
    const files = {
      "src/a.ts": H,
      "dist/a.js": H,
      "packages/x/build/b.js": H,
      "coverage/lcov.js": H,
      "lib/c.js": H,
      "tsconfig.json": '{ "compilerOptions": { "outDir": "lib" } }',
    };
    const result = edges(files);
    expect(result.warnings).toEqual([
      "skipped 4 files in build output (coverage, dist, lib, and 1 more); add a folder back with --source=<path> if it holds source code",
    ]);
    expect(nodes(files, { sources: ["dist", "lib/c.js"] })).toEqual(["internal dist/a.js", "internal lib/c.js", "internal src/a.ts"]);
  });

  test("--source paths that do not exist or leave the project are warnings", () => {
    expect(edges({ "a.ts": H }, { sources: ["nope", "../x"] }).warnings).toEqual([
      "--source=nope: no such file or folder in the project",
      "--source=../x: outside the project, ignored",
    ]);
  });

  test("Windows-1252 file contents and names", () => {
    const root = project({ "a.ts": Buffer.from('// caf\xe9\nimport "./caf\xe9";', "latin1") });
    writeFileSync(Buffer.from(join(root, "caf\xe9.ts"), "latin1"), H);
    expect(scan(root).pairs.edges()).toEqual([{ from: "a.ts", to: "café.ts", kinds: ["import"], count: 1 }]);
  });
});

describe("relative imports", () => {
  test("extension order, NodeNext names and index files", () => {
    expect(
      edges({
        "a.ts": 'import "./b"; import "./c.js"; import "./d"; import "./e.mjs"; import "./f.cjs"; import "./g.jsx";',
        "b.ts": H,
        "b.js": H,
        "c.tsx": H,
        "d/index.js": H,
        "e.d.mts": H,
        "f.cts": H,
        "g.tsx": H,
      }).edges,
    ).toEqual(["a.ts -> b.ts", "a.ts -> c.tsx", "a.ts -> d/index.js", "a.ts -> e.d.mts", "a.ts -> f.cts", "a.ts -> g.tsx"]);
  });

  test("a .js file that exists wins over the .ts source", () => {
    expect(edges({ "a.ts": 'import "./b.js";', "b.js": H, "b.ts": H }).edges).toEqual(["a.ts -> b.js"]);
  });

  test("JSON is an internal node that is not scanned", () => {
    expect(nodes({ "a.ts": 'import "./data.json"; import "./config";', "data.json": "{}", "config.json": "{}" })).toEqual([
      "internal a.ts",
      "internal config.json",
      "internal data.json",
    ]);
  });

  test("non-code files give no edge and one warning", () => {
    const result = edges({ "a.ts": 'import "./a.css"; import "./b.css"; import x from "./x.svg?raw"; import "./LICENSE";', "a.css": "", "b.css": "", "x.svg": "", LICENSE: "" });
    expect(result.edges).toEqual([]);
    expect(result.warnings).toEqual(["4 imports of non-code files gave no edge (.css 2, (no extension) 1, .svg 1)"]);
  });

  test("missing files are unresolved by project path, or as written outside the project", () => {
    expect(nodes({ "src/a.ts": 'import "./x"; import "../src/x"; import "../../y"; import "/z";' })).toEqual([
      "internal src/a.ts",
      "unresolved unresolved:module:../../y",
      "unresolved unresolved:module:/z",
      "unresolved unresolved:module:src/x",
    ]);
  });

  test("the project folder and its index file, from below", () => {
    expect(edges({ "index.js": H, "lib/a.js": 'require("../"); require("..");' }).edges).toEqual(["lib/a.js -> index.js"]);
  });

  test("a file in a hidden folder is scanned when a scanned file imports it", () => {
    expect(
      edges({ "a.ts": 'import "./.config/rules";', ".config/rules/index.ts": 'import "./b";', ".config/rules/b.ts": H, ".config/c.ts": H }).edges,
    ).toEqual([".config/rules/index.ts -> .config/rules/b.ts", "a.ts -> .config/rules/index.ts"]);
  });

  test("build output imported by source is a node that is not scanned", () => {
    expect(edges({ "src/a.ts": 'import "../dist/b.js";', "dist/b.js": 'import "./c.js";', "dist/c.js": H }).edges).toEqual([
      "src/a.ts -> dist/b.js",
    ]);
  });

  test("dynamic references with non-literal arguments", () => {
    expect(nodes({ "a.js": "require(x); import(`./p/${y}`);" })).toEqual([
      "internal a.js",
      "unresolved unresolved:dynamic:`./p/${y}`",
      "unresolved unresolved:dynamic:x",
    ]);
  });
});

describe("packages and builtins", () => {
  const manifest = JSON.stringify({ dependencies: { react: "1", "@s/ui": "1", events: "1" }, devDependencies: { vitest: "1" } });

  test("declared, installed, builtin and unresolved", () => {
    expect(
      nodes({
        "package.json": manifest,
        "node_modules/lodash/package.json": "{}",
        "node_modules/@t/x/package.json": "{}",
        "a.ts":
          'import "react/jsx-runtime"; import "@s/ui/b"; import "vitest"; import "lodash/fp"; import "@t/x"; import "events";' +
          ' import "node:fs/promises"; import "path"; import "left-pad"; import "@";',
      }),
    ).toEqual([
      "internal a.ts",
      "builtin builtin:fs",
      "builtin builtin:path",
      "external npm:@s/ui",
      "external npm:@t/x",
      "external npm:events",
      "external npm:lodash",
      "external npm:react",
      "external npm:vitest",
      "unresolved unresolved:module:@",
      "unresolved unresolved:module:left-pad",
    ]);
  });

  test("without node_modules, unresolved bare specifiers are a warning", () => {
    expect(edges({ "a.ts": 'import "x/y"; import "@a/b/c"; import "react";', "package.json": '{ "dependencies": { "react": "1" } }' }).warnings).toEqual([
      "no node_modules folder, so imports of @a/b, x could only be matched against declared dependencies by name, and show as unresolved; install the project's dependencies first for a complete picture",
    ]);
    expect(edges({ "a.ts": 'import "x";', "node_modules/.bin/x": "" }).warnings).toEqual([]);
  });

  test("a package with types only is the package", () => {
    const files = {
      "package.json": '{ "devDependencies": { "@types/vscode": "1", "@types/babel__core": "1" } }',
      "node_modules/@types/mdast/package.json": "{}",
      "a.ts": 'import "vscode"; import "@babel/core"; import "mdast"; import "electron";',
    };
    expect(edges(files).edges).toEqual(["a.ts -> npm:@babel/core", "a.ts -> npm:mdast", "a.ts -> npm:vscode", "a.ts -> unresolved:module:electron"]);
  });

  test("a package.json in a subfolder adds to the ones above it", () => {
    const files = {
      "package.json": '{ "dependencies": { "react": "1" } }',
      "app/package.json": '{ "dependencies": { "vue": "1", "events": "1" } }',
      "app/node_modules/pinia/package.json": "{}",
      "broken/package.json": "{",
      "app/src/a.ts": 'import "react"; import "vue"; import "pinia"; import "events";',
      "b.ts": 'import "vue"; import "pinia"; import "events";',
      "broken/c.ts": 'import "react";',
    };
    const result = edges(files);
    expect(result.edges).toEqual([
      "app/src/a.ts -> npm:events",
      "app/src/a.ts -> npm:pinia",
      "app/src/a.ts -> npm:react",
      "app/src/a.ts -> npm:vue",
      "b.ts -> builtin:events",
      "b.ts -> unresolved:module:pinia",
      "b.ts -> unresolved:module:vue",
      "broken/c.ts -> npm:react",
    ]);
    expect(result.warnings).toEqual([expect.stringMatching(/^broken\/package\.json: cannot read it/)]);
  });

  test("package.json imports", () => {
    const files = {
      "package.json": JSON.stringify({
        dependencies: { lodash: "1" },
        imports: {
          "#a/*": "./src/a/*.js",
          "#a/special": "./src/special.ts",
          "#b": { types: { import: "./src/b.d.ts" }, default: "./src/b.js" },
          "#c": ["lodash/fp"],
          "#d": "./missing.js",
        },
      }),
      "src/a/x.ts": H,
      "src/special.ts": H,
      "src/b.d.ts": H,
      "main.ts": 'import "#a/x"; import "#a/special"; import "#b"; import "#c"; import "#d"; import "#e";',
    };
    expect(edges(files).edges).toEqual([
      "main.ts -> npm:lodash",
      "main.ts -> src/a/x.ts",
      "main.ts -> src/b.d.ts",
      "main.ts -> src/special.ts",
      "main.ts -> unresolved:module:#e",
      "main.ts -> unresolved:module:missing.js",
    ]);
  });
});

describe("aliases", () => {
  test("tsconfig paths relative to baseUrl, then baseUrl itself", () => {
    const files = {
      "tsconfig.json": '{ "compilerOptions": { "baseUrl": "./src", "paths": { "@/*": ["*"], "#lib": ["lib/index.ts"] } } }',
      "src/a.ts": 'import "@/b"; import "#lib"; import "utils/c"; import "react";',
      "src/b.ts": H,
      "src/lib/index.ts": H,
      "src/utils/c.ts": H,
      "package.json": '{ "dependencies": { "react": "1" } }',
    };
    expect(edges(files).edges).toEqual(["src/a.ts -> npm:react", "src/a.ts -> src/b.ts", "src/a.ts -> src/lib/index.ts", "src/a.ts -> src/utils/c.ts"]);
  });

  test("a # name that package.json imports does not map can be a tsconfig path", () => {
    const files = {
      "package.json": '{ "imports": { "#a": "./a.ts" } }',
      "tsconfig.json": '{ "compilerOptions": { "paths": { "#/*": ["./src/*"] } } }',
      "main.ts": 'import "#a"; import "#/b"; import "#c";',
      "a.ts": H,
      "src/b.ts": H,
    };
    expect(edges(files).edges).toEqual(["main.ts -> a.ts", "main.ts -> src/b.ts", "main.ts -> unresolved:module:#c"]);
  });

  test("jsconfig.json when there is no tsconfig.json", () => {
    expect(edges({ "jsconfig.json": '{ "compilerOptions": { "paths": { "@/*": ["./src/*"] } } }', "a.js": 'import "@/b";', "src/b.js": H }).edges).toEqual([
      "a.js -> src/b.js",
    ]);
  });

  test("an alias that finds no file falls through to packages", () => {
    const files = {
      "tsconfig.json": '{ "compilerOptions": { "paths": { "*": ["./types/*"] } } }',
      "package.json": '{ "dependencies": { "react": "1" } }',
      "a.ts": 'import "react"; import "local";',
      "types/local.d.ts": H,
    };
    expect(edges(files).edges).toEqual(["a.ts -> npm:react", "a.ts -> types/local.d.ts"]);
  });

  test("extends: the extending file wins, and cycles end", () => {
    const files = {
      "tsconfig.json": '{ "extends": "./base.json", "compilerOptions": { "paths": { "@/*": ["./app/*"] } } }',
      "base.json": '{ "extends": "./tsconfig.json", "compilerOptions": { "paths": { "@/*": ["./lib/*"] }, "outDir": "out" } }',
      "a.ts": 'import "@/b";',
      "app/b.ts": H,
      "lib/b.ts": H,
      "out/x.js": H,
    };
    const result = edges(files);
    expect(result.edges).toEqual(["a.ts -> app/b.ts"]);
    expect(result.warnings[0]).toMatch(/^skipped 1 file in build output \(out\)/);
  });

  test("--aliases files come first; bad ones are warnings", () => {
    const root = project({
      "tsconfig.json": '{ "compilerOptions": { "paths": { "@/*": ["./b/*"] } } }',
      "aliases.json": '{ "@/*": ["a/*"], "cfg": "a/config.ts" }',
      "list.json": "[1]",
      "bad.json": "{",
      "a.ts": 'import "@/x"; import "cfg";',
      "a/x.ts": H,
      "a/config.ts": H,
      "b/x.ts": H,
    });
    const result = scan(root, { aliases: [join(root, "aliases.json"), join(root, "list.json"), join(root, "bad.json"), "nope.json"] });
    expect(result.pairs.edges().map((edge) => edge.to)).toEqual(["a/config.ts", "a/x.ts"]);
    expect(result.warnings).toEqual([
      `--aliases=${join(root, "list.json")}: not a JSON object of aliases; ignored`,
      expect.stringMatching(/bad\.json: cannot read it \(.*\); ignoring it$/),
      "--aliases=nope.json: no such file",
    ]);
  });

  test("an invalid tsconfig.json is a warning", () => {
    expect(edges({ "tsconfig.json": "{ nope", "a.ts": H }).warnings).toEqual([expect.stringMatching(/^tsconfig.json: cannot read it/)]);
  });
});

describe("warnings", () => {
  test("files that do not parse, and recovered errors in one warning", () => {
    const result = edges({ "a.ts": "const = {{;", "b.ts": 'import "./c"; let x; let x;', "c.ts": H });
    expect(result.edges).toEqual(["b.ts -> c.ts"]);
    expect(result.warnings).toEqual([
      expect.stringMatching(/^a\.ts: cannot parse: /),
      expect.stringMatching(/^1 file has syntax errors; the imports the parser could still read are kept: b\.ts: /),
    ]);
  });
});

test("scans are deterministic and kinds carry type", () => {
  const files = { "a.ts": 'import type { B } from "./b"; import { c } from "./b"; export * from "./b";', "b.ts": H };
  expect(scan(project(files)).pairs.edges()).toEqual([{ from: "a.ts", to: "b.ts", kinds: ["export", "import", "type"], count: 3 }]);
});
