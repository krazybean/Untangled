<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests\Graph;

use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;
use Untangled\Graph\DocumentException;
use Untangled\Graph\PairsDocument;
use Untangled\Version;

final class PairsDocumentTest extends TestCase
{
    public function testEdgesMergeKindsAndCounts(): void
    {
        $doc = self::abc();
        $doc->addEdge('a.php', 'b.php', 'new');
        $doc->addEdge('a.php', 'b.php', 'import');
        $doc->addEdge('a.php', 'b.php', 'new');
        self::assertSame([['from' => 'a.php', 'to' => 'b.php', 'kinds' => ['import', 'new'], 'count' => 3]], $doc->edges());
    }

    public function testSelfEdgesAreDropped(): void
    {
        $doc = self::abc();
        $doc->addEdge('a.php', 'a.php', 'static');
        $doc->mergeEdge('b.php', 'b.php', ['type'], 4);
        self::assertSame([], $doc->edges());
    }

    public function testMergeEdgeAddsCounts(): void
    {
        $doc = self::abc();
        $doc->mergeEdge('a.php', 'b.php', ['type', 'new'], 2);
        $doc->mergeEdge('a.php', 'b.php', ['new'], 3);
        self::assertSame([['from' => 'a.php', 'to' => 'b.php', 'kinds' => ['new', 'type'], 'count' => 5]], $doc->edges());
    }

    public function testNodesAndEdgesSortInByteOrder(): void
    {
        $doc = new PairsDocument('php');
        foreach (['b.php', 'B.php', 'a.php', '_.php'] as $id) {
            $doc->addNode($id, PairsDocument::INTERNAL);
        }
        $doc->addEdge('b.php', 'a.php', 'new');
        $doc->addEdge('B.php', 'b.php', 'new');
        $doc->addEdge('a.php', '_.php', 'new');
        $doc->addEdge('B.php', 'a.php', 'new');
        // Uppercase sorts before underscore, which sorts before lowercase.
        self::assertSame(['B.php', '_.php', 'a.php', 'b.php'], array_column($doc->nodes(), 'id'));
        self::assertSame(
            ['B.php>a.php', 'B.php>b.php', 'a.php>_.php', 'b.php>a.php'],
            array_map(static fn (array $e): string => "{$e['from']}>{$e['to']}", $doc->edges()),
        );
    }

    public function testAddNodeKeepsTheFirstDefinition(): void
    {
        $doc = new PairsDocument('php');
        $doc->addNode('a.php', PairsDocument::INTERNAL, ['module' => 'A']);
        $doc->addNode('a.php', PairsDocument::EXTERNAL);
        self::assertSame(['id' => 'a.php', 'kind' => 'internal', 'module' => 'A'], $doc->node('a.php'));
        self::assertNull($doc->node('missing.php'));
    }

    public function testToArrayCarriesTheHeader(): void
    {
        $array = (new PairsDocument('php'))->toArray();
        self::assertSame('untangled-pairs', $array['format']);
        self::assertSame(Version::SPEC, $array['version']);
        self::assertSame('php', $array['language']);
        self::assertSame(['name' => Version::NAME, 'version' => Version::VERSION], $array['generator']);
    }

    public function testJsonUsesTwoSpacesAndATrailingNewline(): void
    {
        $json = self::abc()->toJson();
        self::assertStringStartsWith("{\n  \"format\": \"untangled-pairs\",\n", $json);
        self::assertStringContainsString("\n    {\n      \"id\": \"a.php\",", $json);
        self::assertStringEndsWith("}\n", $json);
    }

    public function testJsonDoesNotEscapeSlashesOrUnicode(): void
    {
        $doc = new PairsDocument('php');
        $doc->addNode('src/Café.php', PairsDocument::INTERNAL, ['module' => 'App\\Café']);
        $json = $doc->toJson();
        self::assertStringContainsString('"src/Café.php"', $json);
        self::assertStringContainsString('"App\\\\Café"', $json);
    }

    public function testSnakefoodWritesOnlyInternalEdgesAndLonelyFiles(): void
    {
        $doc = self::abc();
        $doc->addNode('composer:x/y', PairsDocument::EXTERNAL);
        $doc->addEdge('a.php', 'b.php', 'new');
        $doc->addEdge('b.php', 'composer:x/y', 'import');
        self::assertSame(implode("\n", [
            "(('/r', 'a.php'), ('/r', 'b.php'))",
            "(('/r', 'b.php'), (None, None))",
            "(('/r', 'c.php'), (None, None))",
        ]) . "\n", $doc->toSnakefood('/r'));
    }

    public function testSnakefoodQuotesAndTreatsClustersAsUnits(): void
    {
        $doc = new PairsDocument('php');
        $doc->addNode("it's", PairsDocument::CLUSTER, ['members' => []]);
        $doc->addNode('A\\B', PairsDocument::CLUSTER, ['members' => []]);
        $doc->addEdge("it's", 'A\\B', 'new');
        self::assertSame(
            "(('/r', 'A\\\\B'), (None, None))\n(('/r', 'it\\'s'), ('/r', 'A\\\\B'))\n",
            $doc->toSnakefood('/r'),
        );
    }

