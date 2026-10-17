<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests\Analysis;

use PHPUnit\Framework\TestCase;
use Untangled\Analysis\Filter;
use Untangled\Graph\PairsDocument;
use Untangled\Tests\Graph\PairsBuilder;

final class FilterTest extends TestCase
{
    public function testDropsBuiltinsByDefault(): void
    {
        $filtered = (new Filter())->apply(PairsBuilder::build(['a.php -> builtin:Countable', 'a.php -> b.php']));
        self::assertSame(['a.php', 'b.php'], self::ids($filtered));
        self::assertSame(['a.php>b.php'], self::edges($filtered));
    }

    public function testCanKeepBuiltins(): void
    {
        $filtered = (new Filter(keepBuiltins: true))->apply(PairsBuilder::build(['a.php -> builtin:Countable']));
        self::assertSame(['a.php', 'builtin:Countable'], self::ids($filtered));
    }

    public function testKeepsExternalAndUnresolvedTargets(): void
    {
        $filtered = (new Filter())->apply(PairsBuilder::build(['a.php -> composer:x/y', 'a.php -> unresolved:class:Z']));
        self::assertSame(['a.php', 'composer:x/y', 'unresolved:class:Z'], self::ids($filtered));
    }

    public function testExcludeRemovesFilesAndTheirEdgesBothWays(): void
    {
        $filtered = (new Filter())->exclude('tests/**')->apply(PairsBuilder::build([
            'tests/ATest.php -> src/A.php',
            'src/A.php -> tests/Fixture.php',
            'src/A.php -> src/B.php',
        ]));
        self::assertSame(['src/A.php', 'src/B.php'], self::ids($filtered));
        self::assertSame(['src/A.php>src/B.php'], self::edges($filtered));
    }

    public function testTheLastMatchingPatternWins(): void
    {
        $doc = PairsBuilder::build([], isolated: ['tests/ATest.php', 'tests/Keep.php', 'src/A.php']);
        self::assertSame(['src/A.php', 'tests/Keep.php'], self::ids((new Filter())->exclude('tests/**')->include('tests/Keep.php')->apply($doc)));
        self::assertSame(['src/A.php'], self::ids((new Filter())->include('tests/Keep.php')->exclude('tests/**')->apply($doc)));
    }

    public function testAFileMatchingNoPatternIsIncluded(): void
    {
        $doc = PairsBuilder::build([], isolated: ['src/A.php', 'lib/B.php']);
        self::assertSame(['lib/B.php', 'src/A.php'], self::ids((new Filter())->include('src/**')->apply($doc)));
    }

    public function testKeeps(): void
    {
        $filter = (new Filter())->exclude('**/*Test.php')->include('src/Keep*Test.php');
        self::assertTrue($filter->keeps('src/A.php'));
        self::assertFalse($filter->keeps('src/ATest.php'));
        self::assertTrue($filter->keeps('src/KeepMeTest.php'));
    }

    public function testDropsTargetsThatOnlyRemovedFilesUsed(): void
    {
        $filtered = (new Filter())->exclude('legacy/**')->apply(PairsBuilder::build([
            'legacy/Old.php -> composer:old/lib',
            'legacy/Old.php -> unresolved:class:Gone',
            'src/A.php -> composer:new/lib',
        ]));
        self::assertSame(['composer:new/lib', 'src/A.php'], self::ids($filtered));
    }

    public function testKeepsEdgeKindsCountsAndNodeFields(): void
    {
        $doc = new PairsDocument('php');
        $doc->addNode('a.php', PairsDocument::INTERNAL, ['module' => 'App', 'symbols' => ['App\\A']]);
        $doc->addNode('b.php', PairsDocument::INTERNAL);
        $doc->addEdge('a.php', 'b.php', 'new');
        $doc->addEdge('a.php', 'b.php', 'type');
        $filtered = (new Filter())->apply($doc);
        self::assertSame($doc->toArray(), $filtered->toArray());
    }

    public function testClusterNodesPassThrough(): void
    {
        $doc = new PairsDocument('php');
        $doc->addNode('App', PairsDocument::CLUSTER, ['members' => ['a.php']]);
        self::assertTrue((new Filter())->exclude('**')->apply($doc)->hasNode('App'));
    }

    public function testLeavesTheInputUntouched(): void
    {
        $doc = PairsBuilder::build(['a.php -> builtin:Countable']);
        $before = $doc->toArray();
        (new Filter())->exclude('a.php')->apply($doc);
        self::assertSame($before, $doc->toArray());
    }

    /** @return list<string> */
    private static function ids(PairsDocument $doc): array
    {
        return array_column($doc->nodes(), 'id');
    }

    /** @return list<string> */
    private static function edges(PairsDocument $doc): array
    {
        return array_map(static fn (array $e): string => "{$e['from']}>{$e['to']}", $doc->edges());
    }
}
