<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests\Graph;

use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;
use Untangled\Graph\DocumentException;
use Untangled\Graph\Json;

final class JsonTest extends TestCase
{
    /** @return iterable<string, array{float|int, float|int, string}> */
    public static function numbers(): iterable
    {
        yield 'zero' => [0, 0, '0'];
        yield 'float zero' => [0.0, 0, '0'];
        yield 'one' => [1.0, 1, '1'];
        yield 'a third' => [1 / 3, 0.3333, '0.3333'];
        yield 'two thirds rounds up' => [2 / 3, 0.6667, '0.6667'];
        yield 'a half' => [0.5, 0.5, '0.5'];
        yield 'rounds to a whole number' => [0.99999, 1, '1'];
        yield 'large' => [7 / 6 + 10, 11.1667, '11.1667'];
    }

    #[DataProvider('numbers')]
    public function testNumberRoundsToFourPlacesAndWritesWholeNumbersAsIntegers(float|int $value, float|int $expected, string $written): void
    {
        self::assertSame($expected, Json::number($value));
        self::assertSame($written, json_encode(Json::number($value)));
    }

    public function testEncodeIndentsNestedLevelsByTwo(): void
    {
        self::assertSame("{\n  \"a\": {\n    \"b\": [\n      1\n    ]\n  }\n}\n", Json::encode(['a' => ['b' => [1]]]));
    }

    public function testEncodeLeavesFourSpacesInsideStringsAlone(): void
    {
        self::assertStringContainsString('"x    y"', Json::encode(['s' => 'x    y']));
    }

    public function testDecodeRejectsInvalidJson(): void
    {
        $this->expectException(DocumentException::class);
        $this->expectExceptionMessage('pairs.json is not valid JSON');
        Json::decode('{', 'pairs.json');
    }

    public function testDecodeRejectsAScalar(): void
    {
        $this->expectException(DocumentException::class);
        $this->expectExceptionMessage('is not a JSON object');
        Json::decode('42', 'pairs.json');
    }
}
