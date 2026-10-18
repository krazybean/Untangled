# js-assets-and-tests

Which files are scanned, from `src/app.tsx`:

- `./app.css`, `./logo.svg` and `./icon.svg?url` exist but are not code: no
  edge (the scan warns with the count per extension).
- `dist/` is build output, and so is `out/`, the `outDir` of `tsconfig.json`:
  neither is scanned. `../dist/legacy.js`, which `src/app.tsx` imports, is an
  `internal` node with no edges of its own.
- `build/generated/` is build output too, but `typescript/sources` adds it back
  with `--source`, so `schema.js` is scanned.
- Tests are not scanned by default: `src/app.test.tsx` and `tests/e2e.spec.ts`
  are not nodes. `src/__mocks__/api.ts` is in a test folder, but real code
  imports it, so it is scanned and its import of `../http` is an edge.
