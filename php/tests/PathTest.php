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
        yield ['d:/www/../app//x.php', 'D:/app/x.php'];
        yield ['D:\\', 'D:/'];
        yield ['C:/a/../../b', 'C:/b'];
        yield ['src\\..\\lib\\x.php', 'lib/x.php'];
    }

    #[DataProvider('normalized')]
    public function testNormalize(string $path, string $expected): void
    {
        self::assertSame($expected, Path::normalize($path));
    }

    public function testJoin(): void
    {
        self::assertSame('D:/other/x.php', Path::join('D:/www/p', 'd:\\other\\x.php'));
        self::assertSame('D:/www/p/src/a.php', Path::join('D:/www/p', 'src\\a.php'));
        self::assertSame('/p/src/a.php', Path::join('/p', 'src/a.php'));
        self::assertSame('/p/a.php', Path::join('/p/src', '../a.php'));
        self::assertSame('/etc/x.php', Path::join('/p', '/etc/x.php'));
    }

    public function testIsAbsolute(): void
    {
        foreach (['/a', 'C:/a', 'c:\\a', 'D:\\'] as $path) {
            self::assertTrue(Path::isAbsolute($path), $path);
        }
        foreach (['a/b', './a', '../a', 'C:a', 'C:', ''] as $path) {
            self::assertFalse(Path::isAbsolute($path), $path);
        }
    }

    public function testRelativeOnAWindowsDrive(): void
    {
        self::assertSame('vendor/autoload.php', Path::relative('d:\\www\\app', 'D:/www/app/vendor/autoload.php'));
        self::assertSame('.', Path::relative('D:/www/app', 'D:/www/app'));
        self::assertNull(Path::relative('D:/www/app', 'E:/www/app/x.php'));
        self::assertSame('x.php', Path::relative('D:/', 'D:/x.php'));
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
