<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests;

use PHPUnit\Framework\TestCase;
use Untangled\Diagnostic;

final class DiagnosticTest extends TestCase
{
    public function testTheFieldsAreWrittenInTheSpecifiedOrder(): void
    {
        $diagnostic = Diagnostic::warning('uncovered-files', 'three files', ['a.php', 'b/c.php']);
        self::assertSame('{"level":"warning","code":"uncovered-files","message":"three files","files":["a.php","b/c.php"]}', $diagnostic->toJson());
        self::assertSame(['level', 'code', 'message', 'files'], array_keys($diagnostic->toArray()));
    }

    public function testNoFilesMeansNoFilesField(): void
    {
        $diagnostic = Diagnostic::error('project-unreadable', 'not a folder');
        self::assertSame('{"level":"error","code":"project-unreadable","message":"not a folder"}', $diagnostic->toJson());
        self::assertSame('error: not a folder', $diagnostic->toText());
        self::assertSame('warning: x', Diagnostic::warning('c-d', 'x')->toText());
    }

    public function testASpecialMessageStaysOneValidLine(): void
    {
        $message = "quote \" backslash \\ newline \n tab \t cr \r nul \0 unit \x1f slash / unicode é 漢 😀 separator \u{2028}";
        $json = Diagnostic::warning('some-code', $message, ["dir/na\"me\n.php", 'ünï/ç.php'])->toJson();
        self::assertStringNotContainsString("\n", $json);
        self::assertStringNotContainsString("\r", $json);
        $decoded = json_decode($json, true, 512, JSON_THROW_ON_ERROR);
        self::assertSame($message, $decoded['message']);
        self::assertSame(["dir/na\"me\n.php", 'ünï/ç.php'], $decoded['files']);
        // Slashes and non-ASCII are written as they are; control characters are escaped in lower-case hex.
        self::assertStringContainsString('slash / unicode é 漢 😀', $json);
        self::assertStringContainsString('\\u001f', $json);
        self::assertStringContainsString('\\u0000', $json);
    }

    public function testTextThatIsNotUtf8IsWrittenWithTheReplacementCharacter(): void
    {
        $json = Diagnostic::warning('some-code', "bad \xff byte", ["na\xffme.php"])->toJson();
        $decoded = json_decode($json, true, 512, JSON_THROW_ON_ERROR);
        self::assertSame("bad \u{fffd} byte", $decoded['message']);
        self::assertSame(["na\u{fffd}me.php"], $decoded['files']);
    }
}
