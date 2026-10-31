<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests\Analysis;

use PHPUnit\Framework\TestCase;
use Untangled\Analysis\Dependents;
use Untangled\Analysis\Filter;
use Untangled\Graph\PairsDocument;
use Untangled\Tests\Graph\PairsBuilder;

final class DependentsTest extends TestCase
{
    /**
     * web/Controller -> core/Service -> core/Repo, web/View -> core/Service, and a cycle
     * core/Repo <-> core/Cache. Controller also uses composer:acme/lib.
     */
    private static function graph(): PairsDocument
    {
        $document = new PairsDocument('php');
        foreach (['web/Controller.php' => 'Web\\Controller', 'web/View.php' => 'Web\\View', 'core/Service.php' => 'Core\\Service', 'core/Repo.php' => 'Core\\Repo', 'core/Cache.php' => 'Core\\Cache'] as $id => $symbol) {
            $document->addNode($id, PairsDocument::INTERNAL, ['symbols' => [$symbol]]);
        }
        $document->addNode('composer:acme/lib', PairsDocument::EXTERNAL);
        foreach ([
            ['web/Controller.php', 'core/Service.php'],
            ['web/View.php', 'core/Service.php'],
            ['core/Service.php', 'core/Repo.php'],
            ['core/Repo.php', 'core/Cache.php'],
            ['core/Cache.php', 'core/Repo.php'],
            ['web/Controller.php', 'composer:acme/lib'],
        ] as [$from, $to]) {
            $document->addEdge($from, $to, 'new');
        }
        return $document;
    }

    /** @param array<string, mixed> $document @return array<string, int> */
    private static function depths(array $document): array
    {
        return array_column($document['dependents'], 'depth', 'id');
    }

    public function testDirectDependentsByDefault(): void
    {
        $document = (new Dependents())->find(self::graph(), ['core/Service.php'], false);
        self::assertSame(['web/Controller.php' => 1, 'web/View.php' => 1], self::depths($document));
        self::assertFalse($document['transitive']);
    }

    public function testTransitiveDependentsCarryTheirShortestDepth(): void
    {
        $document = (new Dependents())->find(self::graph(), ['core/Cache.php'], true);
        self::assertSame(
            ['core/Repo.php' => 1, 'core/Service.php' => 2, 'web/Controller.php' => 3, 'web/View.php' => 3],
            self::depths($document),
        );
    }

    public function testDependentsAreSortedByDepthThenId(): void
    {
        $document = (new Dependents())->find(self::graph(), ['core/Cache.php'], true);
        self::assertSame(['core/Repo.php', 'core/Service.php', 'web/Controller.php', 'web/View.php'], array_column($document['dependents'], 'id'));
    }

    public function testATargetInACycleIsNotItsOwnDependent(): void
    {
        $document = (new Dependents())->find(self::graph(), ['core/Repo.php'], true);
        self::assertArrayNotHasKey('core/Repo.php', self::depths($document));
        self::assertSame(1, self::depths($document)['core/Cache.php']);
    }

    public function testASymbolNamesTheFileThatDeclaresIt(): void
    {
        $document = (new Dependents())->find(self::graph(), ['Core\\Service'], false);
        self::assertSame([['target' => 'Core\\Service', 'nodes' => ['core/Service.php']]], $document['targets']);
        self::assertSame(['web/Controller.php', 'web/View.php'], array_column($document['dependents'], 'id'));
    }

    public function testAnExternalPackageCanBeATarget(): void
    {
        $document = (new Dependents())->find(self::graph(), ['composer:acme/lib'], true);
        self::assertSame(['web/Controller.php' => 1], self::depths($document));
    }

    public function testSeveralTargetsAreOneQueryAtTheShortestDistance(): void
    {
        $document = (new Dependents())->find(self::graph(), ['core/Repo.php', 'core/Service.php'], true);
        // Service is a target, so it is not listed even though it depends on Repo.
        self::assertSame(['core/Cache.php' => 1, 'web/Controller.php' => 1, 'web/View.php' => 1], self::depths($document));
        self::assertSame(['core/Repo.php'], $document['targets'][0]['nodes']);
    }

