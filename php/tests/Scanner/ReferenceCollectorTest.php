<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests\Scanner;

use PHPUnit\Framework\Attributes\DataProvider;

/** One test per construct in the edge-kind table of spec/languages/php.md. */
final class ReferenceCollectorTest extends CollectorTestCase
{
    /** @return iterable<string, array{string, list<string>}> */
    public static function constructs(): iterable
    {
        yield 'import' => ['use App\\Models\\User;', ['import class App\\Models\\User']];
        yield 'aliased import' => ['use App\\Models\\User as U; new U();', ['import class App\\Models\\User', 'new class App\\Models\\User']];
        yield 'grouped import' => ['use App\\{Models\\User, Billing\\Tax};', ['import class App\\Models\\User', 'import class App\\Billing\\Tax']];
        yield 'function import' => ['use function App\\helper;', ['import function App\\helper']];
        yield 'constant import' => ['use const App\\VERSION;', ['import constant App\\VERSION']];
        yield 'mixed group import' => ['use App\\{Models\\User, function helper, const VERSION};', ['import class App\\Models\\User', 'import function App\\helper', 'import constant App\\VERSION']];
        yield 'extends' => ['namespace App; class A extends B {}', ['extends class App\\B']];
        yield 'interface extends' => ['namespace App; interface A extends B, C {}', ['extends class App\\B', 'extends class App\\C']];
        yield 'implements' => ['namespace App; class A implements B, \\Countable {}', ['implements class App\\B', 'implements class Countable']];
        yield 'enum implements' => ['namespace App; enum Suit: string implements HasLabel { case Hearts = "h"; }', ['implements class App\\HasLabel']];
        yield 'trait' => ['namespace App; class A { use T1, T2; }', ['trait class App\\T1', 'trait class App\\T2']];
        yield 'trait in a trait' => ['namespace App; trait A { use B; }', ['trait class App\\B']];
        yield 'new' => ['namespace App; new Foo();', ['new class App\\Foo']];
        yield 'new fully qualified' => ['namespace App; new \\Other\\Foo();', ['new class Other\\Foo']];
        yield 'new relative to namespace' => ['namespace App; new namespace\\Foo();', ['new class App\\Foo']];
        yield 'static call' => ['namespace App; Foo::make();', ['static class App\\Foo']];
        yield 'class constant' => ['namespace App; Foo::BAR;', ['static class App\\Foo']];
        yield '::class' => ['namespace App; Foo::class;', ['static class App\\Foo']];
        yield 'static property' => ['namespace App; Foo::$bar;', ['static class App\\Foo']];
        yield 'parameter type' => ['namespace App; function f(Foo $x) {}', ['type class App\\Foo']];
        yield 'return type' => ['namespace App; function f(): Foo {}', ['type class App\\Foo']];
        yield 'nullable type' => ['namespace App; function f(?Foo $x) {}', ['type class App\\Foo']];
        yield 'union type' => ['namespace App; function f(Foo|Bar|null $x) {}', ['type class App\\Foo', 'type class App\\Bar']];
        yield 'intersection type' => ['namespace App; function f(Foo&Bar $x) {}', ['type class App\\Foo', 'type class App\\Bar']];
        yield 'DNF type' => ['namespace App; function f((Foo&Bar)|null $x) {}', ['type class App\\Foo', 'type class App\\Bar']];
        yield 'scalar types are not references' => ['namespace App; function f(int $a, ?string $b, array|bool $c): void {}', []];
        yield 'property type' => ['namespace App; class A { private Foo $foo; }', ['type class App\\Foo']];
        yield 'promoted property' => ['namespace App; class A { public function __construct(private Foo $foo) {} }', ['type class App\\Foo']];
        yield 'typed class constant' => ['namespace App; class A { const Foo X = null; }', ['type class App\\Foo']];
        yield 'closure types' => ['namespace App; $f = function (Foo $x): Bar {};', ['type class App\\Foo', 'type class App\\Bar']];
        yield 'arrow function types' => ['namespace App; $f = fn (Foo $x): Bar => $x;', ['type class App\\Foo', 'type class App\\Bar']];
        yield 'instanceof' => ['namespace App; $x instanceof Foo;', ['instanceof class App\\Foo']];
        yield 'catch' => ['namespace App; try {} catch (FooException | \\RuntimeException $e) {}', ['catch class App\\FooException', 'catch class RuntimeException']];
        yield 'attribute' => ['namespace App; #[Route("/")] class A {}', ['attribute class App\\Route']];
        yield 'attribute on a parameter' => ['namespace App; function f(#[Inject] $x) {}', ['attribute class App\\Inject']];
        yield 'function call in a namespace tries both names' => ['namespace App; helper();', ['call function App\\helper|helper']];
        yield 'fully qualified call' => ['namespace App; \\helper();', ['call function helper']];
        yield 'global call' => ['helper();', ['call function helper']];
        yield 'constant in a namespace tries both names' => ['namespace App; echo VERSION;', ['const constant App\\VERSION|VERSION']];
        yield 'true, false and null are not constants' => ['namespace App; $a = [true, FALSE, Null];', []];
        yield 'self and static are dropped' => ['namespace App; class A { function f(): self { return new static(); } function g() { self::x(); } }', []];
        yield 'parent becomes the parent class' => ['namespace App; class A extends B { function f() { parent::f(); } }', ['extends class App\\B', 'static class App\\B']];
        yield 'parent without a parent is dropped' => ['namespace App; class A { function f() { parent::f(); } }', []];
        yield 'parent in a nested anonymous class' => ['namespace App; class A extends B { function f() { return new class extends C { function g() { parent::g(); } }; } }', ['extends class App\\B', 'extends class App\\C', 'static class App\\C']];
        yield 'parent after a nested class' => ['namespace App; class A extends B { function f() { new class {}; parent::f(); } }', ['extends class App\\B', 'static class App\\B']];
        yield 'dynamic class names are unresolved' => ['namespace App; new $class(); $class::make(); $x instanceof $y;', [
            'new dynamic $class',
            'static dynamic $class',
            'instanceof dynamic $y',
        ]];
        yield 'dynamic class constants and properties' => ['namespace App; $c::CONST; $c::$prop;', ['static dynamic $c', 'static dynamic $c']];
        yield 'dynamic class from an expression' => ['namespace App; new ($factory())(1);', ['new dynamic $factory()']];
        yield 'dynamic source text collapses whitespace' => ["namespace App; new (\$a\n    ->b())();", ['new dynamic $a ->b()']];
        yield '::class on an object names nothing to load' => ['namespace App; $o::class;', []];
        yield 'string class names are not references' => ['namespace App; $c = "App\\\\Foo";', []];
        yield 'docblock types are not references' => ["namespace App; /** @param Foo \$x */ function f(\$x) {}", []];
    }

