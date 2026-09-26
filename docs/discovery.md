# Test-framework discovery

Discovery inspects one explicitly selected repository-like root. It never executes repository
tests, installs dependencies, or treats repository text as instructions.

## Bounds

The default index limits are:

- 20,000 files
- depth 12
- 1 MB for any text file read by a plugin

The scanner prunes dependency/build/cache directories and does not follow symlink directories
or files. A root must contain .test-platform.yaml or .git and cannot be the filesystem root.

When the file limit is reached, the result is LIMIT_EXCEEDED. Incomplete discovery is never
reported as a complete absence of frameworks.

## Plugin contract

Framework plugins have a stable framework ID and adapter version and return a normalized
FrameworkDiscovery.

V1 built-in discovery recognizes pytest, Jest, Vitest, Playwright, and Pester using static
configuration/file signatures.

Package.json script names can be reported as command identifiers. Script bodies are never
returned as execution instructions.

Malformed configuration is explicit MALFORMED evidence. A repository with no supported
framework is UNKNOWN rather than successful or empty-qualified.
