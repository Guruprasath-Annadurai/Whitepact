# Exact free-tier resource allocation

These numbers are the prepared candidate. They are also the Terraform
defaults in `infra/zero-budget/oci/variables.tf`. Preflight fails if the
defaults drift. Nothing has been created.

Oracle's published Always Free Ampere allowance, as of 2026-10-09, is
**1,500 OCPU-hours and 9,000 GB-hours per month**, which Oracle describes as
**2 OCPUs and 12 GB** for an Always Free tenancy. Older WhitePact notes that
say "4 OCPU / 24 GB" describe the previous allowance and must not be used
for this design.

## Candidate VM (the only persistent allocation)

| Resource | Exact value | Published cap | Headroom left by this module |
|---|---|---|---|
| Shape | `VM.Standard.A1.Flex` | A1 flex only | Paid shapes are rejected by variable validation |
| Count | 1 instance | 1 or 2, totaling 2 OCPUs | A second A1 does not fit in the quota below |
| OCPU | 2 | 2 | 0. The quota statement sets `standard-a1-core-count` to 2 |
| Memory | 12 GB | 12 GB | 0. The quota statement sets `standard-a1-memory-count` to 12 |
| Boot volume | 50 GB | 200 GB combined boot + data | 100 GB unused after boot + data |
| Data volume | 50 GB | same 200 GB | Docker data root and Postgres live here |
| Volume backups | 0 | 5 | Do not enable backups until a retention rule exists |
| Public IPv4 | 1 ephemeral, primary VNIC | Included with the instance | No reserved public IP resource |
| Load balancer | none | 1 flexible at 10 Mbps | Omitted |
| NAT gateway | none | not Always Free | Omitted |
| VCN | 1 (`10.8.0.0/16`) | 2 on a Free Tier tenancy without trial credits | One left unused |
| Internet gateway | 1 | included with the VCN | Route `0.0.0.0/0` only |
| Bastion | 1 STANDARD | Oracle lists Bastion as free | Client CIDR is the operator, never `0.0.0.0/0` |
| Object storage | 0 | 20 GB combined on an Always Free-only account, or 10 GB per tier while trial credits exist | Do not store evidence here |
| Outbound data | image pulls and apt only | 10 TB/month | Far above dev use; still a cap, not an invitation |

Block arithmetic: 50 + 50 = 100 GB of 200 GB. Two further 50 GB volumes
would hit the cap. Deleting the instance with `preserve_boot_volume = false`
is required so a terminated boot volume does not keep consuming the 200 GB.

## Memory budget on the 12 GB guest

| Consumer | Allocation |
|---|---|
| Ubuntu + Docker daemon | 1.0 GB |
| PostgreSQL 16 | 1.0 GB working set (`shared_buffers` 256 MB) |
| Redis 7 | 0.25 GB |
| Dashboard, 1 uvicorn worker | 1.0 GB |
| MCP HTTP | 0.5 GB |
| One compliance sandbox | 0.5 GB (`ResourceLimits.max_memory_mb=512`) |
| One strict sandbox | 0.25 GB (default 256 MB) |
| Page cache and headroom | about 7.5 GB |

`WHITEPACT_WORKERS=4`, the `docker-compose.prod.yml` default, is not used.
Helm's 2 × 1 Gi dashboard limit plus 2 × 512 Mi MCP limit is not used.
Either choice would still fit in 12 GB and would erase the headroom the
sandbox tests need. The candidate stays at one worker.

CPU: the compliance sandbox asks for 1.0 CPU of the 2 OCPUs. That is
acceptable for a single interactive test and unacceptable as a concurrency
claim. Do not run a matrix of sandboxes in parallel on this VM.

## Disk budget on the 50 GB data volume

| Use | Planned |
|---|---|
| Docker data root (move it off the boot volume before the first image build) | 30 GB |
| Postgres data directory | 15 GB |
| Redis AOF | 1 GB |
| Free | 4 GB |

The WhitePact image is built from `python:3.12-slim` and `node:22-alpine`.
Both pinned index digests include `linux/arm64/v8`, as do
`postgres:16-alpine` and `redis:7-alpine` in `docker-compose.prod.yml`
(registry index inspected 2026-10-09). Building the application image on
ARM was not done in this pass. Do that only after authorization, and treat
a missing aarch64 wheel as a stop, not as a reason to switch to an AMD paid
shape.

## Process layout versus Helm

| Helm default | This candidate | Reason |
|---|---|---|
| Dashboard replicas 2, MCP replicas 2 | 1 and 1 | Always Free is one VM. A second VM would be another boot volume and would exceed the A1 quota if it also needed memory |
| Dashboard limit 1 CPU / 1 Gi | 1 worker, no second replica | Leaves RAM for the isolation sandbox |
| HPA max 10 | off | There is no cluster and no spare Always Free CPU |
| SQLite PVC 5 Gi when `databaseUrl` is empty | Postgres on the data volume | Production mode refuses SQLite. Dev on this VM still uses Postgres so migration tests match CI |
| NetworkPolicy disabled in values | Host security list + sandbox `--network=none` | There is no Kubernetes network policy controller on this VM |

## What GitHub Actions already allocates

No new runner size. The existing `test` job starts one `postgres:16-alpine`
container with user `wp`, database `whitepact_e2e`, published on port 55432.
Redis is not started. Tests that need Redis use an in-process fallback or
an in-memory fake. Docker-gated isolation tests use the runner daemon when
it is present.

## Temporary alternatives (not allocated)

These are ceilings to check later, not resources to create now.

| Path | Maximum this program would allow | Stop condition |
|---|---|---|
| GCP Free Trial VM | One `e2-standard-2` (2 vCPU, 8 GB) or smaller, standard disk ≤ 30 GB beyond the Always Free 30 GB-month only if the trial credit is paying, us region | Delete before the earlier of credit exhaustion and day 90. Do not upgrade billing |
| AWS credit VM | One Graviton instance with at least 4 GB RAM, one gp3 volume ≤ 50 GB, no NAT, no load balancer, no RDS | Delete, including volumes and addresses, before the credit expiry recorded in the billing console |
| Neon | One Free project, one branch, scale-to-zero left on | Delete the project at the end of the experiment. Storage does not reset monthly |
| Cloudflare R2 | One bucket, under 10 GB-month, synthetic objects | Empty and delete the bucket. Do not attach a payment method to raise the cap |

## Quota statements prepared, not applied

```text
set compute-core quota standard-a1-core-count to 2 in compartment <whitepact-dev>
set compute-memory quota standard-a1-memory-count to 12 in compartment <whitepact-dev>
```

Names match Oracle's Compute Quotas page (`standard-a1-core-count` in family
`compute-core`, `standard-a1-memory-count` in family `compute-memory`). The
compartment path is an input because a nested compartment must be written as
`parent:child`. A wrong name fails a future apply closed; it does not create
the instance first. Apply is still refused.