    /** @param list<string> $expected */
    #[DataProvider('constructs')]
    public function testReferences(string $code, array $expected): void
    {
        self::assertSame($expected, self::references('<?php ' . $code));
    }

    public function testDeclarations(): void
    {
        $result = self::scan(<<<'PHP'
            <?php
            namespace App;
            class A {}
            interface B {}
            trait C {}
            enum D {}
            function helper() {}
            const VERSION = '1', BUILD = 2;
            define('GLOBAL_FLAG', true);
            define('\Leading\SLASH', true);
            define($dynamic, true);
            new class {};
            PHP);
        self::assertSame(['App\\A', 'App\\B', 'App\\C', 'App\\D'], $result->classes);
        self::assertSame(['App\\helper'], $result->functions);
        self::assertSame(['App\\VERSION', 'App\\BUILD', 'GLOBAL_FLAG', 'Leading\\SLASH'], $result->constants);
        self::assertSame(['App\\A', 'App\\B', 'App\\BUILD', 'App\\C', 'App\\D', 'App\\VERSION', 'App\\helper', 'GLOBAL_FLAG', 'Leading\\SLASH'], $result->symbols());
    }

    public function testModuleIsTheFirstNamespace(): void
    {
        self::assertSame('App\\First', self::scan('<?php namespace App\\First { class A {} } namespace App\\Second { class B {} }')->module);
        self::assertSame(['App\\First\\A', 'App\\Second\\B'], self::scan('<?php namespace App\\First { class A {} } namespace App\\Second { class B {} }')->classes);
    }

    public function testNoNamespaceMeansNoModule(): void
    {
        self::assertNull(self::scan('<?php class A {}')->module);
        // A global namespace block has no name either.
        self::assertNull(self::scan('<?php namespace { class A {} }')->module);
    }

    public function testFunctionsDeclaredInsideFunctionsCount(): void
    {
        self::assertSame(['App\\outer', 'App\\inner'], self::scan('<?php namespace App; function outer() { function inner() {} }')->functions);
    }

    public function testParseErrorsAreReported(): void
    {
        $result = self::scan('<?php class {');
        self::assertNotNull($result->error);
        self::assertStringStartsWith('parse error: ', (string) $result->error);
        self::assertSame([], $result->references);
    }

    public function testAnUnreadableFileIsReported(): void
    {
        $result = (new \Untangled\Scanner\FileScanner())->scan('/no/such/file.php');
        self::assertSame('cannot read file', $result->error);
    }

    public function testAFileWithOnlyHtmlIsEmpty(): void
    {
        $result = self::scan('<html><body>hi</body></html>');
        self::assertNull($result->error);
        self::assertSame([], $result->references);
    }
}
