# psr4-basic

One PSR-4 root. Checks each class-reference kind the scanner records
(`import`, `extends`, `implements`, `new`, `static`, `type`), that `self` and
`static` produce no self-edge, that a builtin class becomes a `builtin:` node,
and that a class under the project's own prefix that no file declares becomes
`unresolved:class:`.