    public function testASymbolDeclaredInSeveralFilesMatchesAllOfThem(): void
    {
        $document = new PairsDocument('php');
        $document->addNode('a.php', PairsDocument::INTERNAL, ['symbols' => ['Polyfill']]);
        $document->addNode('b.php', PairsDocument::INTERNAL, ['symbols' => ['Polyfill']]);
        $document->addNode('user.php', PairsDocument::INTERNAL);
        $document->addEdge('user.php', 'b.php', 'new');
        $found = (new Dependents())->find($document, ['Polyfill'], false);
        self::assertSame(['a.php', 'b.php'], $found['targets'][0]['nodes']);
        self::assertSame(['user.php' => 1], self::depths($found));
    }

    public function testTheFilterHidesDependentsButTheWalkGoesThroughThem(): void
    {
        $filter = (new Filter())->exclude('**')->include('web/**');
        $document = (new Dependents())->find(self::graph(), ['core/Cache.php'], true, $filter);
        self::assertSame(['web/Controller.php' => 3, 'web/View.php' => 3], self::depths($document));
    }

    public function testNothingDependsOnATopLevelFile(): void
    {
        $document = (new Dependents())->find(self::graph(), ['web/Controller.php'], true);
        self::assertSame([], $document['dependents']);
        self::assertSame("No dependents of web/Controller.php\n", Dependents::renderText($document));
    }

    public function testAnUnknownTargetIsAnError(): void
    {
        $this->expectException(\InvalidArgumentException::class);
        $this->expectExceptionMessage('no node or symbol "Nope" in the pairs document');
        (new Dependents())->find(self::graph(), ['core/Service.php', 'Nope'], false);
    }

    public function testAClusteredDocumentIsRefused(): void
    {
        $document = new PairsDocument('php');
        $document->addNode('Core', PairsDocument::CLUSTER, ['members' => ['a.php']]);
        $this->expectException(\InvalidArgumentException::class);
        $this->expectExceptionMessage('already clustered');
        (new Dependents())->find($document, ['Core'], false);
    }

    public function testTextGroupsDependentsByFolder(): void
    {
        $document = (new Dependents())->find(self::graph(), ['core/Service.php', 'Core\\Repo'], false);
        self::assertSame("3 dependents of core/Service.php, Core\\Repo\n\ncore/\n  Cache.php\n\nweb/\n  Controller.php\n  View.php\n", Dependents::renderText($document));
    }

    public function testTextShowsTheDepthWhenTransitiveAndRootFilesGoFirst(): void
    {
        $document = PairsBuilder::build(['index.php -> lib/a.php', 'lib/b.php -> lib/a.php']);
        $text = Dependents::renderText((new Dependents())->find($document, ['lib/a.php'], true));
        self::assertSame("2 dependents of lib/a.php\n\n./\n  index.php  (depth 1)\n\nlib/\n  b.php  (depth 1)\n", $text);
    }

    public function testTextCountsOneDependentInTheSingular(): void
    {
        $document = PairsBuilder::build(['a.php -> b.php']);
        self::assertStringStartsWith("1 dependent of b.php\n", Dependents::renderText((new Dependents())->find($document, ['b.php'], false)));
    }

    public function testIdsAreSortedByByteValueEvenWhenTheyLookNumeric(): void
    {
        $document = new PairsDocument('php');
        foreach (['t', '9', '10', '1e1', '2'] as $id) {
            $document->addNode($id, PairsDocument::INTERNAL);
        }
        foreach (['9', '10', '1e1', '2'] as $from) {
            $document->addEdge($from, 't', 'use');
        }
        $result = (new Dependents())->find($document, ['t'], false);
        self::assertSame(['10', '1e1', '2', '9'], array_column($result['dependents'], 'id'));
        self::assertSame("4 dependents of t\n\n./\n  10\n  1e1\n  2\n  9\n", Dependents::renderText($result));
    }

