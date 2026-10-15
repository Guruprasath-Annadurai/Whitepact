# Local first-run preflight: configuration, not customer authority

Run from a trusted source checkout using Python 3.11 or newer:

```sh
python3 scripts/developer/first_run.py
```

This standalone standard-library command reads the current process environment.
It prints only fixed JSON check names/statuses and exits 0 for a configuration
preflight pass, 2 otherwise. It does not load `.env`, invoke Docker, install
packages, resolve DNS, connect to a database, run migrations, create users,
write files, issue grants or call governance tools. It deliberately does not
print credentials, URLs, user-supplied variable names, filesystem paths or parser
exceptions. A pass is **not** a connection, migration, tool-version, security,
production-readiness or customer-onboarding qualification.

## Prepare an isolated environment

Use a dedicated local PostgreSQL and Redis instance with dedicated ports,
databases and randomly generated local-only credentials. Do not point these
instructions at managed/cloud/production services. Set the following through
your approved private runtime environment mechanism; do not paste secrets into
committed examples, shell history, tickets or test output:

| Setting | Required shape for this preflight |
| --- | --- |
| `WHITEPACT_DATABASE_URL` | `postgresql://<local-user>:<private-password>@127.0.0.1:<local-port>/<dedicated-db>` |
| `WHITEPACT_REDIS_URL` | `redis://127.0.0.1:<local-port>/0` (local authentication may be added) |
| `WHITEPACT_API_KEYS` | Fresh private local API key(s), never a production key |
| `WHITEPACT_ENV` | `development` or another explicit non-production environment |
| `WHITEPACT_AUTH_ENABLED` | `true` |
| `PHASE7A_DISPATCHER_ENABLED` | `false` |

PostgreSQL precedence in dashboard configuration is `WHITEPACT_DATABASE_URL`,
`DATABASE_URL`, `RAI_DATABASE_URL`; the diagnostic rejects unsafe values even in
shadowed aliases. Redis aliases are `WHITEPACT_REDIS_URL`, `RAI_REDIS_URL`.
Case-insensitive duplicate settings with different values are rejected.
API keys follow the actual server's comma-separated `NoDecode` contract, not
JSON-array decoding. Comma/whitespace-only strings contain no key. An explicitly
empty `WHITEPACT_API_KEYS` does not fall back to `RAI_API_KEYS`. A JSON-looking
value such as `[]` is a literal key under this parser, not an empty array; do
not use it as an example credential. The check confirms configuration presence
only, not key strength, server acceptance or authenticated principal authority.
Loopback literals and `localhost` are accepted; query/fragment overrides and
remote/private-network hosts are not. Loopback configuration alone does not
prove the service listening there belongs to your isolated development stack.
Docker, Git, Node and npm checks prove PATH presence only, not executable version,
daemon health or dependency integrity. Python's running version is checked.

### Concrete isolated PostgreSQL recipe (operator-run, not executed evidence)

This recipe uses the exact PostgreSQL image pinned by
`.github/workflows/m12p-product-review.yml` and `.github/workflows/ci.yml`.
It has not been executed as part of this documentation change. First-run time
under ten minutes has **not** been measured; image pulls and dependency installs
vary. Check that Docker is already installed and running:

```sh
docker version --format '{{.Server.Version}}'
```

Create a private directory outside the checkout and an initially empty private
environment file. These commands do not generate or print credentials:

```sh
mkdir -p "$HOME/.config/whitepact-m12p"
chmod 700 "$HOME/.config/whitepact-m12p"
touch "$HOME/.config/whitepact-m12p/postgres.env"
chmod 600 "$HOME/.config/whitepact-m12p/postgres.env"
```

Using your trusted local editor, populate `postgres.env` with exactly
`POSTGRES_USER=whitepact_m12p`, `POSTGRES_DB=whitepact_m12p`, and
`POSTGRES_PASSWORD=` followed by a freshly generated private random password.
Do not use an example password, `trust` authentication, a production credential,
or a shell command containing the password. Use a password-manager generator or
equivalent secure local mechanism; a long random hexadecimal password avoids
URL-escaping ambiguity. The file is Docker env-file syntax, not a script to
source. Do not print it. Docker administrators can inspect container environment,
so the local Docker daemon and its administrators are part of the trusted setup.

Choose an unused dedicated port. The following recipe reserves **55439**, not
the repository CI service port. It creates one dedicated named container and
volume; if the name/port already exists, inspect ownership first and do not
delete or replace another workload:

```sh
docker run --detach --name whitepact-m12p-postgres \
  --publish 127.0.0.1:55439:5432 \
  --env-file "$HOME/.config/whitepact-m12p/postgres.env" \
  --mount type=volume,source=whitepact-m12p-postgres-data,target=/var/lib/postgresql/data \
  --health-cmd 'pg_isready -U whitepact_m12p -d whitepact_m12p' \
  --health-interval 5s --health-timeout 3s --health-retries 20 \
  postgres:16-alpine@sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685
```

Inspect only non-secret health, version and loopback port output:

```sh
docker inspect --format '{{.State.Health.Status}}' whitepact-m12p-postgres
docker exec whitepact-m12p-postgres postgres --version
docker exec whitepact-m12p-postgres pg_isready -U whitepact_m12p -d whitepact_m12p
docker port whitepact-m12p-postgres 5432
```

