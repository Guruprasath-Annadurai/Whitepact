# Infrastructure architecture

Authorization gate: **CLOSED**. This is the candidate shape, not a running system.

```text
                    tests that do not need a cloud
                    +----------------------------------+
                    | GitHub Actions (public repo)     |
                    | ubuntu-latest + postgres:16      |
                    | lint, unit, migration, scans     |
                    +----------------------------------+

                    optional synthetic SQL only
                    +----------------------------------+
                    | Neon Free (one project)          |
                    | suspends after 5 min; 1 GB       |
                    | not an authority database        |
                    +----------------------------------+

  operator laptop -- OCI Bastion (Always Free) --> SSH
                                                      |
                                                      v
                    +-----------------------------------------------+
                    | OCI home region, one VCN 10.8.0.0/16         |
                    | subnet 10.8.1.0/24                            |
                    | internet gateway (free)                       |
                    | security list: no internet ingress            |
                    |                                               |
                    | VM.Standard.A1.Flex                           |
                    | 2 OCPU, 12 GB, Ubuntu aarch64                 |
                    | ephemeral public IPv4 for outbound only       |
                    | 50 GB boot + 50 GB data                       |
                    |                                               |
                    | docker compose:                               |
                    |   postgres:16  (internal network only)        |
                    |   redis:7      (internal network only)        |
                    |   dashboard    127.0.0.1:8765  workers=1      |
                    |   mcp-http     127.0.0.1:8766                 |
                    |   sandbox      --network=none, 256 or 512 MB  |
                    +-----------------------------------------------+
                                      |
                                      | HTTPS 443 outbound
                                      v
                    Ubuntu archives, image registries, git

                    not in this design
                    +----------------------------------+
                    | NAT gateway, load balancer       |
                    | production DNS, Cloudflare zone  |
                    | GCP e2-micro as the host         |
                    | AWS as the persistent host       |
                    +----------------------------------+
```

## Why the pieces are split

GitHub Actions is the default test plane. The repository already runs the
suite, including PostgreSQL 16, without a standing VM. Adding a cloud
database under CI would spend Neon CU-hours and would put synthetic-test
credentials into GitHub. That is rejected.

The OCI VM is the only persistent candidate that meets the memory floor
inside a published Always Free allowance. Helm's two dashboard replicas
plus two MCP replicas are not part of this candidate. High availability is
a paid-capacity problem. `DEPLOY_RUNBOOK.md` already says 2 vCPU / 4 GB is
below the hosted SLA recommendation; this VM is 2 OCPU / 12 GB, which clears
the dev floor and still does not clear that SLA.

Google Cloud and AWS appear only as temporary, credit-backed alternatives
if OCI has no Ampere capacity in the home region. They are not provisioned
and they are not the architecture of record. Using them requires a dated
shutdown before credits expire. See the risk register.

Neon and Cloudflare are test dependencies with explicit non-roles:

- Neon may hold a disposable schema for migration experiments. It is not
  the authority database, because a managed free database is shared
  infrastructure and WhitePact has no PostgreSQL row-level security.
- Cloudflare may hold test objects in R2 and may exercise Workers limits.
  It does not terminate production DNS, and a Worker does not become a
  second governance engine.

## Compute and data plane on the candidate VM

| Process | Bind | Notes |
|---|---|---|
| PostgreSQL 16 | Docker network `rai-internal` only | Same engine as `docker-compose.prod.yml`. No host port |
| Redis 7 | Docker network `rai-internal` only | Rate-limit counters. Authority remains in Postgres |
| Dashboard | `127.0.0.1:8765` | `WHITEPACT_WORKERS=1` so a compliance sandbox still fits |
| MCP HTTP | `127.0.0.1:8766` | Not published beyond the host |
| Isolation sandbox | `--network=none` | `DockerContainerBackend` in `src/responsibleai/isolation/container_backend.py` |

The operator reaches the host through OCI Bastion, which Oracle lists as free.
The instance security list allows TCP 22 only from the VCN CIDR. It does not
allow TCP 22, 80, 443, 8765, or 8766 from the internet.

Outbound internet uses an ephemeral public IPv4 and the free internet
gateway. A private subnet plus NAT gateway would hide that address, and the
NAT gateway is a paid resource, so it is excluded. Unsolicited inbound
packets are dropped by the stateful security list. That is weaker than a
private subnet: a later console edit could open a port. The prepared module
does not contain such a rule, and preflight rejects an ingress source of
`0.0.0.0/0`. This gap is the same class as CLOUD-AG-02; it is not closed.

## What stays inside WhitePact

Cloud IAM, OCI Bastion, and Cloudflare Access are operator access paths.
They are not `WhitePactRuntimeGateway`. Governance decisions remain the
in-process deterministic engine. Phase 3's rule stands: the platform
operator does not bootstrap a customer's trust root
(`docs/security/PHASE3_GLOBAL_TRUST_FABRIC_CLOSURE.md`). Sovereign surfaces
read and simulate; they do not become the authority
(`docs/sovereign/ARCHITECTURE.md`).

Sandbox egress stays impossible at the container (`--network=none`).
Control-plane HTTP egress stays in `src/responsibleai/net/egress.py`
(`SafeNetworkBackend`): public destinations only by default, metadata
addresses rejected, `trust_env=False` so `HTTP_PROXY` is ignored, TLS
verification not disableable. The VM cloud-init unit drops container TCP
80/443 to `169.254.169.254` and to `fd00:ec2::254` without dropping DNS to
the OCI resolver on port 53.

Tenant rows stay in one Postgres on this VM for a single dev tenant set.
That matches the application, which isolates by `org_id` and does not
enable RLS. It is not an enterprise claim that a shared free database
separates customers. Customer data does not go on this VM, on Neon, or in
R2.

## Explicit non-architecture

- No production cutover and no change to `whitepact-mcp-http.onrender.com`.
- No DNS record.
- No load balancer in front of 8765 or 8766.
- No replica of the Helm chart's HPA, PDB, or 2+2 replica defaults.
- No Phase 7A worker fleet. The dispatcher is a gated stub and production refuses to start it.
- No use of this module to "finish" the blocked enterprise cloud design.
