# M13 immutable container-image admission

This contract closes content-selection admission in the Docker backend. It does not approve a production image, qualify an identity provider or authorize deployment.

## Trust boundary

The previous backend passed `image_name` directly to `docker create`; recommending a pinned image in a comment was not enforcement. PR240/241 recorded image IDs/RepoDigests while explicitly reporting `digest_admission_enforced: false`. Their original evidence remains unchanged.

Every default backend execution now requires explicit deployment approval, fresh image admission, content-ID creation with `--pull=never`, and inspection of the actual stopped container's image before START. Both ordinary broker execution and direct backend callers traverse the gate. The isolated workload cannot set host approval policy or choose an image through request environment overrides.

`WHITEPACT_ISOLATION_IMAGE_APPROVALS` is a bounded JSON object mapping the exact immutable reference to its expected Docker content/configuration ID. An example shape (placeholders are intentionally invalid until replaced by actual reviewed values):

```text
WHITEPACT_ISOLATION_IMAGE=registry.example/whitepact@sha256:<manifest-or-index-digest>
WHITEPACT_ISOLATION_IMAGE_APPROVALS={"registry.example/whitepact@sha256:<manifest-or-index-digest>":"sha256:<approved-config-id>"}
```

Only the trusted deployment/release owner supplies this configuration. It is not customer input, a registry-discovery result, an automatic cache approval, or an execution grant. A registry manifest/index digest and a Docker configuration ID are different content identifiers; comparing them directly for equality would be incorrect. The approval binds the pair. A deployment on another architecture needs an explicitly approved configuration ID for that architecture, even when the index digest is shared.

Production requires a repository@sha256 reference, an approved full configuration ID, successful digest-addressed Docker pull, exact matching RepoDigests entry, Linux OS, and actual inspected content-ID equality. Tags, tag-plus-digest aliases, shortened digests, malformed/duplicate approval data, missing approvals, failed pull/inspect, substituted manifest/configuration, or changed container identity refuse admission. Docker's content-addressed store and its digest verification are trusted. A compromised privileged Docker daemon/host is outside this containment guarantee. TLS/authentication remain Docker's configured registry transport; this implementation does not disable verification or inject registry credentials.

For nonproduction, explicitly approved full local IDs (`sha256:<64 lowercase hex>`) support CI images built from the exact source. The approval key must equal its value, and actual inspection must match. There is no mutable-tag exception and no fallback from a failed registry pull to local mode. Every recognized production alias, conflicting/unknown environment value, and later switch to production makes a local-only image ineligible. Local-ID qualification is **not registry manifest or signature qualification**.

Image signing/attestation (cosign/Notation) is not implemented or claimed; no signing trust key was supplied. Digest approval is content selection, not publisher identity verification. Missing production approvals continue to block production execution.

## Lifecycle and recovery

Preflight checks admission before nonce admission, without creating or starting a container. A proven refusal keeps the consumed approval consumed and records BLOCKED with an unspent nonce under existing Option A semantics. Execute performs fresh admission; it never trusts a preflight lease/cache. Once the execution nonce is admitted, failures retain UNKNOWN/reconciliation semantics. Nothing resets an approval, nonce or uncertain execution.

Docker create receives only the admitted content ID and `--pull=never`. Before START, the backend checks the stopped container's image ID and current approval. Existing final wall deadline, authorization expiry and revocation checks run after image inspection so its latency cannot extend authority. Cleanup, durable ownership fencing, UID/ACLs, read-only mounts, capability dropping, resource limits and network denial remain in force.

Hosted executions also persist `isolation.image.bound` in the existing enterprise security audit before START. The transaction checks the acknowledged ACTIVE containment row's generation and container ID, and binds the approved reference/content ID to the organization, execution, authorization and action digest. `start_sent:false` means this record is image-binding evidence, never proof of tool execution or success. A failed audit write prevents START; original durable nonce/outcome/cleanup rules still apply. No database schema is changed. Image approval is checked again after inspection and immediately before START, including after this evidence write.

Recovery is operator-led: restore the registry/daemon or approve a separately reviewed new immutable binding, preserve the failed attempt, and obtain fresh request/approval where required. A successful later admission is not permission to replay an earlier uncertain execution. Remove an old policy entry to revoke that content; changing an image-selection variable alone does not revoke other explicitly approved entries.

## Qualification provenance

Existing workflow setup now adds `docker build --iidfile` and a CI-only helper which inspects that exact build ID and writes nonproduction approval/environment records for later steps. Mandatory test commands, assertions, zero-skip guards and security settings remain intact. This is approval of the disposable test build only, not production release authority. The historical stock-image-negative test now approves a pinned stock image's immutable local ID before retaining its original missing-WhitePact assertions. The creation-protocol Docker double supplies typed image receipts and adds content-ID/pull-policy assertions; it does not mock out the admission gate.

New coverage includes malformed/tag references, independent approval, wrong manifest/config/repository/platform, registry failure without fallback, JSON ambiguity/size limits, policy removal, request override rejection, production/local separation, and durable BLOCKED/UNKNOWN accounting. Native Linux tests use a digest-pinned disposable registry bound to loopback only. They exercise actual Docker pulls, tag mutation, registry outage/recovery, manifest-body substitution, actual stopped-container binding and approval removal after real backend creation. Native tests and source/host receipts must pass with zero skips; mocked tests alone are not containment evidence.

Stage19's prior five qualification tests are ported onto this new branch; only the old false-enforcement assertion is strengthened to require true after actual preflight. Frozen PR240/241 source/artifacts are not edited. Full real-tool execution and the existing native/P0 tests remain required on Linux.

The new workflow also prepares a genuine canonical journey on Ubuntu24.04/PostgreSQL16/Docker/ACLs/Chromium. It uses no identity seeding, prototype mode or Windows shim. Its ordinary canonical acceptance command must fail until the legitimate identity/provider gates are satisfied; reports are uploaded even on failure. The existing Sovereign workflow's expected 17/1/7 refusal remains a refusal-contract test, not full customer acceptance. No green 25-stage canonical result is manufactured.

References checked29 October2026: [Docker pull and immutable digests](https://docs.docker.com/reference/cli/docker/image/pull/), [OCI manifest/config descriptors](https://specs.opencontainers.org/image-spec/manifest/), [OCI descriptor integrity](https://specs.opencontainers.org/image-spec/descriptor/). Registry fixture digest was obtained from Docker Hub's official library/registry2.8.3 metadata; it is a test dependency, never a runtime production approval.

M13 OPEN / PRODUCTION NO-GO / M14 NOT AUTHORIZED.
