# Global website delivery identity and release gate

Repository baseline: `52d9b3c5497af24bb7d4a7147e33deaadc64296e`.
This is a local source investigation, not a deployment record. No deployment,
hosting configuration change, credential change, push or production retirement
is authorized or performed by this document.

## Observed delivery mismatch

The current browser audit supplied for this phase reports that the public root
still displays the ResponsibleAI legacy shell and a missing Authorization error.
The deployed source SHA, image digest, hosting build identity, startup command,
runtime configuration and proxy route map are unknown. Hosting credentials are
unavailable. The older `docs/phase1/PADDLE_PRODUCTION_DEPLOYMENT_REPORT.md`
independently records a historical legacy root and missing public legal routes;
that report is not proof of today's deployment identity.

Stale deployment is a hypothesis, not a demonstrated cause. A different image,
startup module, mounted asset directory, host/path mapping, proxy upstream or
cached response could also explain a difference. A frontend API error does not
establish that the root HTML request itself required authentication.

## Source route and packaging trace

| Evidence | Source behavior / implication |
|---|---|
| `src/responsibleai/dashboard/app.py`, `_static_dir` | Resolves `Path(__file__).parent / "static"`, beside the imported Python package. |
| Same file, `root()` | `/` reads `whitepact/pages/home.html`; public corporate content must load anonymously. |
| Same file, commerce and SPA route maps | Legal/pricing static pages and public SPA entry routes are separate from authenticated account/workspace API operations. `/dashboard` loads a shell; protected data still requires its existing verified session. |
| `Dockerfile`, `web-builder` and wheel builder | Builds `web/` with `sdk/` and `contracts/`, copies generated assets into `src/responsibleai/dashboard/static/whitepact/`, then builds the wheel. |
| `pyproject.toml`, wheel target | Includes `src/responsibleai` as a package; actual wheel asset bytes must be checked in the release artifact. |
| `Dockerfile`, runtime stage | Installs that wheel, separately copies checkout static files into `/app/static/`, then starts `uvicorn responsibleai.dashboard.app:app`. |

For this entrypoint, package-relative assets are the source of truth. The separate
`/app/static/` copy is not the directory selected by `_static_dir`; replacing it
alone does not establish that the installed application serves changed bytes.
The wheel's generated static files and checkout copy can differ. Confirm the
imported module path and served file hashes in the actual candidate image before
release; do not infer a packaging defect merely from the duplicate copy.

`helm/rai-governance/templates/deployment.yaml` selects an image tag and inherits
the image entrypoint, with ConfigMap/secret/`extraEnv` inputs and optional mounts.
`helm/rai-governance/values.yaml` contains example image/tag/host values; these are
not live hosting facts. `templates/ingress.yaml` forwards configured paths to the
service. `docker-compose.prod.yml` binds the dashboard to localhost for an
external TLS proxy. `scripts/phase0b/proxy_boundary_live.py` is a diagnostic nginx
harness, not evidence of the public host's routing configuration.

## Boundary and safe remediation

Serve corporate navigation, pricing inquiries, documentation, trust explanation
and legal information anonymously. Retain existing authentication and server
authorization for account, organization, credentials, billing and execution
operations. Do not put a machine API key in marketing JavaScript or weaken an
API check to clear a public-page error. Product kernel, authentication and
security changes are out of scope.

An owner/operator must first reconcile host → proxy route → service → immutable
image/build → source revision → imported package/static hashes. Build and inspect
the exact website candidate, verify anonymous HTML/assets and existing protected
API behavior locally, then obtain release authorization through the owner's
normal deployment process. Cache remediation requires proof of the affected
cache layer and correct origin content; purging alone is not a verified fix.

## Owner deployment identity gate — open

Required release evidence: authorized target/service owner; source SHA; build ID
and timestamp; immutable image digest when applicable; effective startup module;
package/static asset identity; effective mounts and configuration; proxy routing;
rollback identity; and post-release anonymous desktop/mobile/JavaScript-disabled
route checks. Protected API rejection behavior must remain intact.

Deployed identity: **UNKNOWN**. Root-cause attribution: **UNRESOLVED**.
Release authorization: **NOT ESTABLISHED**. Deployment performed: **NO**.
