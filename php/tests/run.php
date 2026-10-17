<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

// Runs the PHP library's checks: the shared conformance cases plus a few unit checks.
// Usage: php tests/run.php

require __DIR__ . '/../vendor/autoload.php';

use Untangled\Cli\Application;
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

// Conformance: every case under conformance/cases/*/php must produce its expected pairs.
$cases = glob(__DIR__ . '/../../conformance/cases/*/php', GLOB_ONLYDIR) ?: [];
check('conformance cases exist', $cases !== []);
foreach ($cases as $case) {
    $name = basename(dirname($case));
    $expected = json_decode((string) file_get_contents($case . '/expected/pairs.json'), true, 512, JSON_THROW_ON_ERROR);
    $actual = (new Scanner())->scan($case . '/project')->pairs->toArray();
    $same = withoutGenerator($expected) === withoutGenerator($actual);
    check("conformance {$name}", $same, $same ? '' : json_encode(withoutGenerator($actual), JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES));
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

echo "\n{$passed} passed, {$failures} failed\n";
exit($failures === 0 ? 0 : 1);
