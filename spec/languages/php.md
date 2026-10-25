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
- `--source=<path>` (repeatable) adds code that `composer.json` does not
  autoload, as legacy applications load it with their own autoloader or
  `include_path`: the path is relative to the project root and is read like a
  `classmap` entry (a file, or the `.php` and `.inc` files under a folder).
  A path that does not exist is a warning.
- `--aliases=<preset|file>` (repeatable) declares global class aliases that
  a framework registers at runtime; see [Class aliases](#class-aliases).
- `vendor/` (or `config.vendor-dir`) and hidden directories are never scanned.
- `module` of a file is the namespace it declares (the first one, if several).
- The scanner warns, without failing, when the result is likely incomplete:
  - when no `vendor/composer/installed.json` or `composer.lock` exists but
    `composer.json` requires packages, since their classes will be unresolved;
  - when `.php` files under the root are not scanned: not covered by any
    `autoload` or `autoload-dev` rule, a `--source` path, or a followed
    include, and not matched by `exclude-from-classmap` (`vendor/`,
    `node_modules/` and hidden directories are not counted, nor are files git
    ignores, such as compiled views; a tracked file counts even when a
    `.gitignore` pattern matches it, and a project that is not a git
    repository, or a machine without git, has nothing left out). The warning gives
    the count and, for the top-level folders holding the most of them, the
    deepest folder each one's files share (`database/migrations/`, `lang/`),
    so the user can decide what to pass to `--source`.

## Resolving a class-like name

For each referenced class, interface, trait or enum name (fully qualified after
applying `namespace` and `use` rules):

1. **Project symbol.** If a scanned file declares it, the target is that file.
   Names compare case-insensitively, as in PHP. If two files declare the same
   class, the first in path order wins and the scanner warns.
   (The scanner builds the symbol table from the scanned files themselves, which
   is what Composer's optimized classmap would contain.)
2. **Builtin.** If it is a class known to the PHP runtime running the scanner
   (core and loaded extensions), the target is `builtin:<Name>`. Builtins come
   before packages because polyfill packages (`symfony/polyfill-php80` and
   the like) declare classes such as `Stringable` that newer PHP versions
   build in; on a PHP that lacks the class, the polyfill's package is the
   target.
3. **Vendor package.** If it matches a `psr-4` / `psr-0` prefix (the longest
   matching prefix wins; empty catch-all prefixes are ignored) or a class
   declared in a `classmap` entry of an installed package, the target is
   `composer:<package-name>`. Installed packages are read from
   `vendor/composer/installed.json`, or from `composer.lock` when `vendor/` is
   absent. Classmap packages can only be resolved when `vendor/` is installed,
   since their classes are read from the package's files.
4. **Composer runtime.** `Composer\Autoload\ClassLoader` and
   `Composer\InstalledVersions`, which Composer writes into `vendor/composer/`
   itself, are `composer:composer-runtime-api` (the package name Composer
   gives that API).
5. **Declared alias.** If the name is a [class alias](#class-aliases) the
   user declared, the class it aliases is resolved with steps 1 to 4 (aliases
   are not followed further), and the result is the target. When that class
   does not resolve either, the target is `unresolved:class:<aliased class>`.
6. Otherwise the target is `unresolved:class:<FQCN>`.

`self` and `static` point at the current class, so they become self-edges and
are dropped. `parent` is replaced by the parent class's name and resolved as
above.

### Class aliases

Some frameworks register short global names at runtime with `class_alias()`
or an alias autoloader: Laravel's `\DB` is `Illuminate\Support\Facades\DB`.
No file declares those names, so the scanner cannot find them by itself, and
it does not read framework configuration to look for them. Instead the user
declares them with `--aliases=<preset|file>` (repeatable):

- A **file** is JSON: `{"aliases": {"DB": "Illuminate\\Support\\Facades\\DB"}}`,
  alias name to class name, both fully qualified (a leading `\` is allowed).
  Alias names compare case-insensitively, as class names do in PHP. An
  optional `"package-extra": "<key>.<key>"` names where installed packages
  declare more aliases inside their `extra` section, read from
  `vendor/composer/installed.json` (or `composer.lock`).
- A **preset** is such a file shipped with the library, chosen by name.
  `laravel` holds Laravel's default aliases
  (`Illuminate\Support\Facades\Facade::defaultAliases()`, which also covers
  Lumen's `withFacades()`), and reads the aliases packages declare under
  `extra.laravel.aliases` (`Livewire`, `Socialite`). Aliases an application
  adds in its own `config/app.php` go in a file.

When several declare the same alias, the later `--aliases` wins, and any
`--aliases` entry wins over one a package declares. A name nobody declares
stays unresolved. An alias whose name a project file, builtin or package
already provides is not used, since that class is what PHP loads.

Presets exist only where a framework relies on global aliases and its list is
short and stable. Symfony, CakePHP, CodeIgniter 4, Yii, Drupal and Magento
use namespaced classes or real global classes (`Yii`, `Drupal`, `Mage`)
instead. PrestaShop's `Product` / `ProductCore` overrides and the Laminas
`Zend\` bridge rename classes by rule rather than by a list, so they have no
preset.

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
including file's directory, then against each `--source` folder in the order
given (legacy applications put their source folders on `include_path`). The
first candidate that exists wins.

- An existing file inside the project → that file, which is then scanned too.
- An existing file inside `vendor/<vendor>/<package>/` → `composer:<vendor>/<package>`.
- Composer's own autoloader (`vendor/autoload.php`, or a file in
  `vendor/composer/`) → not recorded. It only loads the packages, which the
  class references already point at.
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
| `new` | `new Foo()`, `new $class()` |
| `static` | `Foo::method()`, `Foo::CONST`, `Foo::$prop`, `Foo::class`, `$class::method()` |
| `type` | parameter, return and property types, including union/intersection/nullable |
| `instanceof` | `$x instanceof Foo`, `$x instanceof $class` |
| `catch` | `catch (Foo $e)` |
| `attribute` | `#[Foo]` |
| `call` | call to a project-declared function |
| `const` | use of a project-declared constant |
| `include` | `include` / `require` family |

A class named by an expression instead of a name (`new $class()`,
`new ($factory())(1)`, `$class::method()`, `$class::CONST`, `$class::$prop`,
`$x instanceof $class`) has no name to resolve. It is recorded as
`unresolved:dynamic:<source text>`, the expression as written with runs of
whitespace collapsed to one space, with the edge kind of the construct (`new`,
`static`, `instanceof`). `$object::class` loads nothing and adds no edge.

Not in v0.1: docblock types (`@param Foo`), string class names
(`'App\Foo'`), and functions that take a class name (`class_exists($class)`,
`app()->make($class)`).

## Parser

The reference implementation uses
[nikic/PHP-Parser](https://github.com/nikic/PHP-Parser) and its `NameResolver`.
A file that fails to parse is still a node, with `"error": "parse"`; the
scanner reports the error and records no edges for it. A file that cannot be
read gets `"error": "read"`.
