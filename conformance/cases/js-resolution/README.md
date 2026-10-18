# js-resolution

How a relative specifier finds its file, from `src/main.ts`:

- `./util/format.js` names `src/util/format.ts` (the `NodeNext` convention), as
  does `./util/format.js?raw` once the query is dropped: one edge, count 2.
  `./components/button.jsx` names the `.tsx` file, `./legacy/esm.mjs` the
  `.mts` and `./legacy/common.cjs` the `.cts`.
- `./both`: `both.ts` and `both.js` exist, and `.ts` is tried first.
- `./util` is a folder, so its `index.ts`. In there, `"."` is the file itself
  (a self-edge, dropped) and `".."` is `src/index.js`.
- `./legacy/old.js` exists as written; it `require`s `../util/format` with no
  extension.
- `../settings.json` is an `internal` node that is not scanned.
- `./types/shapes` is a declaration file, scanned because it is imported, so
  its own import of `./colors` (another `.d.ts`) is an edge too.
  `types/unused.d.ts` is imported by nothing and is not a node.
- `./missing.js` and `../src/missing.js` name the same missing file, so they
  share one node, `unresolved:module:src/missing.js` (count 2).
- `../../outside.js` leaves the project and `/abs/path.js` is absolute: both
  are unresolved as written.