    public function testOnlyInternalNodesAnswerToASymbol(): void
    {
        $document = new PairsDocument('php');
        $document->addNode('a.php', PairsDocument::INTERNAL, ['symbols' => ['App\\A']]);
        $document->addNode('composer:x/y', PairsDocument::EXTERNAL, ['symbols' => ['Vendor\\Y']]);
        $document->addEdge('a.php', 'composer:x/y', 'use');
        $this->expectException(\InvalidArgumentException::class);
        $this->expectExceptionMessage('no node or symbol "Vendor\\Y"');
        (new Dependents())->find($document, ['Vendor\\Y'], false);
    }

    /** @param array<string, mixed> $document @return list<string> */
    private static function ids(array $document): array
    {
        return array_column($document['dependents'], 'id');
    }

    public function testMaxDepthStopsTheWalk(): void
    {
        $find = static fn (int $depth): array => self::depths((new Dependents())->find(self::graph(), ['core/Cache.php'], true, maxDepth: $depth));
        self::assertSame(['core/Repo.php' => 1], $find(1));
        self::assertSame(['core/Repo.php' => 1, 'core/Service.php' => 2], $find(2));
        self::assertSame(['core/Repo.php' => 1, 'core/Service.php' => 2, 'web/Controller.php' => 3, 'web/View.php' => 3], $find(3));
        self::assertSame($find(3), $find(1000));
    }

    public function testMaxDepthOfOneIsTheDirectDependents(): void
    {
        $direct = (new Dependents())->find(self::graph(), ['core/Service.php'], false);
        $limited = (new Dependents())->find(self::graph(), ['core/Service.php'], true, maxDepth: 1);
        self::assertSame($direct['dependents'], $limited['dependents']);
        self::assertTrue($limited['transitive']);
    }

    public function testMaxDepthBelowOneIsRefused(): void
    {
        $this->expectException(\InvalidArgumentException::class);
        (new Dependents())->find(self::graph(), ['core/Service.php'], true, maxDepth: 0);
    }

    public function testThroughOnlyGoesIntoMatchingFiles(): void
    {
        $find = static fn (array $through, array $targets = ['core/Cache.php']): array => self::depths((new Dependents())->find(self::graph(), $targets, true, through: $through));
        self::assertSame(['core/Repo.php' => 1, 'core/Service.php' => 2], $find(['core/**']));
        // Repo is not eligible, so nothing is found by way of it, even the web files that use Service.
        self::assertSame([], $find(['web/**']));
        // The patterns are alternatives.
        self::assertSame(['core/Repo.php' => 1, 'core/Service.php' => 2, 'web/Controller.php' => 3, 'web/View.php' => 3], $find(['core/**', 'web/**']));
        // The target is the start of the walk whatever it matches: Cache is not under web/.
        self::assertSame(['core/Repo.php' => 1], $find(['core/Repo.php']));
    }

    public function testThroughFindsTheShortestPathThroughEligibleFilesOnly(): void
    {
        $document = new PairsDocument('php');
        foreach (['t.php', 'a.php', 'm.php', 'c.php', 'x.php'] as $id) {
            $document->addNode($id, PairsDocument::INTERNAL);
        }
        // c is two steps from t by way of x, but x is not eligible: by way of m and a it is three.
        foreach ([['x.php', 't.php'], ['c.php', 'x.php'], ['a.php', 't.php'], ['m.php', 'a.php'], ['c.php', 'm.php']] as [$from, $to]) {
            $document->addEdge($from, $to, 'use');
        }
        self::assertSame(
            ['a.php' => 1, 'm.php' => 2, 'c.php' => 3],
            self::depths((new Dependents())->find($document, ['t.php'], true, through: ['a.php', 'm.php', 'c.php'])),
        );
        self::assertSame(
            ['a.php' => 1, 'x.php' => 1, 'c.php' => 2, 'm.php' => 2],
            self::depths((new Dependents())->find($document, ['t.php'], true)),
        );
    }

