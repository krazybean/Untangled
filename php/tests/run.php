<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

// Runs the PHP library's checks: the shared conformance cases plus a few unit checks.
// Usage: php tests/run.php

require __DIR__ . '/../vendor/autoload.php';

use Untangled\Analysis\Analyzer;
use Untangled\Analysis\Clustering;
use Untangled\Analysis\Cycles;
use Untangled\Analysis\Filter;
use Untangled\Analysis\Glob;
use Untangled\Cli\Application;
use Untangled\Graph\DocumentException;
use Untangled\Graph\PairsDocument;
use Untangled\Path;
use Untangled\Scanner\Scanner;

$failures = 0;
$passed = 0;

function check(string $name, bool $ok, string $detail = ''): void
{
    global $failures, $passed;
    if ($ok) {
        $passed++;
        echo "ok   {$name}\n";
    } else {
        $failures++;
        echo "FAIL {$name}\n" . ($detail === '' ? '' : "{$detail}\n");
    }
}

/** @param array<string, mixed> $document */
function withoutGenerator(array $document): array
{
    unset($document['generator']);
    return $document;
}

/** Equality as the spec defines it for conformance: numbers compare to 4 decimal places. */
function sameDocument(mixed $expected, mixed $actual): bool
{
    if ((is_int($expected) || is_float($expected)) && (is_int($actual) || is_float($actual))) {
        return round((float) $expected, 4) === round((float) $actual, 4);
    }
    if (is_array($expected) && is_array($actual)) {
        if (array_keys($expected) !== array_keys($actual)) {
            return false;
        }
        foreach ($expected as $key => $value) {
            if (!sameDocument($value, $actual[$key])) {
                return false;
            }
        }
        return true;
    }
    return $expected === $actual;
}

/** @return array<string, mixed> */
function readJson(string $file): array
{
    return json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
}

// Conformance: every case under conformance/cases/*/php must produce its expected pairs, and
// every expected/analysis[.<clustering>].json its analysis (see conformance/README.md).
$cases = glob(__DIR__ . '/../../conformance/cases/*/php', GLOB_ONLYDIR) ?: [];
check('conformance cases exist', $cases !== []);
foreach ($cases as $case) {
    $name = basename(dirname($case));
    $pairs = (new Scanner())->scan($case . '/project')->pairs;
    $actual = $pairs->toArray();
    $same = sameDocument(withoutGenerator(readJson($case . '/expected/pairs.json')), withoutGenerator($actual));
    check("conformance {$name} pairs", $same, $same ? '' : json_encode(withoutGenerator($actual), JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));

    $analyses = glob($case . '/expected/analysis*.json') ?: [];
    check("conformance {$name} has an expected analysis", $analyses !== []);
    foreach ($analyses as $file) {
        $suffix = substr(basename($file, '.json'), strlen('analysis'));
        $clustering = match (true) {
            $suffix === '' => null,
            $suffix === '.rules' => Clustering::parseRules((string) file_get_contents($case . '/clusters.rules')),
            default => Clustering::fromString(preg_replace('/-(?=[0-9]+$)/', ':', substr($suffix, 1))),
        };
        $actual = (new Analyzer())->analyze((new Filter())->apply($pairs), $clustering);
        $same = sameDocument(withoutGenerator(readJson($file)), withoutGenerator($actual));
        check("conformance {$name} " . basename($file), $same, $same ? '' : json_encode(withoutGenerator($actual), JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));
    }
}

// Path helpers.
check('normalize collapses dot segments', Path::normalize('/a/./b/../c//d') === '/a/c/d');
check('normalize keeps leading .. of relative paths', Path::normalize('../x/../../y') === '../../y');
check('relative inside root', Path::relative('/p', '/p/src/A.php') === 'src/A.php');
check('relative outside root', Path::relative('/p', '/pp/A.php') === null);

