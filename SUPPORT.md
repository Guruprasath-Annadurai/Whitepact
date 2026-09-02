# Support

WhitePact (package name `rai-governance-platform`) is a founder-led
project (Guruprasath Annadurai) — support channels are scoped
honestly to what a single-maintainer project can actually staff, not
implied to be a 24/7 enterprise support desk that doesn't exist yet.

## Where to get help

- **Bugs and feature requests**: open a
  [GitHub issue](https://github.com/Guruprasath-Annadurai/Whitepact/issues) —
  the right place for anything reproducible or anything you want
  tracked publicly.
- **Security vulnerabilities**: **do not** open a public issue — see
  [SECURITY.md](SECURITY.md)'s reporting process
  (`annaduraiguruprasath7@gmail.com`, 48-hour acknowledgement target).
- **Questions about self-hosting, configuration, or general usage**:
  open a [GitHub Discussion](https://github.com/Guruprasath-Annadurai/Whitepact/discussions)
  if enabled on this repository, otherwise a GitHub issue tagged
  `question` — see the repository's issue templates.
- **Enterprise/hosted-tier support**: email
  `annaduraiguruprasath7@gmail.com` with your organization name and
  plan tier. `SLA.md` states the real, current response-time targets
  per tier — PRO and ENTERPRISE hosted customers get faster
  acknowledgement than the general community queue; FREE/self-hosted
  users should expect community-timescale response via GitHub issues,
  not a guaranteed SLA (`SLA.md` says this plainly too).

## What to include in a bug report

- WhitePact version (`pip show rai-governance-platform` or the
  `X-API-Version` response header) and deployment mode (self-hosted
  SQLite, self-hosted Postgres, or hosted).
- The exact request/response or command that reproduces the issue —
  redact any API key, OIDC token, or other credential before pasting
  it anywhere, including in a private email.
- Whether `enterprise_mode`/`mcp_governance_enabled` were on — several
  behaviors are deliberately different in that mode (see
  `docs/security/PRODUCTION_CONFIGURATION_STANDARD.md`).

## Response time expectations

Stated honestly, not aspirationally: this is not a company with a
support rotation. Community (GitHub issue) response time varies with
the maintainer's availability. `SLA.md`'s hosted-tier targets are the
only *committed* response times, and only for hosted PRO/ENTERPRISE
customers — everything else is best-effort.

## Related documents

- [SECURITY.md](SECURITY.md) — vulnerability disclosure
- [SLA.md](SLA.md) — uptime and support response-time targets by tier
- [CONTRIBUTING.md](CONTRIBUTING.md) — how to contribute a fix yourself
- [docs/operations/INCIDENT_RESPONSE.md](docs/operations/INCIDENT_RESPONSE.md) —
  how an in-progress incident is handled once reported