    public function testSnakefoodOfAnEmptyDocumentIsEmpty(): void
    {
        self::assertSame('', (new PairsDocument('php'))->toSnakefood('.'));
    }

    public function testFromArrayRoundTrips(): void
    {
        $doc = self::abc();
        $doc->addNode('unresolved:class:X', PairsDocument::UNRESOLVED);
        $doc->addEdge('a.php', 'b.php', 'new');
        $doc->addEdge('a.php', 'b.php', 'type');
        $doc->addEdge('c.php', 'unresolved:class:X', 'static');
        self::assertSame($doc->toArray(), PairsDocument::fromArray($doc->toArray())->toArray());
    }

    public function testFromArrayDefaultsAMissingCountToOne(): void
    {
        $doc = PairsDocument::fromArray([
            'nodes' => [['id' => 'a.php', 'kind' => 'internal'], ['id' => 'b.php', 'kind' => 'internal']],
            'edges' => [['from' => 'a.php', 'to' => 'b.php', 'kinds' => ['new']]],
        ] + self::minimal());
        self::assertSame(1, $doc->edges()[0]['count']);
    }

    public function testFromArrayWarnsOnAnUnknownMinorVersion(): void
    {
        $warnings = [];
        PairsDocument::fromArray(['version' => '0.99'] + self::minimal(), $warnings);
        self::assertCount(1, $warnings);
        self::assertStringContainsString('0.99', $warnings[0]);

        $warnings = [];
        PairsDocument::fromArray(self::minimal(), $warnings);
        self::assertSame([], $warnings);
    }

    /** @return iterable<string, array{array<string, mixed>, string}> */
    public static function invalidDocuments(): iterable
    {
        $base = self::minimal();
        yield 'another format' => [['format' => 'untangled-analysis'] + $base, 'not an Untangled pairs document'];
        yield 'no format' => [array_diff_key($base, ['format' => true]), 'not an Untangled pairs document'];
        yield 'unknown major version' => [['version' => '1.0'] + $base, 'unsupported pairs document version'];
        yield 'version not a string' => [['version' => 0.1] + $base, 'unsupported pairs document version'];
        yield 'no nodes' => [array_diff_key($base, ['nodes' => true]), 'needs "language", "nodes" and "edges"'];
        yield 'no language' => [array_diff_key($base, ['language' => true]), 'needs "language", "nodes" and "edges"'];
        yield 'node without kind' => [['nodes' => [['id' => 'a.php']]] + $base, 'every node needs'];
        yield 'node not an object' => [['nodes' => ['a.php']] + $base, 'every node needs'];
        yield 'edge without to' => [['nodes' => [['id' => 'a.php', 'kind' => 'internal']], 'edges' => [['from' => 'a.php']]] + $base, 'every edge needs'];
        yield 'edge to a missing node' => [['nodes' => [['id' => 'a.php', 'kind' => 'internal']], 'edges' => [['from' => 'a.php', 'to' => 'b.php']]] + $base, 'not in the document'];
    }

    /** @param array<string, mixed> $data */
    #[DataProvider('invalidDocuments')]
    public function testFromArrayRejects(array $data, string $message): void
    {
        $this->expectException(DocumentException::class);
        $this->expectExceptionMessage($message);
        PairsDocument::fromArray($data);
    }

    /** @return array<string, mixed> */
    private static function minimal(): array
    {
        return ['format' => 'untangled-pairs', 'version' => Version::SPEC, 'language' => 'php', 'nodes' => [], 'edges' => []];
    }

    private static function abc(): PairsDocument
    {
        $doc = new PairsDocument('php');
        foreach (['c.php', 'a.php', 'b.php'] as $id) {
            $doc->addNode($id, PairsDocument::INTERNAL);
        }
        return $doc;
    }

    public function testNamesThatAreNotUtf8AreStoredAsUtf8(): void
    {
        $doc = new PairsDocument('php');
        $doc->addNode("src/Caf\xe9.php", PairsDocument::INTERNAL, ['module' => "App\\Caf\xe9", 'symbols' => ["App\\Caf\xe9"]]);
        $doc->addEdge("src/Caf\xe9.php", "unresolved:class:Cr\xe8me", 'new');
        self::assertTrue($doc->hasNode("src/Caf\xe9.php"));
        self::assertTrue($doc->hasNode('src/Café.php'));
        self::assertSame(['id' => 'src/Café.php', 'kind' => 'internal', 'module' => 'App\\Café', 'symbols' => ['App\\Café']], $doc->node("src/Caf\xe9.php"));
        self::assertSame([['from' => 'src/Café.php', 'to' => 'unresolved:class:Crème', 'kinds' => ['new'], 'count' => 1]], $doc->edges());
        self::assertJson($doc->toJson());
    }
}
