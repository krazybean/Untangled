<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests\Scanner;

use PHPUnit\Framework\Attributes\DataProvider;

/** How include / require paths are evaluated (spec/languages/php.md, "include / require"). */
final class IncludeEvaluationTest extends CollectorTestCase
{
    /** @return iterable<string, array{string, ?string, string}> */
    public static function includes(): iterable
    {
        yield 'string literal' => ["include 'lib/a.php';", 'lib/a.php', "'lib/a.php'"];
        yield 'double-quoted literal' => ['require "lib/a.php";', 'lib/a.php', '"lib/a.php"'];
        yield 'include_once' => ["include_once 'a.php';", 'a.php', "'a.php'"];
        yield 'require_once' => ["require_once 'a.php';", 'a.php', "'a.php'"];
        yield '__DIR__' => ["require __DIR__ . '/a.php';", '/project/src/a.php', "__DIR__ . '/a.php'"];
        yield '__FILE__' => ['require __FILE__;', '/project/src/File.php', '__FILE__'];
        yield 'dirname(__FILE__)' => ["require dirname(__FILE__) . '/a.php';", '/project/src/a.php', "dirname(__FILE__) . '/a.php'"];
        yield 'dirname(__DIR__)' => ["require dirname(__DIR__) . '/a.php';", '/project/a.php', "dirname(__DIR__) . '/a.php'"];
        yield 'dirname with levels' => ["require dirname(__FILE__, 2) . '/a.php';", '/project/a.php', "dirname(__FILE__, 2) . '/a.php'"];
        yield 'nested dirname' => ["require dirname(dirname(__FILE__)) . '/a.php';", '/project/a.php', "dirname(dirname(__FILE__)) . '/a.php'"];
        yield 'chained concatenation' => ["require __DIR__ . '/lib' . '/' . 'a.php';", '/project/src/lib/a.php', "__DIR__ . '/lib' . '/' . 'a.php'"];
        yield 'parenthesised' => ["require(__DIR__ . '/a.php');", '/project/src/a.php', "__DIR__ . '/a.php'"];
        yield 'variable' => ["include \$base . '/a.php';", null, "\$base . '/a.php'"];
        yield 'constant' => ["include APP_ROOT . '/a.php';", null, "APP_ROOT . '/a.php'"];
        yield 'function call' => ["include path('a.php');", null, "path('a.php')"];
        yield 'dirname with variable levels' => ["include dirname(__FILE__, \$n) . '/a.php';", null, "dirname(__FILE__, \$n) . '/a.php'"];
        yield 'interpolated string' => ['include "$dir/a.php";', null, '"$dir/a.php"'];
        yield 'whitespace collapses in the source text' => ["include \$a\n    .   '/x.php';", null, "\$a . '/x.php'"];
    }

    #[DataProvider('includes')]
    public function testIncludes(string $code, ?string $path, string $text): void
    {
        self::assertSame([['path' => $path, 'text' => $text]], self::scan('<?php ' . $code)->includes);
    }

    public function testIncludesAreNotClassReferences(): void
    {
        self::assertSame([], self::scan("<?php require __DIR__ . '/a.php';")->references);
    }
}
