# includes

`classmap` and `files` autoloading, and the include rules: a `__DIR__` path
and a `dirname(__DIR__)` path are followed into files outside the autoload
rules (which are then scanned too), a path built from a variable becomes
`unresolved:include:` with its source text, and a literal path to a missing
file becomes `unresolved:include:` with its project-relative path. Calls to a
project function and uses of project constants (`const` and `define()`) are
edges; calls to builtin functions (`strlen`, `number_format`) are not.
