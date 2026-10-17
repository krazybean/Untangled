<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests\Analysis;

use PHPUnit\Framework\TestCase;
use Untangled\Analysis\Analyzer;
use Untangled\Analysis\Clustering;
use Untangled\Graph\PairsDocument;
use Untangled\Tests\Graph\PairsBuilder;
use Untangled\Version;

final class AnalyzerTest extends TestCase
{
    public function testHeader(): void
    {
        $analysis = (new Analyzer())->analyze(new PairsDocument('php'));
        self::assertSame('untangled-analysis', $analysis['format']);
        self::assertSame(Version::SPEC, $analysis['version']);
        self::assertSame('php', $analysis['language']);
        self::assertSame(['name' => Version::NAME, 'version' => Version::VERSION], $analysis['generator']);
        self::assertNull($analysis['clustering']);
        self::assertSame(['format', 'version', 'language', 'generator', 'clustering', 'summary', 'units', 'cycles'], array_keys($analysis));
    }

    public function testEmptyProject(): void
    {
        $analysis = (new Analyzer())->analyze(new PairsDocument('php'));
        self::assertSame([
            'units' => 0, 'edges' => 0, 'cycles' => 0, 'largest_cycle' => 0, 'units_in_cycles' => 0,
            'units_in_cycles_ratio' => 0, 'mean_fan_out' => 0, 'external_packages' => 0, 'unresolved_references' => 0,
        ], $analysis['summary']);
        self::assertSame([], $analysis['units']);
        self::assertSame([], $analysis['cycles']);
    }

    public function testFileUnitMetrics(): void
    {
        $analysis = (new Analyzer())->analyze(PairsBuilder::build([
            'a.php -> b.php',
            'a.php -> c.php',
            'b.php -> c.php',
            'a.php -> composer:x/y',
            'a.php -> composer:z/w',
            'b.php -> composer:x/y',
            'c.php -> unresolved:class:Q',
        ], isolated: ['d.php']));
        self::assertSame([
            ['id' => 'a.php', 'fan_in' => 0, 'fan_out' => 2, 'external' => 2, 'unresolved' => 0, 'instability' => 1],
            ['id' => 'b.php', 'fan_in' => 1, 'fan_out' => 1, 'external' => 1, 'unresolved' => 0, 'instability' => 0.5],
            ['id' => 'c.php', 'fan_in' => 2, 'fan_out' => 0, 'external' => 0, 'unresolved' => 1, 'instability' => 0],
            ['id' => 'd.php', 'fan_in' => 0, 'fan_out' => 0, 'external' => 0, 'unresolved' => 0, 'instability' => null],
        ], $analysis['units']);
        self::assertSame([
            'units' => 4, 'edges' => 3, 'cycles' => 0, 'largest_cycle' => 0, 'units_in_cycles' => 0,
            'units_in_cycles_ratio' => 0, 'mean_fan_out' => 0.75, 'external_packages' => 2, 'unresolved_references' => 1,
        ], $analysis['summary']);
    }

    public function testAFileWithOnlyExternalDependenciesHasNullInstability(): void
    {
        $analysis = (new Analyzer())->analyze(PairsBuilder::build(['a.php -> composer:x/y']));
        self::assertNull($analysis['units'][0]['instability']);
        self::assertSame(1, $analysis['units'][0]['external']);
    }

    public function testBuiltinNodesNeverCount(): void
    {
        // The analyzer is normally given a filtered document; a builtin left in still adds nothing.
        $analysis = (new Analyzer())->analyze(PairsBuilder::build(['a.php -> builtin:Countable']));
        self::assertSame(['units' => 1, 'edges' => 0], array_slice($analysis['summary'], 0, 2));
        self::assertSame(0, $analysis['units'][0]['external']);
    }

    public function testCycleSummary(): void
    {
        $analysis = (new Analyzer())->analyze(PairsBuilder::build([
            'a.php -> b.php', 'b.php -> c.php', 'c.php -> a.php',
            'd.php -> e.php', 'e.php -> d.php',
            'f.php -> a.php',
        ]));
        self::assertSame(2, $analysis['summary']['cycles']);
        self::assertSame(3, $analysis['summary']['largest_cycle']);
        self::assertSame(5, $analysis['summary']['units_in_cycles']);
        self::assertSame(0.8333, $analysis['summary']['units_in_cycles_ratio']);
        self::assertSame(['a.php', 'b.php', 'c.php', 'a.php'], $analysis['cycles'][0]['example']);
    }

    public function testFractionsAreRoundedToFourPlaces(): void
    {
        $analysis = (new Analyzer())->analyze(PairsBuilder::build(['a.php -> b.php', 'c.php -> b.php', 'b.php -> d.php']));
        $b = $analysis['units'][1];
        self::assertSame('b.php', $b['id']);
        self::assertSame(0.3333, $b['instability']);
        self::assertSame(0.75, $analysis['summary']['mean_fan_out']);
    }

    public function testClusterUnitsCarryCaCeAndMembersInSpecOrder(): void
    {
        $analysis = (new Analyzer())->analyze(self::layered(), Clustering::fromString('folder:1'));
        self::assertSame('folder:1', $analysis['clustering']);
        self::assertSame(['id', 'fan_in', 'fan_out', 'ca', 'ce', 'external', 'unresolved', 'instability', 'members'], array_keys($analysis['units'][0]));
    }

