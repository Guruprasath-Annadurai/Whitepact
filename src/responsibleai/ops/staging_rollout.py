# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Staging rollout plans. This module has no terraform apply path."""

from __future__ import annotations

import re
from urllib.parse import urlparse

OWNER_GATE_TOKEN = "APPROVE_STAGING_CLOUD_PROVISIONING"
OWNER_GATE_PHRASE = "APPROVE STAGING CLOUD PROVISIONING"
_SHA = re.compile(r"^[0-9a-f]{40}$")


class StagingRolloutRefused(RuntimeError):
    """The requested rollout step is not authorized."""


def assert_owner_gate(token: str) -> None:
    if token != OWNER_GATE_TOKEN:
        raise StagingRolloutRefused("Owner gate token rejected.")


def plan_deploy(git_sha: str, token: str) -> dict[str, object]:
    """Return the commands an operator would run after a separate apply approval.

    terraform apply is intentionally absent.
    """
    assert_owner_gate(token)
    if _SHA.fullmatch(git_sha) is None:
        raise StagingRolloutRefused("SHA must be 40 lowercase hex characters.")
    return {
        "action": "plan",
        "git_sha": git_sha,
        "terraform_apply": False,
        "dns_change": False,
        "production": False,
        "billing_activation": False,
        "commands": [
            "terraform -chdir=infra/terraform/environments/staging init -backend=false",
            "terraform -chdir=infra/terraform/environments/staging validate",
            "terraform -chdir=infra/terraform/environments/staging plan -out=staging.plan",
            "alembic upgrade head",
        ],
        "migration": "planned_after_owner_apply",
        "note": "alembic upgrade head is the migration step to run on the staging database after an owner apply. This function does not execute it.",
    }


def plan_health(base_url: str | None) -> dict[str, object]:
    if not base_url:
        return {
            "status": "NOT_RUN",
            "live": False,
            "reason": "WHITEPACT_STAGING_HEALTH_URL is unset.",
            "checks": ["/livez", "/readyz"],
        }
    parsed = urlparse(base_url)
    host = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or not host:
        raise StagingRolloutRefused("Health checks require an https URL.")
    if host == "whitepact.com" or host.endswith(".whitepact.com") and "staging" not in host:
        raise StagingRolloutRefused("Refusing a production hostname for the staging health check.")
    return {
        "status": "PLANNED",
        "live": False,
        "url": base_url,
        "checks": [base_url.rstrip("/") + "/livez", base_url.rstrip("/") + "/readyz"],
        "note": "Planned only. This function does not open a connection.",
    }


def plan_rollback(previous_sha: str, failed_sha: str) -> dict[str, object]:
    if _SHA.fullmatch(previous_sha) is None or _SHA.fullmatch(failed_sha) is None:
        raise StagingRolloutRefused("Rollback SHAs must be 40 lowercase hex characters.")
    if previous_sha == failed_sha:
        raise StagingRolloutRefused("Rollback target must differ from the failed SHA.")
    return {
        "action": "rollback_plan",
        "execute": False,
        "previous_sha": previous_sha,
        "failed_sha": failed_sha,
        "steps": [
            "Stop traffic to the failed SHA at the origin. Do not change production DNS.",
            f"Redeploy the previous SHA {previous_sha} with the same staging gate.",
            "Run /livez and /readyz against the staging hostname.",
            "Confirm the failed SHA is not the load balancer target.",
            "Leave the failed database migration in place unless the owner approves a forward fix. Do not drop the active database.",
        ],
    }
