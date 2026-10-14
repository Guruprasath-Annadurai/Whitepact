# M11: deterministic offline infrastructure validation

Status: **LOCAL TOOLING REMEDIATION IMPLEMENTED; DEPLOYMENT / PRODUCTION NO-GO**.
Source baseline: `62be9caa70e6c2eb1c4782a64554323646d987e0`.

## Integration correction after actual Linux CI

The first integrated M11 CI at adc6359883047861bd13a981b94c6c185d9f7d50
passed Cloudflare validation but failed Google validation: the cached Linux
package did not match a recorded platform h1 checksum. Darwin-only execution
had not exposed this. The failure was independently reproduced in an isolated
Linux container using the verified native binary; checks were NOT disabled.

The coordinator extended ownership to the optional GCP lock only and generated
Linux/Darwin checksums with `terraform providers lock` against the unchanged
Google5.45.2 selection. Terraform reported HashiCorp signature verification.
All thirteen existing hashes were retained; one Linux h1 was added. No provider
upgrade, Cloudflare lock/routing, resource/IAM/encryption change, plan/apply or
credential was involved. Normal validation remains `-lockfile=readonly`.
Diagnostics now include bounded failure categories, never raw expression values.
The initial lane's no-lock-change and Linux-unexecuted statements below describe
that initial lane, not the subsequent integrated remediation.

## Ownership and non-mutation boundary

Codex owns only new `scripts/infra/validate_terraform.py`,
`tests/test_m11_infra_validator.py` and this document on
`codex/whitepact-m11-offline-infra`. Existing Terraform modules, locks,
Cloudflare configuration, backend security and Antigravity branches are
unchanged. No cloud account, production secret, remote state, IAM binding,
plan/apply, provisioning, paid resource, DNS action or deployment is authorized.
No push has been performed by this workstream.

Here **offline** means validation without a live cloud control-plane or state
backend. Downloading pinned public Terraform/provider dependencies still
requires network access and explicit CLI opt-in. It is not a claim that a cold
machine can fetch missing dependencies while physically disconnected.

## Reproduced defect and actual fix

`/opt/homebrew/bin/terraform` resolves to the Homebrew tfenv wrapper. It derives
its configuration directory from `TFENV_CONFIG_DIR`, `XDG_CONFIG_HOME`, or the
child process's `HOME/.config/tfenv`. In an isolated temporary HOME it failed
before Terraform ran:

```text
exit 1
tfenv: [ERROR] Version could not be resolved
```

The missing configuration was the temporary `.config/tfenv/version`. Restoring
a real user HOME or reusing user credentials is not the fix. The new validator
requires an explicit **native executable** and verifies its bytes against a
pinned official-release-derived SHA-256 before executing it. A wrapper, an
unknown binary, an unsupported platform or a version mismatch is rejected.
It then uses a fresh private child HOME and minimal environment. The actual
native executable works there without tfenv configuration or credential files.

This is a real code/tooling remediation, not a blanket test skip or a change to
shared Terraform. Existing tests that independently call a PATH tfenv wrapper
are not silently relabeled passing; the integration owner must deliberately
invoke the new tool for this validation lane.

## Verified binary provenance

