<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests\Analysis;

use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;
use Untangled\Analysis\Clustering;
use Untangled\Graph\PairsDocument;
use Untangled\Tests\Graph\PairsBuilder;

final class ClusteringTest extends TestCase
{
    /** @return iterable<string, array{string, string, ?string, string}> */
    public static function clusterIds(): iterable
    {
        yield 'namespace:2' => ['namespace:2', 'src/Billing/Tax.php', 'App\\Billing\\Tax', 'App\\Billing'];
        yield 'namespace:1' => ['namespace:1', 'src/Billing/Tax.php', 'App\\Billing', 'App'];
        yield 'namespace:N keeps a shorter namespace whole' => ['namespace:3', 'src/Tax.php', 'App', 'App'];
        yield 'namespace:N splits Python modules on dots' => ['namespace:2', 'src/shop/billing/tax.py', 'shop.billing.tax', 'shop.billing'];
        yield 'namespace:N keeps a shorter Python module whole' => ['namespace:2', 'manage.py', 'manage', 'manage'];
        yield 'namespace:N falls back to folder:N without a module' => ['namespace:2', 'lib/a/b/x.php', null, 'lib/a'];
        yield 'namespace:N falls back for an empty module' => ['namespace:2', 'lib/a/b/x.php', '', 'lib/a'];
        yield 'namespace:N fallback puts root files in "."' => ['namespace:2', 'index.php', null, '.'];
        yield 'folder:1' => ['folder:1', 'src/Billing/Tax.php', 'App\\Billing', 'src'];
        yield 'folder:2' => ['folder:2', 'src/Billing/Tax.php', null, 'src/Billing'];
        yield 'folder:N keeps a shorter directory path' => ['folder:3', 'src/x.php', null, 'src'];
        yield 'folder:N puts root files in "."' => ['folder:1', 'index.php', null, '.'];
        yield 'folder:N ignores the module' => ['folder:1', 'lib/x.php', 'App\\X', 'lib'];
    }

    #[DataProvider('clusterIds')]
    public function testClusterOf(string $strategy, string $id, ?string $module, string $expected): void
    {
        $node = ['id' => $id, 'kind' => 'internal'] + ($module === null ? [] : ['module' => $module]);
        self::assertSame($expected, Clustering::fromString($strategy)->clusterOf($node));
    }

    public function testNames(): void
    {
        self::assertSame('namespace:2', Clustering::fromString('namespace:2')->name());
        self::assertSame('folder:10', Clustering::byFolder(10)->name());
        self::assertSame('rules', Clustering::parseRules('src/ Core')->name());
    }

    /** @return iterable<array{string}> */
    public static function invalidStrategies(): iterable
    {
        foreach (['namespace', 'namespace:0', 'namespace:-1', 'namespace:01', 'files:2', 'folder:x', 'folder:2 ', 'Folder:2', 'rules', ''] as $bad) {
            yield $bad => [$bad];
        }
    }

    #[DataProvider('invalidStrategies')]
    public function testRejectsUnknownStrategies(string $strategy): void
    {
        $this->expectException(\InvalidArgumentException::class);
        Clustering::fromString($strategy);
    }

    public function testRejectsDepthZero(): void
    {
        $this->expectException(\InvalidArgumentException::class);
        Clustering::byNamespace(0);
    }

    public function testRulesFirstMatchingPrefixWins(): void
    {
        $rules = Clustering::parseRules("src/Billing/ Billing\nsrc/Invoice Billing\nsrc/ Core\n");
        self::assertSame('Billing', self::of($rules, 'src/Billing/Tax.php'));
        self::assertSame('Billing', self::of($rules, 'src/InvoiceLine.php'));
        self::assertSame('Core', self::of($rules, 'src/Clock.php'));
        self::assertSame('index.php', self::of($rules, 'index.php'));
    }

    public function testUnmatchedListsNodesNoRuleMatchesSorted(): void
    {
        $files = PairsBuilder::build(['src/Billing/a.php -> src/NewFolder/z.php', 'src/NewFolder/b.php -> src/Billing/a.php', 'lib/c.php -> lib/c.php']);
        $rules = Clustering::parseRules("src/Billing/ Billing\nlib/ Lib\n");
        self::assertSame(['src/NewFolder/b.php', 'src/NewFolder/z.php'], $rules->unmatched($files));
    }

    public function testNothingIsUnmatchedWhenEveryNodeHasARule(): void
    {
        $files = PairsBuilder::build(['src/a.php -> lib/b.php']);
        self::assertSame([], Clustering::parseRules("src/ Core\nlib/ Lib\n")->unmatched($files));
    }

    public function testNothingIsUnmatchedWithoutRulesStrategy(): void
    {
        $files = PairsBuilder::build(['src/a.php -> lib/b.php']);
        self::assertSame([], Clustering::byFolder(1)->unmatched($files));
        self::assertSame([], Clustering::byNamespace(1)->unmatched($files));
    }

    public function testNonInternalNodesAreNeverUnmatched(): void
    {
        $files = PairsBuilder::build(['src/a.php -> composer:acme/lib']);
        self::assertSame([], Clustering::parseRules("src/ Core\n")->unmatched($files));
    }

