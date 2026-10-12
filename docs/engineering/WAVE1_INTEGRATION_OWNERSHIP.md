# Wave 1 compatibility integration ownership

Preserved ancestor: PR #198 / `f338556baf9984ab485f2d4758179fb87e8baa4d`.

Coordinator branch: `codex/whitepact-wave1-compatibility-qualification`.
Only new protocol/framework tests, dependency pins, evidence/model documents and
the dedicated read-only CI workflow are integrated here. Source lane commits:

- MCP: `810ebe3fc4c34093cf62bf4b4b85fbafa7490ecb`.
- Frameworks: `62e494d8c4c95ace28ecdb6b158d7fd40e507981`.
- Nine-platform model: `aeff5c13a758811638c59431eaddfa0054ca5df8`.

Separate Go governance SDK branch/PR #199 owns its SDK files and SDK workflows.
Separate package-install lane owns only its newly assigned package qualification
files unless a defect is reproduced against this exact ancestor.

Antigravity exclusively owns ongoing core security/runtime, billing, authentication,
authority, revocation and Linux containment remediation. Existing infrastructure
security route mismatches are reported, not modified. No cloud credentials,
provisioning, provider account access, Terraform apply, DNS or production action.

These consumer/protocol tests supplement rather than replace Antigravity-executed
security qualification. Source-bound infrastructure tests are not deployment proof.
Production remains NO-GO; no main merge or publication is authorized.
