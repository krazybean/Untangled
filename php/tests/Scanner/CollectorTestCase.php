<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests\Scanner;

use PHPUnit\Framework\TestCase;
use Untangled\Scanner\FileResult;
use Untangled\Scanner\FileScanner;

/** Helpers for tests that parse a snippet of PHP and look at what it declares and references. */
abstract class CollectorTestCase extends TestCase
{
    protected static function scan(string $code, string $path = '/project/src/File.php'): FileResult
    {
        return (new FileScanner())->scanCode($code, $path);
    }

    /**
     * References as "kind symbol candidate[|fallback]" strings, in source order.
     * @return list<string>
     */
    protected static function references(string $code): array
    {
        return array_map(
            static fn (array $r): string => "{$r['kind']} {$r['symbol']} " . implode('|', $r['candidates']),
            self::scan($code)->references,
        );
    }
}
