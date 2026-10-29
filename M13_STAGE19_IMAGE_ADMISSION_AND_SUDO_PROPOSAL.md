# Stage 19 image admission proposal and sudo finding

This document does not change production admission. `digest_admission_enforced` stays false.

## Local image identity

`Dockerfile.isolation` builds `whitepact-isolated-runtime` from the pinned base `python:3.12-slim@sha256:7a8b475003c4fe15a2cd4e55e5cfc2f3560bdc9333d624f24cdd6d4340fd7a17`. A local `docker build` then has its own image id. Docker may also place that id in `RepoDigests` for the local tag. That string is a local identity, not a registry signature and not an admission decision.

The qualification workflow records `image_id`, `repo_digests`, and `registry_admission: false` for the image it builds from the pull request head. It does not teach `DockerContainerBackend` to accept or reject by digest.

## Proposed admission control

Do not implement this until a separate Founder/Security Owner approval.

Before: the backend starts `image_name` from the constructor argument, `WHITEPACT_ISOLATION_IMAGE`, or `python:3.11-slim`. Any tag the daemon can resolve is eligible. A moved tag can change bytes without a code change.

After, if approved:

1. Production configuration names one image by registry digest (`name@sha256:…`), not a floating tag.
2. Startup resolves the local image id and requires it to match that digest. A tag-only name fails closed.
3. Optional second step: verify a cosign or Notation signature against a pinned public key before the daemon create. Failure refuses execution and does not fall back to an unsigned tag.
4. The qualification workflow may still build from source. Its receipt must keep `registry_admission: false` until the built image is pushed, signed, and the pinned digest is the one the backend checks.

Security effect: execution would be bound to reviewed bytes, and a retagged image would not run. Operational effect: every runtime update needs a new approved digest, and a missing signature stops all isolated execution. That is why it stays a proposal.

## Sudo on this agent host

`/etc/sudoers.d/ubuntu` contains `ubuntu ALL=(ALL) NOPASSWD:ALL`. `/etc/sudoers.d/ubuntu-no-lecture` disables the lecture. Both files are timestamped 21 Oct 2026, 11:40 PM IST, before the Stage 19 work on 28 Oct 2026. No WhitePact test drop-in was added. Removing this grant would remove the cloud image's pre-existing administrator path for `ubuntu`, so it was left in place.

This host is not the Antigravity WSL machine. If that machine has a separate temporary file such as `/etc/sudoers.d/whitepact-test`, remove only that file with `visudo -c` first, and leave any vendor or user rule that predates the test. This repository does not contain a sudoers change.

Stage 17 and Option A were not modified. No customer identity was issued.

M13 remains open. Production remains no-go. M14 is not authorized.
