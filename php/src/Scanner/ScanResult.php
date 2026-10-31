<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Scanner;

use Untangled\Diagnostic;
use Untangled\Graph\PairsDocument;

final class ScanResult
{
    /**
     * The messages of the warning diagnostics, kept for callers that read strings. New code
     * should read $diagnostics.
     *
     * @var list<string>
     */
    public readonly array $warnings;

    /** @param list<Diagnostic> $diagnostics problems that did not stop the scan, such as parse errors */
    public function __construct(
        public readonly PairsDocument $pairs,
        public readonly array $diagnostics,
    ) {
        $this->warnings = array_values(array_map(
            static fn (Diagnostic $diagnostic): string => $diagnostic->message,
            array_filter($diagnostics, static fn (Diagnostic $diagnostic): bool => $diagnostic->level === Diagnostic::WARNING),
        ));
    }
}
