<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests\Scanner;

use PHPUnit\Framework\TestCase;
use Untangled\Diagnostic;
use Untangled\Graph\PairsDocument;
use Untangled\Scanner\ScanResult;

/** Code written before diagnostics existed builds and reads a ScanResult the same way. */
final class ScanResultTest extends TestCase
{
    public function testTheOldConstructionWithWarningStringsStillWorks(): void
    {
        $pairs = new PairsDocument('php');
        $positional = new ScanResult($pairs, ['src/A.php: parse error', 'second']);
        self::assertSame($pairs, $positional->pairs);
        self::assertSame(['src/A.php: parse error', 'second'], $positional->warnings);
        self::assertSame([], $positional->diagnostics);

        $named = new ScanResult(pairs: $pairs, warnings: ['only']);
        self::assertSame(['only'], $named->warnings);
        self::assertSame([], $named->diagnostics);

        $none = new ScanResult($pairs);
        self::assertSame([[], []], [$none->warnings, $none->diagnostics]);
    }

    public function testDiagnosticsAreAnAdditionalArgumentAfterTheWarnings(): void
    {
        $diagnostic = Diagnostic::warning('nothing-scanned', 'nothing');
        $result = new ScanResult(new PairsDocument('php'), ['nothing'], [$diagnostic]);
        self::assertSame(['nothing'], $result->warnings);
        self::assertSame([$diagnostic], $result->diagnostics);
    }

    public function testFromDiagnosticsDerivesTheWarningsFromTheWarningDiagnostics(): void
    {
        $result = ScanResult::fromDiagnostics(new PairsDocument('php'), [
            Diagnostic::warning('a-b', 'first'),
            Diagnostic::error('c-d', 'an error'),
            Diagnostic::warning('e-f', 'second'),
        ]);
        self::assertSame(['first', 'second'], $result->warnings);
        self::assertCount(3, $result->diagnostics);
    }
}
