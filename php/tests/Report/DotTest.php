<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests\Report;

use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;
use Untangled\Analysis\Clustering;
use Untangled\Analysis\Filter;
use Untangled\Graph\PairsDocument;
use Untangled\Report\Dot;
use Untangled\Report\Report;
use Untangled\Tests\Graph\PairsBuilder;

/** The DOT format of spec/report.md, byte for byte. */
final class DotTest extends TestCase
{
    private const HEADER = "digraph untangled {\n  graph [rankdir=LR, fontname=\"Helvetica\"];\n  node [shape=box, style=rounded, fontname=\"Helvetica\"];\n  edge [color=\"#898781\"];\n";

    /** @return iterable<string, array{string, string}> */
    public static function quoted(): iterable
    {
        yield 'plain' => ['src/A.php', '"src/A.php"'];
        yield 'backslash' => ['App\\X', '"App\\\\X"'];
        yield 'quote' => ['say "hi"', '"say \\"hi\\""'];
        yield 'newline' => ["a\nb", '"a\\nb"'];
        yield 'everything' => ["App\\X \"y\"\nz", '"App\\\\X \\"y\\"\\nz"'];
        yield 'empty' => ['', '""'];
    }

    #[DataProvider('quoted')]
    public function testQuote(string $text, string $expected): void
    {
        self::assertSame($expected, Dot::quote($text));
    }

    public function testTheSpecExample(): void
    {
        $report = Report::build('x', PairsBuilder::build(['src/A.php -> src/B.php', 'src/B.php -> src/A.php', 'src/B.php -> src/C.php']));
        self::assertSame(self::HEADER . <<<'DOT'

              "src/A.php" [color="#d03b3b", penwidth=2];
              "src/B.php" [color="#d03b3b", penwidth=2];
              "src/C.php";

              "src/A.php" -> "src/B.php" [color="#d03b3b", penwidth=2];
              "src/B.php" -> "src/A.php" [color="#d03b3b", penwidth=2];
              "src/B.php" -> "src/C.php";
            }

            DOT, Dot::render($report));
    }

    public function testAnEmptyGraphIsJustTheHeader(): void
    {
        self::assertSame(self::HEADER . "}\n", Dot::render(Report::build('x', new PairsDocument('php'))));
    }

    public function testUnitsWithoutEdgesHaveNoEdgeBlock(): void
    {
        self::assertSame(self::HEADER . "\n  \"a.php\";\n}\n", Dot::render(Report::build('x', PairsBuilder::build([], isolated: ['a.php']))));
    }

    public function testExternalAndUnresolvedNodesAreLeftOut(): void
    {
        $dot = Dot::render(Report::build('x', PairsBuilder::build(['a.php -> composer:x/y', 'a.php -> unresolved:class:Q'])));
        self::assertSame(self::HEADER . "\n  \"a.php\";\n}\n", $dot);
    }

    public function testClusterUnitsAreLabelledWithTheirFileCount(): void
    {
        $doc = PairsBuilder::build(['App/A.php -> Lib/B.php', 'App/C.php -> Lib/B.php']);
        $dot = Dot::render(Report::build('x', $doc, Clustering::fromString('folder:1')));
        self::assertStringContainsString("  \"App\" [label=\"App\\n2 files\"];\n", $dot);
        self::assertStringContainsString("  \"Lib\" [label=\"Lib\\n1 file\"];\n", $dot);
        self::assertStringContainsString("  \"App\" -> \"Lib\";\n", $dot);
    }

    public function testTheCycleHighlightComesAfterTheLabel(): void
    {
        $doc = PairsBuilder::build(['a/1.php -> b/1.php', 'b/1.php -> a/1.php']);
        $dot = Dot::render(Report::build('x', $doc, Clustering::fromString('folder:1')));
        self::assertStringContainsString('  "a" [label="a\\n1 file", color="#d03b3b", penwidth=2];', $dot);
    }

    public function testNamespaceIdsKeepTheirBackslashes(): void
    {
        $doc = PairsBuilder::build(['a.php -> b.php'], modules: ['a.php' => 'App\\Http', 'b.php' => 'App\\Domain']);
        $dot = Dot::render(Report::build('x', $doc, Clustering::fromString('namespace:2')));
        self::assertStringContainsString('  "App\\\\Http" -> "App\\\\Domain";', $dot);
    }

    private const CLASSIC_HEADER = "digraph untangled {\n  graph [rankdir=LR];\n  node [shape=ellipse, style=filled, fillcolor=lightgrey, fontname=\"Times-Roman\", fontsize=7];\n  edge [color=black];\n";

    public function testClassicDrawsUnitsGreyAndWhatTheyUseWhiteWithNoCycleColour(): void
    {
        $doc = PairsBuilder::build([
            'src/A.php -> src/B.php', 'src/B.php -> src/A.php', 'src/A.php -> composer:x/y',
            'src/B.php -> builtin:DateTime', 'src/B.php -> unresolved:class:Q', 'src/B.php -> composer:x/y',
        ]);
        self::assertSame(self::CLASSIC_HEADER . <<<'DOT'

              "src/A.php";
              "src/B.php";
              "composer:x/y" [fillcolor=white];
              "unresolved:class:Q" [fillcolor=white];

              "src/A.php" -> "composer:x/y";
              "src/A.php" -> "src/B.php";
              "src/B.php" -> "composer:x/y";
              "src/B.php" -> "src/A.php";
              "src/B.php" -> "unresolved:class:Q";
            }

            DOT, Dot::render(Report::build('x', $doc), 'classic'));
    }

    public function testClassicOfAnEmptyGraphIsJustTheHeader(): void
    {
        self::assertSame(self::CLASSIC_HEADER . "}\n", Dot::render(Report::build('x', new PairsDocument('php')), 'classic'));
    }

    public function testClassicLeavesOutWhatFilteredUnitsUse(): void
    {
        $doc = PairsBuilder::build(['a.php -> b.php', 'b.php -> composer:x/y']);
        $dot = Dot::render(Report::build('x', (new Filter())->exclude('b.php')->apply($doc)), 'classic');
        self::assertSame(self::CLASSIC_HEADER . "\n  \"a.php\";\n}\n", $dot);
    }

    public function testClassicLabelsClustersAndKeepsTheirExternalEdges(): void
    {
        $doc = PairsBuilder::build(['App/A.php -> Lib/B.php', 'App/C.php -> composer:x/y']);
        $dot = Dot::render(Report::build('x', $doc, Clustering::fromString('folder:1')), 'classic');
        self::assertStringContainsString("  \"App\" [label=\"App\\n2 files\"];\n", $dot);
        self::assertStringContainsString("  \"App\" -> \"composer:x/y\";\n", $dot);
        self::assertStringContainsString("  \"composer:x/y\" [fillcolor=white];\n", $dot);
    }
}
