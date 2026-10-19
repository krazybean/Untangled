# js-import-kinds

Every kind of reference a JavaScript or TypeScript file can make:

- `src/kinds.ts`: default, side-effect and namespace imports are `import`;
  `import type` and an import whose every name is `type` add `type`; an import
  with one value name does not. `export … from` is `export` (plus `type` for
  `export type`), `import j = require()` is `require`, and `typeof import()`
  is `import` plus `type`.
- `import("./a")` is `dynamic`, so `src/a.ts` gets `dynamic` and `import`
  (count 2). A template literal without expressions resolves; one with an
  expression, and `require(name)`, are `unresolved:dynamic:<source text>`.
  Text in a string that looks like `require()` is not a reference.
- `src/view.jsx` uses JSX, `src/flow.js` Flow types (its `import type` adds
  `type`), and `src/script.cjs` is a CommonJS script whose `require("fs")` is
  a builtin.
- `src/recovered.ts` has a syntax error the parser recovers from, so its import
  is kept (with a warning). `src/broken.ts` does not parse: a node with no
  edges (and a warning).