    public function testDescribeUnmatched(): void
    {
        self::assertSame('rules: 1 file matches no rule and becomes its own cluster: a.php', Clustering::describeUnmatched(['a.php']));
        self::assertSame('rules: 2 files match no rule and each becomes its own cluster: a.php, b.php', Clustering::describeUnmatched(['a.php', 'b.php']));
        self::assertSame(
            'rules: 7 files match no rule and each becomes its own cluster: a, b, c, d, e and 2 more',
            Clustering::describeUnmatched(['a', 'b', 'c', 'd', 'e', 'f', 'g']),
        );
    }

    public function testRulesOrderMatters(): void
    {
        $rules = Clustering::parseRules("src/ Core\nsrc/Billing/ Billing\n");
        self::assertSame('Core', self::of($rules, 'src/Billing/Tax.php'));
    }

    public function testRulesFileSyntax(): void
    {
        $rules = Clustering::parseRules("# header\r\n\r\n   src/Billing/\t\tBilling   # trailing comment\r\n#src/ Ignored\nsrc/ Core");
        self::assertSame('Billing', self::of($rules, 'src/Billing/Tax.php'));
        self::assertSame('Core', self::of($rules, 'src/x.php'));
    }

    public function testAnEmptyRulesFileKeepsEveryFileAlone(): void
    {
        self::assertSame('src/x.php', self::of(Clustering::parseRules("# nothing\n"), 'src/x.php'));
    }

    /** @return iterable<string, array{string}> */
    public static function malformedRules(): iterable
    {
        yield 'three fields' => ["src/ Core extra\n"];
        yield 'one field' => ["src/\n"];
        yield 'error on a later line' => ["src/ Core\nlib/\n"];
    }

    #[DataProvider('malformedRules')]
    public function testRejectsMalformedRules(string $rules): void
    {
        $this->expectException(\InvalidArgumentException::class);
        $this->expectExceptionMessage('must be "<prefix> <cluster>"');
        Clustering::parseRules($rules);
    }

    public function testTheRuleErrorNamesTheLine(): void
    {
        $this->expectExceptionMessage('rules line 3');
        Clustering::parseRules("# comment\nsrc/ Core\nlib/\n");
    }

    public function testApplyMergesEdgesPerClusterAndTarget(): void
    {
        $doc = PairsBuilder::build([
            'a/1.php -> a/2.php',
            'a/1.php -> b/1.php',
            'a/2.php -> b/1.php',
            'a/2.php -> b/2.php',
            'a/1.php -> composer:x/y',
            'a/2.php -> composer:x/y',
            'b/1.php -> unresolved:class:Z',
        ]);
        ['document' => $clustered, 'clusterOf' => $clusterOf, 'dropped' => $dropped] = Clustering::fromString('folder:1')->apply($doc);
        self::assertSame([
            ['from' => 'a', 'to' => 'b', 'kinds' => ['new'], 'count' => 3],
            ['from' => 'a', 'to' => 'composer:x/y', 'kinds' => ['new'], 'count' => 2],
            ['from' => 'b', 'to' => 'unresolved:class:Z', 'kinds' => ['new'], 'count' => 1],
        ], $clustered->edges());
        self::assertSame(['a/1.php' => 'a', 'a/2.php' => 'a', 'b/1.php' => 'b', 'b/2.php' => 'b'], $clusterOf);
        self::assertSame(['a' => 1], $dropped);
    }

    public function testApplyMakesClusterNodesAndPassesOthersThrough(): void
    {
        $doc = PairsBuilder::build(['a/2.php -> composer:x/y', 'a/1.php -> builtin:Countable'], isolated: ['c.php']);
        ['document' => $clustered] = Clustering::fromString('folder:1')->apply($doc);
        self::assertSame([
            ['id' => '.', 'kind' => 'cluster', 'members' => ['c.php']],
            ['id' => 'a', 'kind' => 'cluster', 'members' => ['a/1.php', 'a/2.php']],
            ['id' => 'builtin:Countable', 'kind' => 'builtin'],
            ['id' => 'composer:x/y', 'kind' => 'external'],
        ], $clustered->nodes());
    }

    public function testApplyUnionsKinds(): void
    {
        $doc = new PairsDocument('php');
        foreach (['a/1.php', 'a/2.php', 'b/1.php'] as $id) {
            $doc->addNode($id, PairsDocument::INTERNAL);
        }
        $doc->addEdge('a/1.php', 'b/1.php', 'new');
        $doc->addEdge('a/2.php', 'b/1.php', 'static');
        $doc->addEdge('a/2.php', 'b/1.php', 'new');
        ['document' => $clustered] = Clustering::fromString('folder:1')->apply($doc);
        self::assertSame([['from' => 'a', 'to' => 'b', 'kinds' => ['new', 'static'], 'count' => 3]], $clustered->edges());
    }

    public function testNumericLookingClusterIdsStayStrings(): void
    {
        $rules = Clustering::parseRules("src/ 1\nlib/ 2\n");
        ['document' => $clustered, 'clusterOf' => $clusterOf] = $rules->apply(PairsBuilder::build(['src/a.php -> lib/b.php']));
        self::assertSame(['1', '2'], array_column($clustered->nodes(), 'id'));
        self::assertSame('1', $clustered->edges()[0]['from']);
        self::assertSame(['lib/b.php' => '2', 'src/a.php' => '1'], $clusterOf);
    }

    private static function of(Clustering $clustering, string $id): string
    {
        return $clustering->clusterOf(['id' => $id, 'kind' => 'internal']);
    }
}
