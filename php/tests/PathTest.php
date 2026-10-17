<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests;

use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;
use Untangled\Path;

final class PathTest extends TestCase
{
    /** @return iterable<array{string, string}> */
    public static function normalized(): iterable
    {
        yield ['/a/./b/../c//d', '/a/c/d'];
        yield ['../x/../../y', '../../y'];
        yield ['/../a', '/a'];
        yield ['a/b/..', 'a'];
        yield ['./', ''];
        yield ['C:\\src\\Foo.php', 'C:/src/Foo.php'];
        yield ['src\\..\\lib\\x.php', 'lib/x.php'];
    }

    #[DataProvider('normalized')]
    public function testNormalize(string $path, string $expected): void
    {
        self::assertSame($expected, Path::normalize($path));
    }

    public function testJoin(): void
    {
        self::assertSame('/p/src/a.php', Path::join('/p', 'src/a.php'));
        self::assertSame('/p/a.php', Path::join('/p/src', '../a.php'));
        self::assertSame('/etc/x.php', Path::join('/p', '/etc/x.php'));
    }

    public function testRelative(): void
    {
        self::assertSame('src/A.php', Path::relative('/p', '/p/src/A.php'));
        self::assertSame('src/A.php', Path::relative('/p/', '/p/./src/A.php'));
        self::assertSame('.', Path::relative('/p', '/p'));
        self::assertNull(Path::relative('/p', '/pp/A.php'));
        self::assertNull(Path::relative('/p', '/p/../q/A.php'));
    }
}
