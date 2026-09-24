# SDK acceptance (v1.3.1 RC)

**Harness:** `scripts/v131_sdk_cli_acceptance.py` (LOCAL)

| SDK | Version target | Result | Evidence |
| --- | --- | --- | --- |
| Python `rai-client` | 1.3.1 | **PASS** | Wheel build + fresh venv install + `from rai_client import RAIClient` |
| TypeScript `@responsibleai/client` | 1.3.1 | **PASS** | `npm ci` + `npm run build` (tsc) |
| Go `raiclient` | module in `sdk/go` | **PASS** | `go test ./...` + `go vet ./...` |

## Not exercised in this harness (honest gaps)

| Scenario | Status |
| --- | --- |
| Python SDK live authenticated HTTP against running dashboard | **DEGRADED** — import/install only; full retry/429/503 matrix needs dedicated integration job with server |
| TypeScript live request + typed errors against server | **DEGRADED** — compile/build only |
| Go live request against server | **DEGRADED** — module tests only |

**Classification rule:** PASS requires more than compilation; wheel/install/build tests satisfy minimum RC bar for packaging integrity. Live-server behavioral matrix remains **DEGRADED** pending scripted integration server fixture.
