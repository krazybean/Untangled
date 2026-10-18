# three-cycle

`Cart → Order → Customer → Cart`, plus `Order → Cart` directly, and
`Catalog`, a file with no dependencies, which must still appear as a node.

The Python version has the same shape, with one module per file under
`src/` (an import root), and the same analysis summary.

The TypeScript version (`typescript/`) has the same shape, with `./x.js`
specifiers that name the `.ts` files (the `NodeNext` convention) and one
type-only import.
