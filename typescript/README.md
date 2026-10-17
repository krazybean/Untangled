# Untangled for JavaScript / TypeScript

Planned. The JavaScript/TypeScript library of [Untangled](../README.md), to be
published on npm as `@krazybean/untangled` with the same CLI as the other
languages.

Direction from the project plan: third-party packages become external nodes
and are not followed; relative imports are resolved by trying extensions, then
`index.*`; aliases come from user-declared config, with tsconfig/jsconfig
`paths`/`baseUrl` as a reference; workspace packages are out of scope. Importing
[dependency-cruiser](https://github.com/sverweij/dependency-cruiser) output is
being considered instead of writing a new scanner.

## License

MIT, see [LICENSE](LICENSE).
