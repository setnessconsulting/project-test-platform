# Contributing

## Development environment

Use Python 3.12 or newer.

1. Create a local virtual environment.
2. Install the project with the dev extra.
3. Run the canonical verification command:

   python -m test_platform.verify

The verification path is credential-free and must pass from a clean checkout.

## Change discipline

- Keep the public repository safe for permanent disclosure.
- Preserve authority boundaries documented in ARCHITECTURE.md.
- Add deterministic tests for behavior changes.
- Do not add a test merely to increase count or line coverage.
- Do not add direct provider credentials or CI-controller authority.
- Keep synthetic evidence clearly distinct from live qualification evidence.

## Pull requests

A pull request should identify the Jira issue, summarize behavior changes, list verification
performed, and explicitly call out anything that remains fixture-only or unqualified live.
