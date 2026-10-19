# Security

Please report a vulnerability privately through
[GitHub security advisories](https://github.com/krazybean/Untangled/security/advisories/new)
rather than in a public issue. Include the library (PHP, Python or
JavaScript/TypeScript), its version, and a project or input that shows the
problem.

Untangled parses source code without running it, so the main risks are crafted
input that crashes or slows the scanner, and report HTML that could run
script from a file or class name. Both are treated as security issues.
