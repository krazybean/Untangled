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
}