// Pairs document behaviour.
$doc = new PairsDocument('php');
$doc->addNode('b.php', PairsDocument::INTERNAL);
$doc->addNode('a.php', PairsDocument::INTERNAL);
$doc->addNode('c.php', PairsDocument::INTERNAL);
$doc->addNode('composer:x/y', PairsDocument::EXTERNAL);
$doc->addEdge('a.php', 'b.php', 'new');
$doc->addEdge('a.php', 'b.php', 'import');
$doc->addEdge('a.php', 'a.php', 'static');
$doc->addEdge('b.php', 'composer:x/y', 'import');
check('edges merge kinds and counts, drop self-edges', $doc->edges() === [
    ['from' => 'a.php', 'to' => 'b.php', 'kinds' => ['import', 'new'], 'count' => 2],
    ['from' => 'b.php', 'to' => 'composer:x/y', 'kinds' => ['import'], 'count' => 1],
]);
check('nodes are sorted by id', array_column($doc->nodes(), 'id') === ['a.php', 'b.php', 'c.php', 'composer:x/y']);
check('json uses two-space indentation', str_starts_with($doc->toJson(), "{\n  \"format\""));
check('snakefood format', $doc->toSnakefood('/r') === implode("\n", [
    "(('/r', 'a.php'), ('/r', 'b.php'))",
    "(('/r', 'b.php'), (None, None))",
    "(('/r', 'c.php'), (None, None))",
]) . "\n");

// Reading pairs documents.
$roundTrip = PairsDocument::fromArray(readJson(__DIR__ . '/../../conformance/cases/psr4-basic/php/expected/pairs.json'));
check('pairs documents read back unchanged', withoutGenerator($roundTrip->toArray()) === withoutGenerator(readJson(__DIR__ . '/../../conformance/cases/psr4-basic/php/expected/pairs.json')));
$rejects = static function (array $data): bool {
    try {
        PairsDocument::fromArray($data);
        return false;
    } catch (DocumentException) {
        return true;
    }
};
$minimal = ['format' => 'untangled-pairs', 'version' => '0.1', 'language' => 'php', 'nodes' => [], 'edges' => []];
check('pairs reader rejects another format', $rejects(['format' => 'untangled-analysis'] + $minimal));
check('pairs reader rejects an unknown major version', $rejects(['version' => '1.0'] + $minimal));
check('pairs reader rejects edges to missing nodes', $rejects(['edges' => [['from' => 'a.php', 'to' => 'b.php']]] + $minimal));
$warnings = [];
PairsDocument::fromArray(['version' => '0.9'] + $minimal, $warnings);
check('pairs reader warns on an unknown minor version', count($warnings) === 1);

// Globs and filtering.
check('glob * stays in one segment', (new Glob('src/*.php'))->matches('src/A.php') && !(new Glob('src/*.php'))->matches('src/B/A.php'));
check('glob ** crosses segments', (new Glob('src/**'))->matches('src/B/C/A.php'));
check('glob **/ matches no directory too', (new Glob('**/Test*.php'))->matches('TestA.php') && (new Glob('**/Test*.php'))->matches('a/b/TestA.php'));
check('glob escapes regex characters', (new Glob('src/a+b.php'))->matches('src/a+b.php') && !(new Glob('src/a+b.php'))->matches('src/aab.php'));
$doc = new PairsDocument('php');
foreach (['src/A.php', 'src/B.php', 'tests/ATest.php', 'tests/Keep.php'] as $id) {
    $doc->addNode($id, PairsDocument::INTERNAL);
}
$doc->addNode('builtin:Countable', PairsDocument::BUILTIN);
$doc->addNode('unresolved:class:X', PairsDocument::UNRESOLVED);
$doc->addNode('composer:x/y', PairsDocument::EXTERNAL);
$doc->addEdge('src/A.php', 'src/B.php', 'new');
$doc->addEdge('src/A.php', 'builtin:Countable', 'implements');
$doc->addEdge('src/A.php', 'composer:x/y', 'import');
$doc->addEdge('tests/ATest.php', 'src/A.php', 'new');
$doc->addEdge('tests/ATest.php', 'unresolved:class:X', 'new');
$filtered = (new Filter())->exclude('tests/**')->include('tests/Keep.php')->apply($doc);
check('filter: builtins dropped, last matching pattern wins, orphaned targets dropped', array_column($filtered->nodes(), 'id') === ['composer:x/y', 'src/A.php', 'src/B.php', 'tests/Keep.php']);
check('filter keeps edges between kept nodes', array_map(static fn (array $e): string => "{$e['from']}>{$e['to']}", $filtered->edges()) === ['src/A.php>composer:x/y', 'src/A.php>src/B.php']);
check('filter can keep builtins', (new Filter(keepBuiltins: true))->apply($doc)->hasNode('builtin:Countable'));

