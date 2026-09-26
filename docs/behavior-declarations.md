# Behavior and critical-journey declarations

Repositories declare the behavior they need to prove in a versioned YAML document referenced
by .test-platform.yaml.

A behavior has a stable ID, description, criticality, required evidence classes, and optional
conditional evidence.

A critical journey references declared behaviors and requires assembled end-to-end evidence.
The V1 validator rejects duplicate behavior/journey IDs, unknown journey references, repeated
references, and a critical journey that omits end-to-end evidence.

Behavior declarations describe requirements. They do not become tests by themselves, and
Test Platform does not infer behavior-to-test links from similar names.
