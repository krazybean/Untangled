# dynamic-classes

PHP: a class named by an expression (`new $class()`, `new ($factory())(1)`,
`$class::boot()`, `$class::VERSION`, `$x instanceof $class`) becomes an
`unresolved:dynamic:<source text>` node, with the edge kind of the construct
(`new`, `static`, `instanceof`). `$subject::class` loads nothing and adds no
edge; `Plugin::class` is an ordinary `static` reference.
