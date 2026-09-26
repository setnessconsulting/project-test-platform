# Security

## Public repository rule

Treat every committed byte as permanently public. Making this repository private later does
not retract clones, forks, screenshots, cached copies, or previously distributed history.

Never commit:

- credentials, API keys, tokens, passwords, or private keys;
- private repository inventories or proprietary source/test output;
- raw private Jenkins logs;
- internal user-specific machine paths;
- customer or learner data;
- production fixtures or vulnerability findings tied to private systems;
- raw private qualification evidence.

## Trust boundaries

Repository files, manifests, test names, test output, pull-request content, result files,
and executor output are untrusted data. They must not be allowed to choose credentials,
expand authority, mutate policy, or configure trusted Jenkins controller behavior.

## Secret and path scanning

The repository includes a small deterministic high-confidence public-safety scanner. It is
a release guard, not a replacement for provider secret scanning or code review.

## Reporting vulnerabilities

Do not open a public issue containing an exploitable vulnerability, credential, private
repository detail, or customer data. Use the repository owner's private security/reporting
channel instead.
