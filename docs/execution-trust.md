# Execution trust

V1 defines four execution trust classes:

- pr-untrusted
- trusted-branch
- trusted-manual
- live-qualification

Capabilities only increase through platform policy, never through repository-controlled
text.

An untrusted PR may read the repository, execute tests, and use synthetic fixtures. It cannot
request test/provider credentials or live provider reads.

Trusted branch execution may additionally write bounded private evidence.

Trusted manual execution may additionally use bounded test credentials.

Live qualification is the only class that may use bounded provider credentials or claim live
provider-read evidence. It additionally requires a full exact repository SHA, explicit target,
and explicit owner approval before live qualification can be planned.

No V1 trust class contains generic provider mutation authority.
