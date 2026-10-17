<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests;

use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;
use Untangled\Analysis\Analyzer;
use Untangled\Analysis\Clustering;
use Untangled\Analysis\Filter;
use Untangled\Graph\PairsDocument;
use Untangled\Report\Dot;
use Untangled\Report\Report;
use Untangled\Scanner\ScanResult;
use Untangled\Scanner\Scanner;

/**
 * Runs the shared cases in conformance/cases (see conformance/README.md): every case with a
 * php/ folder, scanned with the --source paths in its php/sources file if it has one, must produce its expected pairs, every expected analysis[.<strategy>].json, and
 * every expected graph[.<strategy>].dot byte for byte.
 */
final class ConformanceTest extends TestCase
{
    private const CASES = __DIR__ . '/../../conformance/cases';

    /** @return iterable<string, array{string}> */
    public static function cases(): iterable
    {
        foreach (glob(self::CASES . '/*/php', GLOB_ONLYDIR) ?: [] as $case) {
            yield basename(dirname($case)) => [$case];
        }
    }

    /** @return iterable<string, array{string, string}> */
    public static function analyses(): iterable
    {
        foreach (self::cases() as $name => [$case]) {
            foreach (glob($case . '/expected/analysis*.json') ?: [] as $file) {
                yield $name . ' ' . basename($file) => [$case, $file];
            }
        }
    }

    /** @return iterable<string, array{string, string}> */
    public static function graphs(): iterable
    {
        foreach (self::cases() as $name => [$case]) {
            foreach (glob($case . '/expected/graph*.dot') ?: [] as $file) {
                yield $name . ' ' . basename($file) => [$case, $file];
            }
        }
    }

    public function testThereAreCases(): void
    {
        self::assertGreaterThanOrEqual(7, iterator_count(self::cases()));
    }

    #[DataProvider('cases')]
    public function testPairs(string $case): void
    {
        $actual = self::scan($case)->pairs->toArray();
        self::assertSameDocument(self::read($case . '/expected/pairs.json'), $actual);
    }

    #[DataProvider('cases')]
    public function testEveryCaseHasAnExpectedAnalysis(string $case): void
    {
        self::assertFileExists($case . '/expected/analysis.json');
    }

    #[DataProvider('cases')]
    public function testScanIsDeterministic(string $case): void
    {
        $first = self::scan($case)->pairs->toJson();
        self::assertSame($first, self::scan($case)->pairs->toJson());
    }

    #[DataProvider('cases')]
    public function testExpectedPairsReadBackUnchanged(string $case): void
    {
        $expected = self::read($case . '/expected/pairs.json');
        self::assertSameDocument($expected, PairsDocument::fromArray($expected)->toArray());
    }

    #[DataProvider('analyses')]
    public function testAnalysis(string $case, string $file): void
    {
        $clustering = self::clustering($case, substr(basename($file, '.json'), strlen('analysis')));
        $pairs = self::scan($case)->pairs;
        $actual = (new Analyzer())->analyze((new Filter())->apply($pairs), $clustering);
        self::assertSameDocument(self::read($file), $actual);
    }

    #[DataProvider('graphs')]
    public function testDotGraph(string $case, string $file): void
    {
        $clustering = self::clustering($case, substr(basename($file, '.dot'), strlen('graph')));
        $pairs = self::scan($case)->pairs;
        $actual = Dot::render(Report::build(basename(dirname($case)), (new Filter())->apply($pairs), $clustering));
        self::assertSame(file_get_contents($file), $actual);
    }

    /** Scans a case's project, with the --source paths listed one per line in its optional `sources` file. */
    private static function scan(string $case): ScanResult
    {
        $sources = is_file($case . '/sources') ? (file($case . '/sources', FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: []) : [];
        return (new Scanner(sources: $sources))->scan($case . '/project');
    }

    /** The clustering an expected file's suffix names: '' (none), '.rules', or '.namespace-2' and the like. */
    private static function clustering(string $case, string $suffix): ?Clustering
    {
        return match (true) {
            $suffix === '' => null,
            $suffix === '.rules' => Clustering::parseRules((string) file_get_contents($case . '/clusters.rules')),
            default => Clustering::fromString((string) preg_replace('/-(?=[0-9]+$)/', ':', substr($suffix, 1))),
        };
    }

    /**
     * Equality as the spec defines it for conformance: the generator is ignored and numbers
     * compare to 4 decimal places. Key order matters, as it does in the written documents.
     *
     * @param array<string, mixed> $expected
     * @param array<string, mixed> $actual
     */
    public static function assertSameDocument(array $expected, array $actual): void
    {
        unset($expected['generator'], $actual['generator']);
        self::assertSame(self::normalize($expected), self::normalize($actual));
    }

    private static function normalize(mixed $value): mixed
    {
        if (is_int($value) || is_float($value)) {
            return round((float) $value, 4);
        }
        return is_array($value) ? array_map(self::normalize(...), $value) : $value;
    }

    /** @return array<string, mixed> */
    public static function read(string $file): array
    {
        return json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
    }
}