// Clustering.
$node = static fn (string $id, ?string $module = null): array => ['id' => $id, 'kind' => 'internal'] + ($module === null ? [] : ['module' => $module]);
check('namespace:2 takes two segments', Clustering::fromString('namespace:2')->clusterOf($node('src/Billing/Tax.php', 'App\\Billing\\Tax')) === 'App\\Billing');
check('namespace:N keeps a shorter namespace whole', Clustering::fromString('namespace:3')->clusterOf($node('src/Tax.php', 'App')) === 'App');
check('namespace:N falls back to folder:N', Clustering::fromString('namespace:2')->clusterOf($node('lib/a/b/x.php')) === 'lib/a');
check('folder:N keeps a shorter directory path', Clustering::fromString('folder:3')->clusterOf($node('src/x.php')) === 'src');
check('folder:N puts root files in "."', Clustering::fromString('folder:1')->clusterOf($node('index.php')) === '.');
$rules = Clustering::parseRules("# comment\nsrc/Billing/  Billing  # trailing\n\nsrc/ Core\n");
check('rules: first matching prefix wins', $rules->clusterOf($node('src/Billing/Tax.php')) === 'Billing' && $rules->clusterOf($node('src/Clock.php')) === 'Core');
check('rules: unmatched files keep their id', $rules->clusterOf($node('index.php')) === 'index.php');
$malformed = false;
try {
    Clustering::parseRules("src/ Core extra\n");
} catch (InvalidArgumentException) {
    $malformed = true;
}
check('rules: malformed lines are rejected', $malformed);
foreach (['namespace', 'namespace:0', 'files:2', 'folder:x'] as $bad) {
    $rejected = false;
    try {
        Clustering::fromString($bad);
    } catch (InvalidArgumentException) {
        $rejected = true;
    }
    check("clustering \"{$bad}\" is rejected", $rejected);
}
$doc = new PairsDocument('php');
foreach (['a/1.php', 'a/2.php', 'b/1.php'] as $id) {
    $doc->addNode($id, PairsDocument::INTERNAL);
}
$doc->addNode('composer:x/y', PairsDocument::EXTERNAL);
$doc->addEdge('a/1.php', 'a/2.php', 'new');
$doc->addEdge('a/1.php', 'b/1.php', 'new');
$doc->addEdge('a/2.php', 'b/1.php', 'static');
$doc->addEdge('a/2.php', 'b/1.php', 'static');
$doc->addEdge('a/1.php', 'composer:x/y', 'import');
$doc->addEdge('a/2.php', 'composer:x/y', 'type');
['document' => $clustered, 'dropped' => $dropped] = Clustering::fromString('folder:1')->apply($doc);
check('clustering merges edges per (cluster, target)', $clustered->edges() === [
    ['from' => 'a', 'to' => 'b', 'kinds' => ['new', 'static'], 'count' => 3],
    ['from' => 'a', 'to' => 'composer:x/y', 'kinds' => ['import', 'type'], 'count' => 2],
]);
check('clustering lists sorted members', $clustered->node('a') === ['id' => 'a', 'kind' => 'cluster', 'members' => ['a/1.php', 'a/2.php']]);
check('clustering counts dropped edges inside a cluster', $dropped === ['a' => 1]);
$refused = false;
try {
    (new Analyzer())->analyze($clustered);
} catch (InvalidArgumentException) {
    $refused = true;
}
check('analyzer refuses an already-clustered document', $refused);

