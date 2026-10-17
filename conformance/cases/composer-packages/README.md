# composer-packages

Without a `vendor/` directory, packages come from `composer.lock`. Classes
under a package's `psr-4` or `psr-0` prefix become one `composer:<name>` node
per package, whatever the class. `use App\Models;` names a namespace, not a
class, so the import is dropped; `Models\User` itself is unresolved because
no file declares it.
