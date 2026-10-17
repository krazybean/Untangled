<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests\Report;

use PHPUnit\Framework\TestCase;
use Untangled\Analysis\Analyzer;
use Untangled\Analysis\Clustering;
use Untangled\Graph\PairsDocument;
use Untangled\Report\Report;
use Untangled\Tests\Graph\PairsBuilder;

final class ReportTest extends TestCase
{
    public function testCarriesTheAnalysis(): void
    {
        $doc = self::demo();
        $report = Report::build('Demo', $doc);
        self::assertSame('Demo', $report->title);
        self::assertSame((new Analyzer())->analyze($doc), $report->analysis);
        self::assertFalse($report->isClustered());
        self::assertSame([], $report->dropped);
    }

    public function testMarksEdgesInsideACycle(): void
    {
        self::assertSame(
            ['a.php>b.php*', 'b.php>a.php*', 'b.php>c.php'],
            array_map(static fn (array $e): string => $e['from'] . '>' . $e['to'] . ($e['cycle'] ? '*' : ''), Report::build('Demo', self::demo())->unitEdges()),
        );
    }

    public function testAnEdgeBetweenTwoDifferentCyclesIsNotACycleEdge(): void
    {
        $report = Report::build('Two', PairsBuilder::build(['a.php -> b.php', 'b.php -> a.php', 'b.php -> c.php', 'c.php -> d.php', 'd.php -> c.php']));
        $edges = array_column(array_map(static fn (array $e): array => [$e['from'] . '>' . $e['to'], $e['cycle']], $report->unitEdges()), 1, 0);
        self::assertFalse($edges['b.php>c.php']);
        self::assertTrue($edges['c.php>d.php']);
    }

    public function testUnitEdgesKeepTheirCountAndLeaveOutOtherNodes(): void
    {
        $doc = self::demo();
        $doc->addEdge('b.php', 'c.php', 'type');
        $edges = Report::build('Demo', $doc)->unitEdges();
        self::assertSame(['from' => 'b.php', 'to' => 'c.php', 'count' => 2, 'cycle' => false], $edges[2]);
        self::assertCount(3, $edges);
    }

    public function testCycleOfNumbersCyclesFromOne(): void
    {
        $report = Report::build('Two', PairsBuilder::build(['a.php -> b.php', 'b.php -> c.php', 'c.php -> a.php', 'x.php -> y.php', 'y.php -> x.php']));
        self::assertSame(['a.php' => 1, 'b.php' => 1, 'c.php' => 1, 'x.php' => 2, 'y.php' => 2], $report->cycleOf());
    }

    public function testListsWhoUsesEachPackageAndReference(): void
    {
        $report = Report::build('Demo', self::demo());
        self::assertSame(['composer:x/y' => ['a.php', 'c.php']], $report->targets(PairsDocument::EXTERNAL));
        self::assertSame(['unresolved:class:</script><b>X' => ['c.php']], $report->targets(PairsDocument::UNRESOLVED));
    }

    public function testClusteredReportsUseTheClusterGraph(): void
    {
        $doc = PairsBuilder::build(['a/1.php -> a/2.php', 'a/1.php -> b/1.php', 'a/2.php -> composer:x/y', 'b/1.php -> composer:x/y']);
        $report = Report::build('Grouped', $doc, Clustering::fromString('folder:1'));
        self::assertTrue($report->isClustered());
        self::assertSame(['a' => 1], $report->dropped);
        self::assertSame([['from' => 'a', 'to' => 'b', 'count' => 1, 'cycle' => false]], $report->unitEdges());
        self::assertSame(['composer:x/y' => ['a', 'b']], $report->targets(PairsDocument::EXTERNAL));
    }

    public function testRefusesAnAlreadyClusteredDocument(): void
    {
        ['document' => $clustered] = Clustering::fromString('folder:1')->apply(PairsBuilder::build(['a/1.php -> b/1.php']));
        $this->expectException(\InvalidArgumentException::class);
        Report::build('x', $clustered);
    }

    /** a and b depend on each other, b uses c; a and c use a package; c has a hostile unresolved name. */
    public static function demo(): PairsDocument
    {
        return PairsBuilder::build([
            'a.php -> b.php',
            'b.php -> a.php',
            'b.php -> c.php',
            'a.php -> composer:x/y',
            'c.php -> composer:x/y',
            'c.php -> unresolved:class:</script><b>X',
        ]);
    }
}
