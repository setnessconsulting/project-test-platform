# Temporary Python 3.12 shadow CI probe — 2026-10-03

This documentation-only change supports exact-head pull-request observation for the existing `project-test-platform-python312` shadow profile. It does not change application code or CI configuration.

The existing Actions `verify` workflow grants `contents: read`, runs on a GitHub-hosted runner, sets up Python 3.12, installs `.[dev]`, and runs `python -m test_platform.verify`. The workflow uses no CI credentials. GitHub Actions remains authoritative while Jenkins is shadow evidence.

This note makes no claim about production behavior or deployment. It contains no credentials or private provider evidence. Close the temporary source pull request unmerged after exact-head Actions and shadow readback are recorded.