    public function testThroughAppliesToDirectDependentsToo(): void
    {
        $document = (new Dependents())->find(self::graph(), ['core/Service.php'], false, through: ['web/Controller.php']);
        self::assertSame(['web/Controller.php'], self::ids($document));
    }

    public function testThroughCombinesWithMaxDepthAndTheOutputFilter(): void
    {
        $find = static fn (?Filter $filter, ?int $maxDepth = null): array => self::depths(
            (new Dependents())->find(self::graph(), ['core/Cache.php'], true, $filter, ['core/**', 'web/**'], $maxDepth),
        );
        self::assertSame(['core/Repo.php' => 1, 'core/Service.php' => 2], $find(null, 2));
        // --exclude hides Service from the list but the walk still goes through it.
        self::assertSame(['core/Repo.php' => 1, 'web/Controller.php' => 3, 'web/View.php' => 3], $find((new Filter())->exclude('core/Service.php')));
        // --include cannot bring back a file --through left out.
        self::assertSame([], self::depths((new Dependents())->find(self::graph(), ['core/Cache.php'], true, (new Filter())->include('**'), ['web/**'])));
    }

    public function testThroughWithTwoTargetsAndACycleListsEachFileOnce(): void
    {
        $document = (new Dependents())->find(self::graph(), ['core/Repo.php', 'core/Cache.php'], true, through: ['core/**', 'web/**']);
        self::assertSame(['core/Service.php' => 1, 'web/Controller.php' => 2, 'web/View.php' => 2], self::depths($document));
    }

    public function testATargetWithALeadingBackslashFindsTheSymbol(): void
    {
        foreach (['\\Core\\Service', '\\\\Core\\Service'] as $target) {
            $document = (new Dependents())->find(self::graph(), [$target], false);
            self::assertSame($target, $document['targets'][0]['target']);
            self::assertSame(['core/Service.php'], $document['targets'][0]['nodes']);
        }
    }

    public function testPathsAreRespelledToProjectIds(): void
    {
        $find = static fn (string $target, ?string $root = '/work/app'): array => (new Dependents())->find(self::graph(), [$target], false, root: $root)['targets'][0]['nodes'];
        foreach (['core/Service.php', './core/Service.php', 'core\\Service.php', 'core//x/../Service.php', '/work/app/core/Service.php', '/work/app/./core/../core/Service.php', 'C:\\work\\app\\core\\Service.php'] as $target) {
            self::assertSame(['core/Service.php'], $find($target, $target[0] === 'C' ? 'c:/work/app' : '/work/app'), $target);
        }
    }

    public function testAnAbsolutePathOutsideTheProjectIsRefused(): void
    {
        foreach (['/work/other/core/Service.php', '/work/application/core/Service.php', '/work/app/../app2/x.php', 'D:\\work\\app\\core\\Service.php'] as $target) {
            try {
                (new Dependents())->find(self::graph(), [$target], false, root: '/work/app');
                self::fail("accepted {$target}");
            } catch (\InvalidArgumentException $e) {
                self::assertStringContainsString('is outside the project folder /work/app', $e->getMessage(), $target);
            }
        }
    }

    public function testAnAbsolutePathMatchesNothingWithoutAProjectFolder(): void
    {
        $this->expectException(\InvalidArgumentException::class);
        $this->expectExceptionMessage('no node or symbol "/work/app/core/Service.php"');
        (new Dependents())->find(self::graph(), ['/work/app/core/Service.php'], false);
    }

    public function testAnAsWrittenMatchStillWinsOverARespelling(): void
    {
        $document = new PairsDocument('php');
        $document->addNode('a/b.php', PairsDocument::INTERNAL);
        $document->addNode('./a/b.php', PairsDocument::INTERNAL);
        $document->addEdge('./a/b.php', 'a/b.php', 'use');
        $result = (new Dependents())->find($document, ['./a/b.php'], false);
        self::assertSame(['./a/b.php'], $result['targets'][0]['nodes']);
    }
}