    public function testCaAndCeCountFilesNotClusters(): void
    {
        $analysis = (new Analyzer())->analyze(self::layered(), Clustering::fromString('folder:1'));
        $units = array_column($analysis['units'], null, 'id');

        // web/ depends on one cluster (core) but on two files in it.
        self::assertSame(1, $units['web']['fan_out']);
        self::assertSame(2, $units['web']['ce']);
        self::assertSame(0, $units['web']['ca']);
        self::assertSame(1, $units['web']['instability']);

        // core/ is used by two files in web/ and one in cli/, and uses nothing outside.
        self::assertSame(2, $units['core']['fan_in']);
        self::assertSame(3, $units['core']['ca']);
        self::assertSame(0, $units['core']['ce']);
        self::assertSame(0, $units['core']['instability']);
    }

    public function testClusterInstabilityUsesCaAndCeNotFanCounts(): void
    {
        // x/ depends on two files of y/; one file of y/ depends back on x/.
        // Fan counts give 1 / (1 + 1) = 0.5, Ca / Ce give 2 / (1 + 2) = 0.6667.
        $doc = PairsBuilder::build(['x/a.php -> y/1.php', 'x/a.php -> y/2.php', 'y/1.php -> x/a.php']);
        $units = array_column((new Analyzer())->analyze($doc, Clustering::fromString('folder:1'))['units'], null, 'id');
        self::assertSame(['fan_in' => 1, 'fan_out' => 1, 'ca' => 1, 'ce' => 2], array_intersect_key($units['x'], array_flip(['fan_in', 'fan_out', 'ca', 'ce'])));
        self::assertSame(0.6667, $units['x']['instability']);
        // y/ is used by one file of x/ and uses that same file: 1 / (1 + 1).
        self::assertSame(0.5, $units['y']['instability']);
    }

    public function testEdgesInsideAClusterDoNotCount(): void
    {
        $doc = PairsBuilder::build(['a/1.php -> a/2.php', 'a/2.php -> a/1.php']);
        $analysis = (new Analyzer())->analyze($doc, Clustering::fromString('folder:1'));
        self::assertSame(['id' => 'a', 'fan_in' => 0, 'fan_out' => 0, 'ca' => 0, 'ce' => 0, 'external' => 0, 'unresolved' => 0, 'instability' => null, 'members' => ['a/1.php', 'a/2.php']], $analysis['units'][0]);
        self::assertSame(0, $analysis['summary']['edges']);
        self::assertSame([], $analysis['cycles']);
    }

    public function testClusteringCanRevealACycle(): void
    {
        $doc = PairsBuilder::build(['a/1.php -> b/1.php', 'b/2.php -> a/2.php']);
        self::assertSame([], (new Analyzer())->analyze($doc)['cycles']);
        $clustered = (new Analyzer())->analyze($doc, Clustering::fromString('folder:1'));
        self::assertSame([['members' => ['a', 'b'], 'size' => 2, 'example' => ['a', 'b', 'a']]], $clustered['cycles']);
    }

    public function testClusterExternalAndUnresolvedAreTheUnionOfItsFiles(): void
    {
        $doc = PairsBuilder::build([
            'a/1.php -> composer:x/y', 'a/2.php -> composer:x/y', 'a/2.php -> composer:z/w',
            'a/1.php -> unresolved:class:Q', 'a/2.php -> unresolved:class:Q',
        ]);
        $unit = (new Analyzer())->analyze($doc, Clustering::fromString('folder:1'))['units'][0];
        self::assertSame(2, $unit['external']);
        self::assertSame(1, $unit['unresolved']);
    }

    public function testNamespaceClusteringFallsBackToFolders(): void
    {
        $doc = PairsBuilder::build(['src/A.php -> bootstrap.php'], modules: ['src/A.php' => 'App\\Domain\\Sub']);
        $analysis = (new Analyzer())->analyze($doc, Clustering::fromString('namespace:2'));
        self::assertSame(['.', 'App\\Domain'], array_column($analysis['units'], 'id'));
    }

    public function testRefusesAnAlreadyClusteredDocument(): void
    {
        ['document' => $clustered] = Clustering::fromString('folder:1')->apply(PairsBuilder::build(['a/1.php -> b/1.php']));
        $this->expectException(\InvalidArgumentException::class);
        $this->expectExceptionMessage('already clustered');
        (new Analyzer())->analyze($clustered);
    }

    public function testTheResultDoesNotDependOnInsertionOrder(): void
    {
        $edges = ['c.php -> a.php', 'a.php -> b.php', 'b.php -> a.php', 'b.php -> composer:x/y', 'd.php -> c.php'];
        $forward = (new Analyzer())->analyze(PairsBuilder::build($edges));
        $backward = (new Analyzer())->analyze(PairsBuilder::build(array_reverse($edges)));
        self::assertSame($forward, $backward);
    }

    /** web/ and cli/ use core/; within core/, Service uses Repo. */
    private static function layered(): PairsDocument
    {
        return PairsBuilder::build([
            'web/Controller.php -> core/Service.php',
            'web/Controller.php -> core/Repo.php',
            'web/View.php -> core/Service.php',
            'cli/Command.php -> core/Service.php',
            'core/Service.php -> core/Repo.php',
        ]);
    }
}