// Cycles.
$cycles = Cycles::find([
    'e' => ['d'], 'd' => ['e'],
    'a' => ['c', 'b'], 'b' => ['c'], 'c' => ['a'],
    'x' => ['y'], 'y' => [],
    'p' => ['q'], 'q' => ['p'],
]);
check('cycles sort by size, then first member', array_column($cycles, 'members') === [['a', 'b', 'c'], ['d', 'e'], ['p', 'q']]);
check('cycle example is the shortest loop, neighbours in byte order', $cycles[0]['example'] === ['a', 'c', 'a']);
$tie = Cycles::find(['a' => ['c', 'b'], 'b' => ['a'], 'c' => ['a']]);
check('cycle example breaks ties in byte order', $tie[0]['example'] === ['a', 'b', 'a']);
$chain = [];
for ($i = 0; $i < 20000; $i++) {
    $chain[sprintf('n%05d', $i)] = [sprintf('n%05d', ($i + 1) % 20000)];
}
$long = Cycles::find($chain);
check('a 20000-unit loop is found without deep recursion', count($long) === 1 && $long[0]['size'] === 20000 && count($long[0]['example']) === 20001);
check('no units, no cycles', Cycles::find([]) === []);
$empty = (new Analyzer())->analyze(new PairsDocument('php'));
check('empty project summary', $empty['summary'] === ['units' => 0, 'edges' => 0, 'cycles' => 0, 'largest_cycle' => 0, 'units_in_cycles' => 0, 'units_in_cycles_ratio' => 0, 'mean_fan_out' => 0, 'external_packages' => 0, 'unresolved_references' => 0]);

// CLI.
$run = static function (array $args): array {
    $out = fopen('php://memory', 'w+');
    $err = fopen('php://memory', 'w+');
    $code = (new Application($out, $err))->run($args);
    rewind($out);
    rewind($err);
    return [$code, stream_get_contents($out), stream_get_contents($err)];
};
[$code, , $err] = $run(['scan', sys_get_temp_dir()]);
check('cli refuses a directory without composer.json', $code === 1 && str_contains($err, 'No composer.json'));
[$code] = $run(['frobnicate']);
check('cli rejects unknown commands', $code === 2);
[$code, $out] = $run(['scan', __DIR__ . '/../../conformance/cases/three-cycle/php/project', '--format=snakefood']);
check('cli scan --format=snakefood', $code === 0 && str_contains($out, "'src/Catalog.php'), (None, None))"));
$layers = __DIR__ . '/../../conformance/cases/layers/php';
[$code, $out] = $run(['analyze', $layers . '/project', '--cluster=namespace:2']);
check('cli analyze --cluster', $code === 0 && sameDocument(withoutGenerator(readJson($layers . '/expected/analysis.namespace-2.json')), withoutGenerator(json_decode($out, true))));
[$code, $out] = $run(['analyze', $layers . '/expected/pairs.json', '--cluster=rules:' . $layers . '/clusters.rules']);
check('cli analyze reads a pairs document', $code === 0 && sameDocument(withoutGenerator(readJson($layers . '/expected/analysis.rules.json')), withoutGenerator(json_decode($out, true))));
[$code, $out] = $run(['analyze', $layers . '/project', '--exclude=src/Http/**', '--include=src/Http/Router.php']);
$ids = array_column(json_decode($out, true)['units'], 'id');
check('cli analyze applies --include / --exclude in order', $code === 0 && in_array('src/Http/Router.php', $ids, true) && !in_array('src/Http/UserController.php', $ids, true));
[$code, , $err] = $run(['analyze', $layers . '/project', '--cluster=files:2']);
check('cli analyze rejects an unknown clustering', $code === 2 && str_contains($err, 'unknown clustering'));
[$code] = $run(['analyze', $layers . '/project', '--format=snakefood']);
check('cli analyze rejects scan-only options', $code === 2);
[$code, , $err] = $run(['analyze', __FILE__]);
check('cli analyze rejects a file that is not a pairs document', $code === 1 && str_contains($err, 'not valid JSON'));

echo "\n{$passed} passed, {$failures} failed\n";
exit($failures === 0 ? 0 : 1);
