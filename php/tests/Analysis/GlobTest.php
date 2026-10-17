<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests\Analysis;

use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;
use Untangled\Analysis\Glob;

final class GlobTest extends TestCase
{
    /** @return iterable<string, array{string, string, bool}> */
    public static function cases(): iterable
    {
        yield 'literal' => ['src/A.php', 'src/A.php', true];
        yield 'matches the whole id' => ['src/A.php', 'lib/src/A.php', false];
        yield 'no prefix match' => ['src', 'src/A.php', false];
        yield '* within a segment' => ['src/*.php', 'src/A.php', true];
        yield '* does not cross /' => ['src/*.php', 'src/B/A.php', false];
        yield '* matches empty' => ['src/*A.php', 'src/A.php', true];
        yield '? one character' => ['src/?.php', 'src/A.php', true];
        yield '? not two' => ['src/?.php', 'src/AB.php', false];
        yield '? not /' => ['src?A.php', 'src/A.php', false];
        yield '** crosses /' => ['src/**', 'src/B/C/A.php', true];
        yield '** at the end needs something' => ['src/**', 'src', false];
        yield '**/ matches no directory' => ['**/Test*.php', 'TestA.php', true];
        yield '**/ matches many directories' => ['**/Test*.php', 'a/b/c/TestA.php', true];
        yield '**/ in the middle' => ['src/**/Legacy/*.php', 'src/Legacy/A.php', true];
        yield '**/ in the middle, nested' => ['src/**/Legacy/*.php', 'src/a/b/Legacy/A.php', true];
        yield '**/ in the middle, not under it' => ['src/**/Legacy/*.php', 'src/a/Legacy/b/A.php', false];
        yield 'dot is literal' => ['src/a.php', 'src/aXphp', false];
        yield 'plus is literal' => ['src/a+b.php', 'src/a+b.php', true];
        yield 'plus is not a quantifier' => ['src/a+b.php', 'src/aab.php', false];
        yield 'brackets are literal' => ['src/[ab].php', 'src/[ab].php', true];
        yield 'brackets are not a class' => ['src/[ab].php', 'src/a.php', false];
        yield 'hash is literal' => ['src/#.php', 'src/#.php', true];
        yield 'case-sensitive' => ['src/a.php', 'src/A.php', false];
        yield 'newline in id' => ['src/*', "src/a\nb", true];
    }

    #[DataProvider('cases')]
    public function testMatches(string $pattern, string $id, bool $expected): void
    {
        self::assertSame($expected, (new Glob($pattern))->matches($id));
    }
}
