<?php
// SPDX-License-Identifier: MIT

declare(strict_types=1);

namespace Untangled\Cli;

use Untangled\Composer\ProjectException;
use Untangled\Scanner\Scanner;
use Untangled\Version;

/**
 * `untangled <command> [options]`. The command and option names are shared by every
 * Untangled library; v0.1 implements `scan`.
 */
final class Application
{
    private const USAGE = <<<'TXT'
        Usage: untangled scan [<path>] [--dev] [--format=json|snakefood] [--output=<file>]

        Commands:
          scan       Write the dependency pairs of a Composer project (default path: .)

        Options:
          --dev              Also scan autoload-dev (tests)
          --format=FORMAT    json (default, the Untangled pairs document) or snakefood
          --output=FILE      Write to FILE instead of standard output
          -h, --help         Show this help
          -V, --version      Show the version

        TXT;

    /** @param resource $stdout @param resource $stderr */
    public function __construct(
        private $stdout = STDOUT,
        private $stderr = STDERR,
    ) {
    }

    /** @param list<string> $argv arguments without the program name */
    public function run(array $argv): int
    {
        $positional = [];
        $options = [];
        foreach ($argv as $arg) {
            if ($arg === '-h' || $arg === '--help') {
                fwrite($this->stdout, self::USAGE);
                return 0;
            }
            if ($arg === '-V' || $arg === '--version') {
                fwrite($this->stdout, Version::NAME . ' ' . Version::VERSION . "\n");
                return 0;
            }
            if (str_starts_with($arg, '--')) {
                [$name, $value] = array_pad(explode('=', substr($arg, 2), 2), 2, true);
                $options[$name] = $value;
                continue;
            }
            $positional[] = $arg;
        }

        $command = array_shift($positional);
        if ($command !== 'scan') {
            fwrite($this->stderr, $command === null ? self::USAGE : "Unknown command: {$command}\n\n" . self::USAGE);
            return 2;
        }
        $unknown = array_diff(array_keys($options), ['dev', 'format', 'output']);
        if ($unknown !== []) {
            fwrite($this->stderr, 'Unknown option: --' . reset($unknown) . "\n");
            return 2;
        }
        $format = $options['format'] ?? 'json';
        if (!in_array($format, ['json', 'snakefood'], true)) {
            fwrite($this->stderr, "Unknown format: {$format}\n");
            return 2;
        }

        $path = $positional[0] ?? '.';
        try {
            $result = (new Scanner(dev: isset($options['dev'])))->scan($path);
        } catch (ProjectException $e) {
            fwrite($this->stderr, 'error: ' . $e->getMessage() . "\n");
            return 1;
        }
        foreach ($result->warnings as $warning) {
            fwrite($this->stderr, "warning: {$warning}\n");
        }

        $output = $format === 'json' ? $result->pairs->toJson() : $result->pairs->toSnakefood($path);
        if (isset($options['output']) && is_string($options['output'])) {
            if (file_put_contents($options['output'], $output) === false) {
                fwrite($this->stderr, "error: cannot write {$options['output']}\n");
                return 1;
            }
        } else {
            fwrite($this->stdout, $output);
        }
        return 0;
    }
}