Terraform version is pinned to **1.9.8** for this repository compatibility check;
this is not a claim that it is the newest release or qualified for production.
Official archives were downloaded over verified HTTPS, compared against the
[official 1.9.8 checksum manifest](https://releases.hashicorp.com/terraform/1.9.8/terraform_1.9.8_SHA256SUMS),
then their native `terraform` member bytes were hashed:

| Platform | Official zip SHA-256 | Native executable SHA-256 | Execution proof |
| --- | --- | --- | --- |
| Darwin arm64 | `873d7b925d08578fb6bb9c12c7cd92ae73e289e07c360f2fdd69f9036b7baaab` | `7d15d4cae23f0f85ddd543c5455ecf4b7a384386bb5c0f1da83470f5da543b3f` | Installed `/Users/ag/.config/tfenv/versions/1.9.8/terraform` is byte-identical to official archive member; actual native validation executed |
| Linux x86_64 | `186e0145f5e5f2eb97cbd785bc78f21bae4ef15119349f6ad4fa535b83b10df8` | `7386e89a97d0f24024955acc79ccf693b75b97f7c6383cb9d966e7d59aa5b223` | Official archive/member checksum verified; Linux runtime validation not executed in this workstream |

This verifies official TLS-delivered release checksum identity, **not an
independent GPG verification of HashiCorp's checksum manifest**. No Terraform
binary or provider package is committed to the repository. Other platforms
fail closed until a reviewed, independently verified native hash is added.

## Safe command and executable contract

```sh
python scripts/infra/validate_terraform.py \
  --terraform-binary /Users/ag/.config/tfenv/versions/1.9.8/terraform \
  --revision 62be9caa70e6c2eb1c4782a64554323646d987e0 \
  --allow-provider-download
```

Use the appropriate verified native binary path on another host; do not pass
the tfenv shim or cloud credentials. Only `HEAD` or an exact forty-character
commit SHA is accepted. Per-command timeouts are constrained to 10–300 seconds
(default 120). The validator has no apply/plan/destroy, arbitrary module,
variable-file, credential, backend, force or unpin option.

The tool archives tracked `infra/terraform` and referenced `deploy` files from
the exact Git commit, not dirty/untracked files or existing provider caches.
Archive and expanded-file bytes are bounded to 128 MiB. Absolute paths,
traversal, symlinks, hardlinks and special files are rejected. All extraction,
provider initialization and generated cache files live in disposable storage;
temporary storage is removed on completion. Existing source paths are never
Terraform's working directory.

Child processes inherit no ambient `TF_CLI_ARGS`, `TF_VAR_*`, proxy settings,
cloud credentials, tfenv configuration or operator HOME rc. The tool creates
its own minimal Terraform rc and disables the update checkpoint. Commands are
constructed as argument arrays, not shell strings:

```text
native-terraform version -json
native-terraform fmt -check -recursive infra/terraform
native-terraform init -backend=false -lockfile=readonly -input=false -no-color
native-terraform validate -json
```

Only the two fixed modules `cloudflare-edge` and `gcp-staging-optional` undergo
provider initialization/schema validation. Existing dependency locks determine
provider versions/checksums; Terraform's default provider integrity checks stay
enabled. Lock SHA-256 is compared before and after. There is no lockfile
regeneration, insecure TLS switch or `continue-on-error` behavior. Malformed
validation JSON, non-boolean success, inconsistent error counts, command
failure and changed locks cannot produce a PASS. Warnings remain counted.
Diagnostics source snippets, expression values and arbitrary text are not
printed; output contains bounded categories, counts and severities only.

[HashiCorp's validate contract](https://developer.hashicorp.com/terraform/cli/commands/validate)
explicitly distinguishes schema/internal consistency from remote-service and
state validation and supports backend-disabled initialization. Consequently a
schema PASS does not prove account IAM, current deployed state, route coverage,
origin protection, availability, quota enforcement or financial eligibility.

## Actual local evidence and limitations

Fresh Darwin arm64 run from the baseline used verified native Terraform 1.9.8
with a disposable isolated HOME. Both module `init` and `validate` returned
exit 0, with **zero schema errors and zero schema warnings**. Locked provider
identities were Cloudflare 4.52.9 and Google 5.45.2. Locks remained unchanged:

| Module | Lock SHA-256 |
| --- | --- |
| Cloudflare edge | `a71abbd3cb2f17e31b990f02425da66f61f9b4d2a8b2b3121d25f4246551769c` |
| Optional GCP staging | `e5927a9b3bcb45236e8caf79dc71910c8df66c3a9095a2ad062a61d5d876dc59` |

Focused safety/calculation/CLI regression tests: **28 passed, 0 failed,
0 skipped**, with no cloud/provider execution in those unit tests. Real
provider execution is separately recorded, not counted as mocked unit proof.
Tests cover clean child environment, wrapper/checksum rejection, revision and
deadline bounds, traversal/link rejection, forbidden mutation/module options,
provider-download opt-in, malformed output and diagnostic-secret suppression.
Ruff and exact candidate validation must be freshly rerun after integration.
Any network/TLS/provider failure must remain visible as a failing/blocking
result; do not bypass package verification to make it green.

## Zero-cost deployment artifact honesty

**Paid Hetzner selection is explicitly excluded**, even though its legacy
module exists and was schema-validated in an earlier workstream. This validator
does not initialize it or select it as an evaluation/production host. Formatting
the existing Terraform tree is not selecting legacy modules for deployment.

The defensible artifacts here are the deterministic validator, locked module
schema evidence and non-mutation contract. **No nine-provider deployment-ready
or zero-dollar enterprise stack is proven.** Cloudflare module resources can
change DNS/TLS and feature availability is plan-dependent; optional GCP backup
storage can accrue charges. Their syntactic validity does not make either an
authorized zero-cost deployment. Actual free-plan eligibility, shared quotas,
retention, regions, egress, restore behavior, account caps and IAM require the
owner's separate approval and independent evidence. No paid-plan upgrade is
part of this tool.

For the proposed nine-platform boundaries, consult
`docs/engineering/WAVE1_NINE_PLATFORM_MODEL.md`; it is a design/qualification
model, not deployed infrastructure evidence. This lane does not invent missing
AWS/Oracle/Neon/Upstash/Better Stack/Deno/GitHub deployment modules or alter
shared Cloudflare security configuration. Antigravity's P0 work and all
production activation gates remain independent and unchanged.
