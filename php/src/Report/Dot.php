<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Report;

/**
 * Writes the unit graph as Graphviz DOT, byte for byte as spec/report.md describes, so it can
 * be rendered with `dot -Tsvg` or opened in any Graphviz viewer.
 */
final class Dot
{
    /** The status colour for cycles, shared with the HTML report. */
    public const CYCLE_COLOR = '#d03b3b';

    public static function render(Report $report): string
    {
        $clustered = $report->isClustered();
        $cycleOf = $report->cycleOf();
        $lines = [
            'digraph untangled {',
            '  graph [rankdir=LR, fontname="Helvetica"];',
            '  node [shape=box, style=rounded, fontname="Helvetica"];',
            '  edge [color="#898781"];',
        ];
        if ($report->analysis['units'] !== []) {
            $lines[] = '';
        }
        $highlight = 'color="' . self::CYCLE_COLOR . '", penwidth=2';
        foreach ($report->analysis['units'] as $unit) {
            $attributes = [];
            if ($clustered) {
                $files = count($unit['members']);
                $attributes[] = 'label=' . self::quote($unit['id'] . "\n" . $files . ($files === 1 ? ' file' : ' files'));
            }
            if (isset($cycleOf[$unit['id']])) {
                $attributes[] = $highlight;
            }
            $lines[] = '  ' . self::quote($unit['id']) . self::attributes($attributes) . ';';
        }
        $edges = $report->unitEdges();
        if ($edges !== []) {
            $lines[] = '';
        }
        foreach ($edges as $edge) {
            $lines[] = '  ' . self::quote($edge['from']) . ' -> ' . self::quote($edge['to'])
                . self::attributes($edge['cycle'] ? [$highlight] : []) . ';';
        }
        $lines[] = '}';
        return implode("\n", $lines) . "\n";
    }

    /**
     * A DOT quoted string. Backslashes are doubled so namespace separators survive as ids and as
     * labels; a newline becomes DOT's centred line break.
     */
    public static function quote(string $text): string
    {
        return '"' . str_replace(['\\', '"', "\n"], ['\\\\', '\\"', '\\n'], $text) . '"';
    }

    /** @param list<string> $attributes */
    private static function attributes(array $attributes): string
    {
        return $attributes === [] ? '' : ' [' . implode(', ', $attributes) . ']';
    }
}
