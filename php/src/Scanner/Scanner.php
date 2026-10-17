<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Scanner;

use Untangled\Composer\ComposerProject;
use Untangled\Graph\PairsDocument;
use Untangled\Path;

/**
 * Scans a Composer project into a pairs document, following spec/languages/php.md:
 * autoload rules choose the files, literal includes are followed, and every
 * reference resolves to a project file, a Composer package, a builtin, or
 * an unresolved node.
 */
final class Scanner
{
    private readonly FileScanner $fileScanner;

    public function __construct(private readonly bool $dev = false)
    {
        $this->fileScanner = new FileScanner();
    }

    public function scan(string $path): ScanResult
    {
        $project = ComposerProject::load($path);
        $root = $project->root;
        $vendorDir = $project->vendorDir();
        $warnings = [];

        // Scan the autoloaded files, then any project file reached through a literal include.
        /** @var array<string, FileResult> $results */
        $results = [];
        /** @var array<string, list<string>> include targets per file, as node ids */
        $includeTargets = [];
        $queue = $project->sourceFiles($this->dev);
        while ($queue !== []) {
            $file = array_shift($queue);
            if (isset($results[$file])) {
                continue;
            }
            $result = $this->fileScanner->scan($root . '/' . $file);
            $results[$file] = $result;
            if ($result->error !== null) {
                $warnings[] = "{$file}: {$result->error}";
            }
            foreach ($result->includes as $include) {
                $target = $this->resolveInclude($include, $root, $file, $vendorDir);
                $includeTargets[$file][] = $target;
                if (!self::isPrefixedId($target) && !isset($results[$target])) {
                    $queue[] = $target;
                }
            }
        }
        ksort($results, SORT_STRING);

        // Symbol tables. Class and function names are case-insensitive in PHP, constants are not.
        $classes = [];
        $functions = [];
        $constants = [];
        foreach ($results as $file => $result) {
            foreach ($result->classes as $class) {
                $key = strtolower($class);
                if (isset($classes[$key])) {
                    // Declaring a class twice in one file (inside if/else) is a common polyfill pattern.
                    if ($classes[$key] !== $file) {
                        $warnings[] = "{$file}: {$class} is also declared in {$classes[$key]}; using the first";
                    }
                    continue;
                }
                $classes[$key] = $file;
            }
            foreach ($result->functions as $function) {
                $functions[strtolower($function)] ??= $file;
            }
            foreach ($result->constants as $constant) {
                $constants[$constant] ??= $file;
            }
        }

        $vendor = new VendorIndex($project->packages(), $this->fileScanner);
        $pairs = new PairsDocument('php');

        foreach ($results as $file => $result) {
            $extra = [];
            if ($result->module !== null) {
                $extra['module'] = $result->module;
            }
            $symbols = $result->symbols();
            if ($symbols !== []) {
                $extra['symbols'] = $symbols;
            }
            $pairs->addNode($file, PairsDocument::INTERNAL, $extra);
        }

        foreach ($results as $file => $result) {
            foreach ($result->references as $reference) {
                $target = match ($reference['symbol']) {
                    FileResult::CLASS_SYMBOL => $this->resolveClass($reference['candidates'][0], $classes, $vendor),
                    FileResult::FUNCTION_SYMBOL => self::firstMatch($reference['candidates'], $functions, true),
                    default => self::firstMatch($reference['candidates'], $constants, false),
                };
                if ($target === null) {
                    continue;
                }
                // An import that resolves to nothing may name a namespace (`use App\Models;`);
                // the code that uses it is resolved on its own, so the import adds nothing.
                if ($reference['kind'] === 'import' && str_starts_with($target, 'unresolved:')) {
                    continue;
                }
                $this->link($pairs, $file, $target, $reference['kind']);
            }
            foreach ($includeTargets[$file] ?? [] as $target) {
                $this->link($pairs, $file, $target, 'include');
            }
        }

        return new ScanResult($pairs, $warnings);
    }

    private static function isPrefixedId(string $id): bool
    {
        return str_starts_with($id, 'composer:') || str_starts_with($id, 'builtin:') || str_starts_with($id, 'unresolved:');
    }

    private function link(PairsDocument $pairs, string $from, string $to, string $kind): void
    {
        if (!$pairs->hasNode($to)) {
            $nodeKind = match (true) {
                str_starts_with($to, 'composer:') => PairsDocument::EXTERNAL,
                str_starts_with($to, 'builtin:') => PairsDocument::BUILTIN,
                str_starts_with($to, 'unresolved:') => PairsDocument::UNRESOLVED,
                default => PairsDocument::INTERNAL,
            };
            $pairs->addNode($to, $nodeKind);
        }
        $pairs->addEdge($from, $to, $kind);
    }

    /** @param array<string, string> $classes */
    private function resolveClass(string $name, array $classes, VendorIndex $vendor): string
    {
        if (isset($classes[strtolower($name)])) {
            return $classes[strtolower($name)];
        }
        $package = $vendor->packageFor($name);
        if ($package !== null) {
            return 'composer:' . $package;
        }
        $builtin = self::builtinClass($name);
        if ($builtin !== null) {
            return 'builtin:' . $builtin;
        }
        return 'unresolved:class:' . $name;
    }

    /**
     * Functions and constants only count when the project declares them; anything
     * else is taken to be builtin and not recorded (spec/languages/php.md).
     *
     * @param list<string> $candidates
     * @param array<string, string> $table
     */
    private static function firstMatch(array $candidates, array $table, bool $caseInsensitive): ?string
    {
        foreach ($candidates as $candidate) {
            $key = $caseInsensitive ? strtolower($candidate) : $candidate;
            if (isset($table[$key])) {
                return $table[$key];
            }
        }
        return null;
    }

    /** The canonical name of a class-like built into the running PHP, or null. */
    private static function builtinClass(string $name): ?string
    {
        if (!class_exists($name, false) && !interface_exists($name, false) && !trait_exists($name, false) && !enum_exists($name, false)) {
            return null;
        }
        $reflection = new \ReflectionClass($name);
        return $reflection->isInternal() ? $reflection->getName() : null;
    }

    /**
     * Turns an include into a node id: a project file (which is then scanned too),
     * a Composer package, or an unresolved include.
     *
     * @param array{path: ?string, text: string} $include
     */
    private function resolveInclude(array $include, string $root, string $file, string $vendorDir): string
    {
        if ($include['path'] === null) {
            return 'unresolved:include:' . $include['text'];
        }
        $path = $include['path'];
        $isAbsolute = str_starts_with(str_replace('\\', '/', $path), '/');
        // A relative path is tried against the project root (PHP's working directory
        // when run from the root), then against the including file's directory.
        $candidates = $isAbsolute
            ? [Path::normalize($path)]
            : [Path::join($root, $path), Path::join(dirname($root . '/' . $file), $path)];

        foreach ($candidates as $candidate) {
            $relative = Path::relative($root, $candidate);
            if ($relative === null || !is_file($candidate)) {
                continue;
            }
            if (str_starts_with($relative, $vendorDir . '/')) {
                $parts = explode('/', substr($relative, strlen($vendorDir) + 1));
                if (count($parts) >= 3) {
                    return 'composer:' . $parts[0] . '/' . $parts[1];
                }
                continue;
            }
            return $relative;
        }

        $relative = Path::relative($root, $candidates[0]);
        return 'unresolved:include:' . ($relative ?? $include['text']);
    }
}
