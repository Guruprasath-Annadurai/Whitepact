# Disaster Recovery

- **Primary backup:** Cloudflare R2 (client-side encryption, restricted writer identity).
- **Optional secondary:** GCS while credits valid — production recovery **must not** depend on GCP.

RTO/RPO: not published until demonstrated restore in isolated environment.

**Status:** IMPLEMENTED_NOT_DEPLOYED (IaC/docs); restore drill OWNER_APPROVAL_REQUIRED.
