# Repository manifest

A participating repository binds to Test Platform with a root .test-platform.yaml file.

The V1 manifest contains:

- schema_version
- explicit Quality Profile ID and exact version
- repository-local behavior declaration path
- named suite entrypoints
- suite trust class
- timeout
- evidence classes produced by the suite

Suite entrypoints are identifiers such as test:e2e or verify, not arbitrary shell commands.
An executor maps an allowlisted identifier to repository-local execution under its own
policy.

The behavior path must be a portable repository-relative path. Absolute paths, parent
traversal, backslashes, symlink escapes, and a symlinked manifest are rejected.

The manifest is untrusted repository data. It cannot select credentials, provider accounts,
Jenkins controller configuration, or policy.
