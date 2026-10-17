<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests;

use PHPUnit\Framework\TestCase;
use Untangled\Text;

final class TextTest extends TestCase
{
    public function testValidUtf8IsUnchanged(): void
    {
        self::assertSame('App\\Café', Text::utf8('App\\Café'));
        self::assertSame('', Text::utf8(''));
    }

    public function testOtherBytesAreReadAsWindows1252(): void
    {
        self::assertSame('Café', Text::utf8("Caf\xe9"));
        self::assertSame('€uro—ŸÿÀ', Text::utf8("\x80uro\x97\x9f\xff\xc0"));
    }

    public function testUndefinedWindows1252BytesFallBackToLatin1(): void
    {
        self::assertSame("\u{81}\u{8D}\u{8F}\u{90}\u{9D}", Text::utf8("\x81\x8d\x8f\x90\x9d"));
    }
}
