<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Graph;

use Untangled\Version;

/**
 * The pairs document from spec/pairs-format.md: nodes plus merged (from, to) edges.
 */
final class PairsDocument
{
    public const INTERNAL = 'internal';
    public const EXTERNAL = 'external';
    public const BUILTIN = 'builtin';
    public const UNRESOLVED = 'unresolved';

    /** @var array<string, array<string, mixed>> */
    private array $nodes = [];

    /** @var array<string, array{from: string, to: string, kinds: array<string, true>, count: int}> */
    private array $edges = [];

    public function __construct(private readonly string $language)
    {
    }

    /** @param array<string, mixed> $extra */
    public function addNode(string $id, string $kind, array $extra = []): void
    {
        $this->nodes[$id] ??= ['id' => $id, 'kind' => $kind] + $extra;
    }

    public function hasNode(string $id): bool
    {
        return isset($this->nodes[$id]);
    }

    /** Records one reference; repeated references to the same target merge. Self-edges are dropped. */
    public function addEdge(string $from, string $to, string $kind): void
    {
        if ($from === $to) {
            return;
        }
        $key = $from . "\0" . $to;
        $this->edges[$key] ??= ['from' => $from, 'to' => $to, 'kinds' => [], 'count' => 0];
        $this->edges[$key]['kinds'][$kind] = true;
        $this->edges[$key]['count']++;
    }

    /** @return list<array{from: string, to: string, kinds: list<string>, count: int}> */
    public function edges(): array
    {
        $edges = [];
        foreach ($this->edges as $edge) {
            $kinds = array_keys($edge['kinds']);
            sort($kinds, SORT_STRING);
            $edges[] = ['from' => $edge['from'], 'to' => $edge['to'], 'kinds' => $kinds, 'count' => $edge['count']];
        }
        usort($edges, static fn (array $a, array $b): int => [$a['from'], $a['to']] <=> [$b['from'], $b['to']]);
        return $edges;
    }

    /** @return list<array<string, mixed>> */
    public function nodes(): array
    {
        $nodes = $this->nodes;
        ksort($nodes, SORT_STRING);
        return array_values($nodes);
    }

    /** @return array<string, mixed> */
    public function toArray(): array
    {
        return [
            'format' => 'untangled-pairs',
            'version' => Version::SPEC,
            'language' => $this->language,
            'generator' => ['name' => Version::NAME, 'version' => Version::VERSION],
            'nodes' => $this->nodes(),
            'edges' => $this->edges(),
        ];
    }

    public function toJson(): string
    {
        $json = json_encode($this->toArray(), JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR);
        // json_encode indents by four spaces; the spec asks for two.
        $json = preg_replace_callback('/^(?: {4})+/m', static fn (array $m): string => str_repeat(' ', intdiv(strlen($m[0]), 2)), $json);
        return $json . "\n";
    }

    /**
     * snakefood's line format: ((root, from), (root, to)), and ((root, file), (None, None))
     * for files without internal dependencies. Only internal nodes are written.
     */
    public function toSnakefood(string $root): string
    {
        $quote = static fn (string $s): string => "'" . addcslashes($s, "\\'") . "'";
        $lines = [];
        $hasDeps = [];
        foreach ($this->edges() as $edge) {
            if (($this->nodes[$edge['to']]['kind'] ?? null) !== self::INTERNAL) {
                continue;
            }
            $hasDeps[$edge['from']] = true;
            $lines[] = sprintf('((%s, %s), (%s, %s))', $quote($root), $quote($edge['from']), $quote($root), $quote($edge['to']));
        }
        foreach ($this->nodes() as $node) {
            if ($node['kind'] === self::INTERNAL && !isset($hasDeps[$node['id']])) {
                $lines[] = sprintf('((%s, %s), (None, None))', $quote($root), $quote($node['id']));
            }
        }
        sort($lines, SORT_STRING);
        return $lines === [] ? '' : implode("\n", $lines) . "\n";
    }
}
