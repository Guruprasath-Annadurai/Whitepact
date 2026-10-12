# Go SDK — locally verified interfaces

Status: analytics/health client, not a runtime execution-authority client.
Use this module from a local clone. Published Go module/version retrieval is not
qualified here; the historical module namespace is preserved for compatibility.

```sh
cd sdk/go
go test -race ./...
go vet ./...
go build ./...
go run ./cmd/livecheck http://127.0.0.1:8765
```

Health is public and does not prove authentication. To exercise protected analytics,
privately configure `WHITEPACT_API_KEY` for a disposable authorized test tenant and run:

```sh
go run ./cmd/livecheck http://127.0.0.1:8765 --analytics
```

Do not put credentials in command arguments or repository files. The smoke CLI
reads only `WHITEPACT_API_KEY`; its URL argument is optional and otherwise defaults
to `http://127.0.0.1:19595`. Library `Options` remain explicit configuration;
the library does not silently read environment credentials. Credential arguments
previously accepted by the smoke utility are now rejected.

`Scan` uses `/api/v1/scan`; `AnalyzeHallucination` uses `/api/v1/hallucination`,
matching the existing backend's version middleware and routes. A scan requires an
explicit boolean `is_blocked`; missing/null/string decisions are errors, not safe
results. Hallucination output is heuristic consistency analysis, not truth proof
or canonical execution risk. Legacy optional fields may be absent in server output.

Default timeout is30seconds. A negative timeout is invalid and fails before network
dispatch. Caller context cancellation remains honored. Redirects are refused;
credential-bearing URL userinfo and unsupported protocols are rejected. No mutation
retry is added. HTTP error bodies redact the configured key before truncation; this
is not general secret discovery. TLS verification is not disabled.

Real acceptance uses an authenticated localhost application with migrated disposable
PostgreSQL, valid/missing/incorrect/revoked synthetic credentials and a Go binary
built from this tree. These analytics calls do not prove governance execution,
approval resumption or isolated side effects. Go governance helpers remain UNSUPPORTED;
do not fall back to direct execution when another governance surface denies an action.

Production remains NO-GO pending independent qualification and explicit authorization.
