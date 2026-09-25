# SDK live acceptance

Server: PostgreSQL + uvicorn @ `http://127.0.0.1:19595`

```json
{
  "python": {
    "valid_key": {
      "label": "valid",
      "health": {
        "status": "healthy",
        "version": "1.3.1",
        "uptime_seconds": 3.2,
        "timestamp": "2026-09-25T05:45:44.053891+00:00",
        "checks": {
          "database": "ok",
          "db_backend": "postgresql",
          "rate_limit_backend": "memory",
          "otel": "disabled",
          "auth": "enabled",
          "websocket_connections": 0,
          "webhooks_registered": 0,
          "orgs": 0
        },
        "modules": [
          "trust_score",
          "ai_passport",
          "guardrails",
          "hallucination",
          "compliance",
          "redteam",
          "cost_tracker",
          "cost_analyzer",
          "model_router",
          "drift_monitor",
          "websockets",
          "webhooks",
          "prometheus",
          "rbac",
          "orgs",
          "audit_log",
          "eval_compare",
          "eval_benchmarks",
          "eval_regression",
          "dataset_scan",
          "sso_oidc",
          "api_versioning",
          "support",
          "mcp_server",
          "billing"
        ],
        "api_versions": [
          "1.0",
          "1.1"
        ],
        "stable_since": "1.0.0"
      },
      "governed_action": "DENY_LEGACY_STATIC_KEY",
      "denial_detail": "{\"error\":\"http_error\",\"message\":\"Requires ANALYST role or higher. Your role: VIEWER\",\"status_code\":403,\"request_id\":\"d65cbbf7\"}",
      "status": "PASS"
    },
    "invalid_key": {
      "label": "invalid",
      "health": {
        "status": "healthy",
        "version": "1.3.1",
        "uptime_seconds": 3.2,
        "timestamp": "2026-09-25T05:45:44.078863+00:00",
        "checks": {
          "database": "ok",
          "db_backend": "postgresql",
          "rate_limit_backend": "memory",
          "otel": "disabled",
          "auth": "enabled",
          "websocket_connections": 0,
          "webhooks_registered": 0,
          "orgs": 0
        },
        "modules": [
          "trust_score",
          "ai_passport",
          "guardrails",
          "hallucination",
          "compliance",
          "redteam",
          "cost_tracker",
          "cost_analyzer",
          "model_router",
          "drift_monitor",
          "websockets",
          "webhooks",
          "prometheus",
          "rbac",
          "orgs",
          "audit_log",
          "eval_compare",
          "eval_benchmarks",
          "eval_regression",
          "dataset_scan",
          "sso_oidc",
          "api_versioning",
          "support",
          "mcp_server",
          "billing"
        ],
        "api_versions": [
          "1.0",
          "1.1"
        ],
        "stable_since": "1.0.0"
      },
      "auth_check": 401,
      "status": "PASS"
    },
    "connection_refused": {
      "label": "connection_refused",
      "status": "EXPECTED_FAIL",
      "error": "ConnectError",
      "message": "All connection attempts failed"
    },
    "secret_not_in_logs": true
  },
  "typescript": {
    "npm_install": {
      "cmd": [
        "npm",
        "install"
      ],
      "exit": 0,
      "stdout": "\nup to date, audited 4 packages in 344ms\n\nfound 0 vulnerabilities\n",
      "stderr": ""
    },
    "build": {
      "cmd": [
        "npm",
        "run",
        "build"
      ],
      "exit": 0,
      "stdout": "\n> @responsibleai/client@1.3.1 build\n> tsc\n\n",
      "stderr": ""
    },
    "live_health": {
      "cmd": [
        "node",
        "ts_live.mjs"
      ],
      "exit": 0,
      "stdout": "{\"ok\":true,\"health\":{\"status\":\"healthy\",\"version\":\"1.3.1\",\"uptime_seconds\":4.4,\"timestamp\":\"2026-09-25T05:45:45.235046+00:00\",\"checks\":{\"database\":\"ok\",\"db_backend\":\"postgresql\",\"rate_limit_backend\":\"memory\",\"otel\":\"disabled\",\"auth\":\"enabled\",\"websocket_connections\":0,\"webhooks_registered\":0,\"orgs\":0},\"modules\":[\"trust_score\",\"ai_passport\",\"guardrails\",\"hallucination\",\"compliance\",\"redteam\",\"cost_tracker\",\"cost_analyzer\",\"model_router\",\"drift_monitor\",\"websockets\",\"webhooks\",\"prometheus\",\"rbac\",\"orgs\",\"audit_log\",\"eval_compare\",\"eval_benchmarks\",\"eval_regression\",\"dataset_scan\",\"sso_oidc\",\"api_versioning\",\"support\",\"mcp_server\",\"billing\"],\"api_versions\":[\"1.0\",\"1.1\"],\"stable_since\":\"1.0.0\"}}\n",
      "stderr": "(node:611214) [MODULE_TYPELESS_PACKAGE_JSON] Warning: Module type of file:///workspace/sdk/typescript/dist/index.js is not specified and it doesn't parse as CommonJS.\nReparsing as ES module because module syntax was detected. This incurs a performance overhead.\nTo eliminate this warning, add \"type\": \"module\" to /workspace/sdk/typescript/package.json.\n(Use `node --trace-warnings ...` to show where the warning was created)\n"
    },
    "connection_refused": {
      "cmd": [
        "node",
        "ts_refused.mjs"
      ],
      "exit": 0,
      "stdout": "{\"ok\":false,\"name\":\"RAIError\"}\n",
      "stderr": "(node:611225) [MODULE_TYPELESS_PACKAGE_JSON] Warning: Module type of file:///workspace/sdk/typescript/dist/index.js is not specified and it doesn't parse as CommonJS.\nReparsing as ES module because module syntax was detected. This incurs a performance overhead.\nTo eliminate this warning, add \"type\": \"module\" to /workspace/sdk/typescript/package.json.\n(Use `node --trace-warnings ...` to show where the warning was created)\n"
    },
    "verdict": "PASS"
  },
  "go": {
    "test": {
      "cmd": [
        "go",
        "test",
        "./..."
      ],
      "exit": 0,
      "stdout": "?   \tgithub.com/Guruprasath-Annadurai/ResponsibleAi/sdk/go/cmd/livecheck\t[no test files]\n?   \tgithub.com/Guruprasath-Annadurai/ResponsibleAi/sdk/go/raiclient\t[no test files]\n",
      "stderr": ""
    },
    "vet": {
      "cmd": [
        "go",
        "vet",
        "./..."
      ],
      "exit": 0,
      "stdout": "",
      "stderr": ""
    },
    "live": {
      "cmd": [
        "go",
        "run",
        ".",
        "http://127.0.0.1:19595",
        "<bootstrap-api-key-redacted>"
      ],
      "exit": 0,
      "stdout": "{\"status\":\"healthy\",\"version\":\"1.3.1\",\"uptime_seconds\":4.9,\"timestamp\":\"2026-09-25T05:45:45.815320+00:00\",\"checks\":{\"auth\":\"enabled\",\"database\":\"ok\",\"db_backend\":\"postgresql\",\"orgs\":0,\"otel\":\"disabled\",\"rate_limit_backend\":\"memory\",\"webhooks_registered\":0,\"websocket_connections\":0},\"modules\":[\"trust_score\",\"ai_passport\",\"guardrails\",\"hallucination\",\"compliance\",\"redteam\",\"cost_tracker\",\"cost_analyzer\",\"model_router\",\"drift_monitor\",\"websockets\",\"webhooks\",\"prometheus\",\"rbac\",\"orgs\",\"audit_log\",\"eval_compare\",\"eval_benchmarks\",\"eval_regression\",\"dataset_scan\",\"sso_oidc\",\"api_versioning\",\"support\",\"mcp_server\",\"billing\"]}\n",
      "stderr": ""
    }
  }
}
```
