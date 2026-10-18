// SPDX-License-Identifier: MIT
// Node.js builtin modules (spec/languages/typescript.md, "Resolving an import", step 4).

// Node.js 24's builtinModules without the internal `_` modules, fixed so a project is
// classified the same on every Node version. Modules that only exist with the node:
// prefix (node:test, node:sqlite, node:sea) are builtins only when written with it.
export const BUILTINS: ReadonlySet<string> = new Set([
  "assert", "async_hooks", "buffer", "child_process", "cluster", "console", "constants", "crypto", "dgram",
  "diagnostics_channel", "dns", "domain", "events", "fs", "http", "http2", "https", "inspector", "module", "net",
  "os", "path", "perf_hooks", "process", "punycode", "querystring", "readline", "repl", "stream",
  "string_decoder", "sys", "timers", "tls", "trace_events", "tty", "url", "util", "v8", "vm", "wasi",
  "worker_threads", "zlib",
]);

/** The builtin a specifier names, as `builtin:<name>`'s name, or undefined. */
export function builtinName(specifier: string, declared: ReadonlySet<string>): string | undefined {
  if (specifier.startsWith("node:")) {
    return specifier.slice("node:".length).split("/")[0] || undefined;
  }
  const name = specifier.split("/")[0]!;
  return BUILTINS.has(name) && !declared.has(name) ? name : undefined;
}
