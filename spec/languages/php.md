# PHP profile

How the PHP library turns a project into a [pairs document](../pairs-format.md).

## Input

- The project root MUST contain `composer.json`. Projects without Composer are
  not supported; the scanner exits with an error saying so.
- **Scanned files** are the files covered by the root package's `autoload`
  section: every `.php` file under `psr-4` and `psr-0` directories, every
  `classmap` entry (files, or `.php` files under directories), and every
  `files` entry. `exclude-from-classmap` is honored.
- `autoload-dev` is scanned only with `--dev` (tests usually depend on
  everything, which hides the real structure).
- Files reached through a followed `include` / `require` (see below) are
  scanned too, even when no autoload rule covers them.
- `vendor/` (or `config.vendor-dir`) and hidden directories are never scanned.
- `module` of a file is the namespace it declares (the first one, if several).

## Resolving a class-like name

For each referenced class, interface, trait or enum name (fully qualified after
applying `namespace` and `use` rules):

1. **Project symbol.** If a scanned file declares it, the target is that file.
   Names compare case-insensitively, as in PHP. If two files declare the same
   class, the first in path order wins and the scanner warns.
   (The scanner builds the symbol table from the scanned files themselves, which
   is what Composer's optimized classmap would contain.)
2. **Vendor package.** If it matches a `psr-4` / `psr-0` prefix (the longest
   matching prefix wins; empty catch-all prefixes are ignored) or a class
   declared in a `classmap` entry of an installed package, the target is
   `composer:<package-name>`. Installed packages are read from
   `vendor/composer/installed.json`, or from `composer.lock` when `vendor/` is
   absent. Classmap packages can only be resolved when `vendor/` is installed,
   since their classes are read from the package's files.
3. **Builtin.** If it is a class known to the PHP runtime running the scanner
   (core and loaded extensions), the target is `builtin:<Name>`.
4. Otherwise the target is `unresolved:class:<FQCN>`.

`self` and `static` point at the current class, so they become self-edges and
are dropped. `parent` is replaced by the parent class's name and resolved as
above.

## Functions and constants

Calls to functions and uses of constants are resolved only when they match a
function or constant declared in a scanned file (for example a helper loaded via
`files` autoload). Constants count as declared through `const` and through
`define()` with a string literal name. An unqualified name inside a namespace
is tried as the namespaced name first, then as the global one. Anything else is
assumed to be builtin and is not recorded, because PHP's global fallback makes
"unresolved function" too noisy to be useful.

## Imports

An `import` (`use` statement) is recorded only when it resolves. One that does
not is dropped rather than made unresolved, because it may name a namespace
(`use App\Models;` followed by `Models\User`); the names the code then uses
are resolved, and reported, on their own.

## include / require

`include`, `include_once`, `require` and `require_once` are followed only when
the path is a **constant expression** built from string literals, `__DIR__`,
`dirname(__FILE__)`, `dirname(..., levels)` and the `.` operator. `__DIR__`
forms evaluate to an absolute path. A relative result is tried against the
project root (PHP's working directory when run from there), then against the
including file's directory. The first candidate that exists wins.

- An existing file inside the project → that file, which is then scanned too.
- An existing file inside `vendor/<vendor>/<package>/` → `composer:<vendor>/<package>`.
- Missing, or outside the project → `unresolved:include:<path>`, with the
  project-relative path when it is inside the project, else the source text.
- Any other expression (variables, function calls, constants) →
  `unresolved:include:<source text>`, the expression as written with runs of
  whitespace collapsed to one space.

## Edge kinds

| kind | source construct |
| --- | --- |
| `import` | `use Foo\Bar;` (including grouped and function/const imports) |
| `extends` | `class A extends B`, `interface A extends B` |
| `implements` | `class A implements B` |
| `trait` | `use SomeTrait;` inside a class |
| `new` | `new Foo()` |
| `static` | `Foo::method()`, `Foo::CONST`, `Foo::$prop`, `Foo::class` |
| `type` | parameter, return and property types, including union/intersection/nullable |
| `instanceof` | `$x instanceof Foo` |
| `catch` | `catch (Foo $e)` |
| `attribute` | `#[Foo]` |
| `call` | call to a project-declared function |
| `const` | use of a project-declared constant |
| `include` | `include` / `require` family |

Not in v0.1: docblock types (`@param Foo`), string class names
(`'App\Foo'`), and `new $var` / `$var::method()` (no name to resolve; skipped,
not unresolved).

## Parser

The reference implementation uses
[nikic/PHP-Parser](https://github.com/nikic/PHP-Parser) and its `NameResolver`.
A file that fails to parse is still a node; the scanner reports the error and
records no edges for it.