`pg_isready` proves readiness, **not** password-authentication or migration
success. Set the runtime database URL privately using the same password and
`127.0.0.1:55439/whitepact_m12p`, then execute the migration checks below to
exercise actual application-driver authentication. PostgreSQL initialization
environment applies only to a fresh volume; editing `postgres.env` does not
rotate credentials in an existing database. This dedicated local database uses
the image's initialization user; it is not a production least-privilege design.

**Redis prerequisite remains manual:** use an independently isolated loopback
Redis instance with authentication configured through a private server config
or ACL file, and put its credentials in the private runtime URL. Do not put a
Redis password into `docker run` arguments, command history or logs. Do not use
a remote Upstash/production service or assume a stock unauthenticated Redis
container is an acceptable substitute. This recipe deliberately does not
invent a portable private ACL/volume ownership setup. Verify Redis's installed
version and `PING` using your authenticated local administration mechanism
without placing the password on the command line. The diagnostic checks URL
shape only; Redis connectivity/authentication remains separately unverified.

To pause only this dedicated PostgreSQL container while retaining its database:

```sh
docker stop whitepact-m12p-postgres
docker start whitepact-m12p-postgres
```

Do not run broad container/volume cleanup or remove
`whitepact-m12p-postgres-data`. Discarding local database state requires a
separate explicit operator decision. No cloud services or paid resources are
created by this recipe.

For a source install, create a dedicated virtual environment and install the
checkout, rather than assuming published package and checkout versions match:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dashboard,postgres,redis]'
```

After independently confirming that the configured database is your isolated
local database, the existing migration/application entry points are:

```sh
alembic upgrade head
uvicorn responsibleai.dashboard.app:app --host 127.0.0.1 --port 8765
```

These two commands **do mutate the local database / start a service**; they are
not executed by the preflight. Verify the actual migration head using
`alembic current` and the repository's `alembic heads`; do not assume a frozen
numeric revision from older release instructions. Authentication stays enabled.
Keep the dispatcher disabled and Gate B closed. Do not expose the development
server publicly as part of this workflow.

## Customer root / consent limitation

Starting a server and configuring an API key does not provision organizational
root authority, consent or a customer's legitimate agent lifecycle. The
diagnostic always reports `customer_execution_ready: false` and
`customer_root_consent: NOT_VERIFIED_REQUIRES_REVIEWED_PROVISIONING`.
Use the security owner's reviewed provisioning contract when available. Do not
seed authority rows, disable authentication, fabricate consent or repurpose test
fixtures as genuine customer onboarding.

`whitepact faststart` is an existing local doctrine demonstration, including a
synthetic approval. It is not an authenticated customer execution journey and
must remain labelled as such. Repository SDK tests using transports/fixtures
prove consumer behavior, not production authority or OS containment.

## Supported SDK boundary and uncertainty

Install the Python SDK separately from its actual source package directory:

```sh
python -m pip install -e ./sdk/python
```

The platform distribution does not install the `rai_client` SDK package. This
guide does not start MCP; if using the separately documented MCP entry points,
install the platform's supported `mcp` extra as well.

For a read-only authenticated evidence probe, configure
`WHITEPACT_DEVELOPER_URL` to your loopback origin and
`WHITEPACT_DEVELOPER_API_KEY` privately to a valid local test principal's key:

```sh
python examples/developer/m12p_governance_probe.py
```

The example constructs the actual `GovernanceRuntimeClient` and calls its
supported `list_evidence(limit=1)` GET endpoint. It emits only a fixed status,
never records or exception details, never invokes a tool, and never retries.
HTTP success is reported as `READ_RESPONSE_RECEIVED`, not execution permission
or evidence completeness. An empty bounded response is not complete history.
401/403 and transport failures are safe, distinct non-success results.

The Python consumer in `sdk/python/rai_client/governance.py` supplies
`GovernanceRuntimeClient.call_tool(name, arguments, purpose=...)`, which sends
`POST /api/v1/governance/tools/call` with the tool name, arguments and purpose;
it does not mint execution authority. Configure a real authenticated development
principal through supported flows before calling it. Do not invent an
`organization_id`, grant, price or entitlement in the client request.

Only `GovernanceToolOutcome.completed` indicates a completed response envelope.
Do not interpret absence of an error as success, treat UNKNOWN as ALLOW, or
automatically retry a consequential operation after a timeout/lost response.
Preserve the returned correlation/evidence identifiers when present and use
the existing authenticated evidence/approval surfaces for reconciliation.
If the backend cannot establish whether an effect occurred, remain uncertain;
the SDK does not supply a backend idempotency guarantee.

If independently authorized to execute a configured tool, the actual invocation
syntax is `await client.call_tool(name, arguments, purpose="operator-approved-purpose")`.
This is deliberately not executed by the example: a tool name or manifest alone
is not root authority, consent or permission. Missing authority must remain a
server denial, not be worked around with fixtures. Approval behavior can be
studied in labelled SDK contract tests; it is not a substitute for customer
provisioning.

## Regression command

```sh
python -m pytest --noconftest -o addopts='' -q tests/test_m12p_developer_first_run.py
```

`--noconftest` here isolates an offline, pure standard-library command from the
platform's global database fixtures. It is not a substitute for the platform's
real PostgreSQL, authentication, authority or customer-journey test suites.
