# Security boundary analysis

This design does not relax a WhitePact control to fit a free tier. Where a
free service cannot carry a control, the service is excluded from that role.

Antigravity's cloud verdict remains **BLOCKED — UNSAFE TO PROVISION**.
The notes below are the boundary analysis for a future dev VM. They are not
a claim that CLOUD-AG-01 through CLOUD-AG-07 are fixed.

## 1. Independent authority

WhitePact's decision path is `WhitePactRuntimeGateway`: ALLOW,
ALLOW_WITH_REDACTION, REQUIRE_APPROVAL, DENY, QUARANTINE. It does not call
an LLM and it does not call cloud IAM.

| Boundary | Kept by | Free-tier temptation rejected |
|---|---|---|
| Governance ≠ cloud IAM | Decisions stay in `src/responsibleai/governance/` | Do not encode allow/deny in OCI IAM, GCP IAM, AWS IAM, or a Cloudflare Worker |
| Operator is not the customer root | Phase 3 closure: platform operator cannot bootstrap customer roots | Do not import a cloud admin principal as a tenant trust root |
| Sovereign is read/simulate | `docs/sovereign/ARCHITECTURE.md` | Do not point Sovereign at a Neon or R2 copy and call it the authority record |
| Redis is not authority | Rate limits and the Phase 7A design both say loss of Redis must not grant authority | Do not move evidence or approvals into Upstash, Workers KV, or R2 |
| Phase 7A dispatcher | Production refuses to start the gated stub | Do not enable `PHASE7A_DISPATCHER_ENABLED` on this VM |

OCI IAM on this candidate is limited to the operator API user creating the
network and the VM. That user is an infrastructure administrator. It is not
an `AuthorityContext`.

## 2. Execution isolation

`DockerContainerBackend` refuses any profile whose network policy is not
`none`, drops all capabilities, sets `no-new-privileges`, runs read-only,
and applies the `ResourceLimits` in `src/responsibleai/isolation/models.py`.
Production mode fails closed when Docker is missing and rejects the local
subprocess backend.

The candidate VM keeps that backend:

- Docker is installed from Ubuntu's `docker.io` package, not from a piped
  install script.
- The Docker socket stays on the host. It is not published and it is not
  mounted into the dashboard container. The socket is a control-plane trust
  boundary; anyone who can use it can escape the sandbox flags.
- Sandbox CPU, RAM, and PID limits are the code defaults. They are not
  raised to "fit" a smaller VM. The VM is sized so the defaults fit.
- GitHub-hosted runners may execute the same tests. A pass there shows the
  flags work on that kernel. It does not show tenant separation across a
  shared free application platform.

`LocalSubprocessBackend` remains a development backend. It is not the
production path and it is not how this VM should run consequential actions
once `WHITEPACT_ENV=production` is deliberately set for a disposable test.

## 3. Network egress

Two layers, and neither replaces the other.

**Application.** `SafeNetworkBackend` blocks loopback, RFC1918, link-local,
CGNAT `100.64.0.0/10`, `169.254.169.254`, `fd00:ec2::254`, IPv6 ULA, and the
hostnames `localhost`, `metadata.google.internal`, and `metadata.internal`.
`create_safe_async_client` sets `trust_env=False`. A corporate or cloud HTTP
proxy injected by the environment does not become an allowlist. TLS
verification cannot be turned off in `SafeAsyncHTTPTransport`.

**Host.** Cloud-init installs a systemd unit that drops container TCP 80 and
443 to `169.254.169.254` and to `fd00:ec2::254`. DNS (UDP/TCP 53) to
`169.254.169.254` stays open because that address is the OCI resolver. The
security list mirrors that split: egress TCP 443 to the internet, and DNS
only to the resolver. There is no security-list entry for metadata HTTP.

Consequences:

- Do not set `HTTP_PROXY` or `ALL_PROXY` on the dashboard or MCP containers
  expecting SafeNetworkBackend to honor them. It will not, and a transparent
  proxy would also break IP pinning.
- Do not give the application an OCI instance-principal. The metadata block
  is pointless if the app holds a cloud credential another way.
- Host egress to TCP 443 is broad because image pulls and apt require it.
  That is the host, not the sandbox. Sandboxes still have no network.
- The public IPv4 is a real exposure tradeoff against a paid NAT gateway.
  Ingress from the internet is not in the security list. A console change
  could add it. Record that as an open review item, not as a solved control.

## 4. Tenant separation

The schema isolates tenants in application queries (`org_id`,
`organization_id`, `tenant_id`) and in tests that reject cross-tenant
bootstrap. There is no PostgreSQL RLS policy in this repository. A database
role that can read the cluster can read every org.

| Placement | Tenant-separation consequence |
|---|---|
| Postgres on the candidate VM, synthetic orgs only | Same trust model as a single self-hosted dev database. Acceptable for security tests the operator runs. Not a customer boundary |
| Neon Free | Adds the vendor's staff and storage co-tenancy to the same shared-role problem. Synthetic migration tests only |
| Supabase / other shared free Postgres | Same rejection. Existing live reference deployment is out of scope and is not changed |
| Separate database per tenant | Not required by the schema and not free of operational cost. Not part of this candidate |
| R2 bucket | No tenant evidence, no field-encryption keys, no approval payloads |

`WHITEPACT_FIELD_ENCRYPTION_KEY` stays in the operator secret store. It is
not in Terraform, cloud-init, GitHub, or an example env file.

## 5. Controls this package does not weaken

- Auth default remains on (`WHITEPACT_AUTH_ENABLED` is not set false).
- Production mode still refuses SQLite. This candidate does not flip that.
- MCP allowed hosts are not widened to `*`.
- Gitleaks, CodeQL, dependency review, and the pinned-action check still run.
- No secret is added to git. `terraform.tfvars`, `*.pem`, and `*.key` are ignored under `infra/zero-budget/oci/`.
- DNS is untouched, so there is no new public name to defend or to roll back.

## 6. Controls this package does not create

- No live proof of the security list, the metadata drop, or Bastion. Those
  units exist as code. CLOUD-AG-02's "design-only" finding still applies to
  them until someone is authorized to run them.
- No customer KMS. Volumes use Oracle-managed encryption at rest, and the
  data attachment sets paravirtualized in-transit encryption. That is not a
  customer-managed key and it is not a compliance certification.
- No WAF, no Cloudflare Access JWT proof (CLOUD-AG-03), no load-balancer
  origin lock (CLOUD-AG-07).
- No claim that Always Free isolation equals a dedicated production account
  with paid private networking.
