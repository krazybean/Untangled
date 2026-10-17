<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Tests\Analysis;

use PHPUnit\Framework\TestCase;
use Untangled\Analysis\Cycles;

final class CyclesTest extends TestCase
{
    public function testNoUnitsNoCycles(): void
    {
        self::assertSame([], Cycles::find([]));
    }

    public function testAnAcyclicGraphHasNoCycles(): void
    {
        self::assertSame([], Cycles::find(['a' => ['b', 'c'], 'b' => ['c'], 'c' => [], 'd' => ['a']]));
    }

    public function testATwoUnitLoop(): void
    {
        self::assertSame([['members' => ['a', 'b'], 'size' => 2, 'example' => ['a', 'b', 'a']]], Cycles::find(['b' => ['a'], 'a' => ['b']]));
    }

    public function testSortsBySizeThenFirstMember(): void
    {
        $cycles = Cycles::find([
            'e' => ['d'], 'd' => ['e'],
            'a' => ['c', 'b'], 'b' => ['c'], 'c' => ['a'],
            'x' => ['y'], 'y' => [],
            'p' => ['q'], 'q' => ['p'],
        ]);
        self::assertSame([['a', 'b', 'c'], ['d', 'e'], ['p', 'q']], array_column($cycles, 'members'));
        self::assertSame([3, 2, 2], array_column($cycles, 'size'));
    }

    public function testFirstMemberComparesInByteOrder(): void
    {
        // Numeric-looking ids must not compare as numbers: "10" sorts before "9".
        $cycles = Cycles::find(['9' => ['9b'], '9b' => ['9'], '10' => ['10b'], '10b' => ['10']]);
        self::assertSame([['10', '10b'], ['9', '9b']], array_column($cycles, 'members'));
    }

    public function testMembersSortInByteOrder(): void
    {
        $cycles = Cycles::find(['b' => ['B'], 'B' => ['_'], '_' => ['b']]);
        self::assertSame(['B', '_', 'b'], $cycles[0]['members']);
        self::assertSame(['B', '_', 'b', 'B'], $cycles[0]['example']);
    }

    public function testTheExampleIsTheShortestLoopFromTheSmallestMember(): void
    {
        // a -> b -> c -> d -> a is the long way round; a -> e -> a is shorter.
        $cycles = Cycles::find(['a' => ['b', 'e'], 'b' => ['c'], 'c' => ['d'], 'd' => ['a'], 'e' => ['a']]);
        self::assertSame(['a', 'e', 'a'], $cycles[0]['example']);
        self::assertSame(5, $cycles[0]['size']);
    }

    public function testExampleTiesBreakInByteOrder(): void
    {
        $cycles = Cycles::find(['a' => ['c', 'b'], 'b' => ['a'], 'c' => ['a']]);
        self::assertSame(['a', 'b', 'a'], $cycles[0]['example']);
    }

    public function testExampleOfAThreeLoopWithTiesAtDepthTwo(): void
    {
        // Two loops of length 3: a -> b -> d -> a and a -> c -> d -> a. BFS reaches d through b first.
        $cycles = Cycles::find(['a' => ['c', 'b'], 'b' => ['d'], 'c' => ['d'], 'd' => ['a']]);
        self::assertSame(['a', 'b', 'd', 'a'], $cycles[0]['example']);
    }

    public function testTheExampleStaysInsideItsCycle(): void
    {
        // a reaches x, which is not in the cycle; x leads nowhere back, so it must not appear.
        $cycles = Cycles::find(['a' => ['b', 'x'], 'b' => ['a'], 'x' => ['y'], 'y' => []]);
        self::assertSame(['a', 'b', 'a'], $cycles[0]['example']);
        self::assertSame(['a', 'b'], $cycles[0]['members']);
    }

    public function testTwoCyclesJoinedOneWayStaySeparate(): void
    {
        $cycles = Cycles::find(['a' => ['b'], 'b' => ['a', 'c'], 'c' => ['d'], 'd' => ['c']]);
        self::assertSame([['a', 'b'], ['c', 'd']], array_column($cycles, 'members'));
    }

    public function testTwoCyclesJoinedBothWaysMerge(): void
    {
        $cycles = Cycles::find(['a' => ['b'], 'b' => ['a', 'c'], 'c' => ['d'], 'd' => ['c', 'a']]);
        self::assertSame([['a', 'b', 'c', 'd']], array_column($cycles, 'members'));
    }

    public function testDuplicateSuccessorsAreIgnored(): void
    {
        self::assertSame(['a', 'b', 'a'], Cycles::find(['a' => ['b', 'b'], 'b' => ['a', 'a']])[0]['example']);
    }

    public function testACompleteGraph(): void
    {
        $units = array_map(static fn (int $i): string => sprintf('u%02d', $i), range(0, 29));
        $successors = [];
        foreach ($units as $unit) {
            $successors[$unit] = array_values(array_diff($units, [$unit]));
        }
        $cycles = Cycles::find($successors);
        self::assertCount(1, $cycles);
        self::assertSame(30, $cycles[0]['size']);
        self::assertSame(['u00', 'u01', 'u00'], $cycles[0]['example']);
    }

    public function testALongLoopDoesNotRecurseDeeply(): void
    {
        $successors = [];
        for ($i = 0; $i < 20000; $i++) {
            $successors[sprintf('n%05d', $i)] = [sprintf('n%05d', ($i + 1) % 20000)];
        }
        $cycles = Cycles::find($successors);
        self::assertCount(1, $cycles);
        self::assertSame(20000, $cycles[0]['size']);
        self::assertCount(20001, $cycles[0]['example']);
        self::assertSame('n00000', $cycles[0]['example'][0]);
        self::assertSame('n19999', $cycles[0]['example'][19999]);
    }

    public function testALongChainHasNoCycles(): void
    {
        $successors = [];
        for ($i = 0; $i < 20000; $i++) {
            $successors[sprintf('n%05d', $i)] = $i < 19999 ? [sprintf('n%05d', $i + 1)] : [];
        }
        self::assertSame([], Cycles::find($successors));
    }

    public function testTheResultDoesNotDependOnInputOrder(): void
    {
        $graph = ['a' => ['b'], 'b' => ['c', 'a'], 'c' => ['a'], 'd' => ['e'], 'e' => ['d'], 'f' => ['a']];
        $reversed = array_reverse(array_map('array_reverse', $graph), true);
        self::assertSame(Cycles::find($graph), Cycles::find($reversed));
    }
}
