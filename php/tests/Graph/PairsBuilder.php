<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests\Graph;

use Untangled\Graph\PairsDocument;

/** Builds small pairs documents from "from -> to" strings, for analysis tests. */
final class PairsBuilder
{
    /**
     * Internal nodes are ids without a prefix; `composer:`, `builtin:` and `unresolved:` ids
     * get their kind from the prefix.
     *
     * @param list<string> $edges like 'a.php -> b.php'
     * @param array<string, string> $modules internal id => module
     * @param list<string> $isolated internal ids with no edges
     */
    public static function build(array $edges, array $modules = [], array $isolated = []): PairsDocument
    {
        $document = new PairsDocument('php');
        $add = static function (string $id) use ($document, $modules): void {
            $kind = match (true) {
                str_starts_with($id, 'composer:') => PairsDocument::EXTERNAL,
                str_starts_with($id, 'builtin:') => PairsDocument::BUILTIN,
                str_starts_with($id, 'unresolved:') => PairsDocument::UNRESOLVED,
                default => PairsDocument::INTERNAL,
            };
            $document->addNode($id, $kind, isset($modules[$id]) ? ['module' => $modules[$id]] : []);
        };
        foreach ($isolated as $id) {
            $add($id);
        }
        foreach ($edges as $edge) {
            [$from, $to] = array_map('trim', explode('->', $edge));
            $add($from);
            $add($to);
            $document->addEdge($from, $to, 'new');
        }
        return $document;
    }
}
