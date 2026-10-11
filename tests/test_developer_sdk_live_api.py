# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real TCP + disposable PostgreSQL SDK journey, not a mock transport.

Explicit root/consent fixture records are local test setup, not hosted issuance.
This is development proof, not production isolation or qualification evidence.
"""

from __future__ import annotations

import asyncio
import json
import socket
import sys
from datetime import datetime
from pathlib import Path

import httpx
import pytest
import uvicorn

import responsibleai.dashboard.app as dashboard
from responsibleai.db.policy_repository import PolicyRepository
from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.policy import PolicyRule
from responsibleai.governance.synthetic_counter import SYNTHETIC_COUNTER_TOOL
from tests.org_http_fixtures import seed_org_with_key
from tests.pg_test_url import isolated_pg_url
from tests.test_v1_customer_journey import _upgrade_head

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "sdk" / "python"))
from rai_client.governance import GovernanceRequestError, GovernanceRuntimeClient  # noqa: E402


async def _typescript_call(origin: str, key: str, *, fail_after_effect: bool = False) -> dict:
    example = Path(__file__).resolve().parents[1] / "sdk/typescript/examples/governed-call.mjs"
    script = """
      const {runGovernedCall} = await import(process.argv[1]);
      let input = ''; for await (const chunk of process.stdin) input += chunk;
      console.log(JSON.stringify(await runGovernedCall(JSON.parse(input))));
    """
    process = await asyncio.create_subprocess_exec(
        "node",
        "--input-type=module",
        "-e",
        script,
        example.as_uri(),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    payload = json.dumps(
        {
            "baseUrl": origin,
            "apiKey": key,
            "name": SYNTHETIC_COUNTER_TOOL,
            "purpose": "automated-test",
            "arguments": {"fail_after_effect": fail_after_effect},
        }
    ).encode()
    stdout, stderr = await asyncio.wait_for(process.communicate(payload), timeout=15)
    assert process.returncode == 0, stderr.decode().replace(key, "[REDACTED]")[:1000]
    return json.loads(stdout)


@pytest.mark.asyncio
async def test_sdk_real_tcp_governance_journey(monkeypatch, seed_runtime_authority):
    async for url in isolated_pg_url("wp_sdk_live"):
        await _upgrade_head(url)
        monkeypatch.setattr(dashboard.settings, "database_url", url)
        monkeypatch.setattr(dashboard.settings, "auto_migrate", False)
        monkeypatch.setattr(dashboard.settings, "auth_enabled", True)
        monkeypatch.setattr(dashboard.settings, "environment", "development")
        monkeypatch.setattr(dashboard.limiter, "enabled", False)
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        origin = f"http://127.0.0.1:{sock.getsockname()[1]}"
        server = uvicorn.Server(
            uvicorn.Config(dashboard.app, log_level="critical", access_log=False)
        )
        task = asyncio.create_task(server.serve(sockets=[sock]))
        try:
            async with asyncio.timeout(30):
                while not server.started:
                    if task.done():
                        await task
                        raise AssertionError("Local application did not start")
                    await asyncio.sleep(0.01)
            org_id, key_id, key = await seed_org_with_key(name="SDK local", slug="sdk-local")
            sdk = GovernanceRuntimeClient(key, base_url=origin, timeout=5)
            rejected = GovernanceRuntimeClient("invalid-local-test-key", base_url=origin)
            with pytest.raises(GovernanceRequestError) as auth:
                await rejected.list_approvals()
            assert auth.value.status_code == 401
            denied = await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose="automated-test")
            assert denied.denied and not denied.completed
            assert (await _typescript_call(origin, key))["denied"] is True
            await seed_runtime_authority(
                dashboard._db_engine,
                organization_id=org_id,
                principal_id=key_id,
                action_types=(SYNTHETIC_COUNTER_TOOL,),
                targets=(SYNTHETIC_COUNTER_TOOL,),
                purpose="automated-test",
            )
            policies = PolicyRepository(dashboard._db_engine)
            await policies.add_rule(
                org_id,
                PolicyRule(
                    rule_id="sdk-approval",
                    reason_code="SDK_TEST_REQUIRES_APPROVAL",
                    effect=GovernanceDecision.REQUIRE_APPROVAL,
                    action_types=frozenset({SYNTHETIC_COUNTER_TOOL}),
                ),
            )
            pending = await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose="automated-test")
            assert pending.requires_approval and not pending.completed
            assert pending.approval_id
            ts_pending = await _typescript_call(origin, key)
            assert ts_pending["requiresApproval"] and not ts_pending["completed"]
            assert any(
                item["approval_id"] == pending.approval_id
                for item in (await sdk.list_approvals())["pending"]
            )
            # A fresh ALLOW invocation is distinct from approving/resuming the pending action.
            await policies.remove_rule(org_id, "sdk-approval")
            allowed = await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose="automated-test")
            assert allowed.completed and allowed.raw["result"]["ok"] is True
            assert (await _typescript_call(origin, key))["completed"] is True
            uncertain = await sdk.call_tool(
                SYNTHETIC_COUNTER_TOOL,
                {"fail_after_effect": True},
                purpose="automated-test",
            )
            assert uncertain.reconciliation_required and not uncertain.completed
            ts_uncertain = await _typescript_call(origin, key, fail_after_effect=True)
            assert ts_uncertain["uncertain"] and not ts_uncertain["completed"]
            async with httpx.AsyncClient(base_url=origin) as client:
                response = await client.get(
                    "/api/governance/evidence",
                    headers={"Authorization": f"Bearer {key}"},
                )
                assert response.status_code == 200
                records = (await sdk.list_evidence())["evidence"]
                assert any(record["decision"] == "ALLOW" for record in records)
                assert all(record["organization_id"] == org_id for record in records)
                snapshot = await client.get(
                    "/api/v1/governance/test-counter",
                    headers={"Authorization": f"Bearer {key}"},
                )
                # Two successes plus two uncertain effects, with no SDK automatic retry.
                assert snapshot.json()["counter"] == 4
                assert snapshot.json()["downstream_call_count"] == 4
                # Backend exposes an attestation, NOT the standalone detail route the SDK assumes.
                evidence_id = records[0]["evidence_id"]
                attestation = await client.get(
                    f"/api/governance/evidence/{evidence_id}/attestation",
                    headers={"Authorization": f"Bearer {key}"},
                )
                assert attestation.status_code == 200
                sdk_attestation = await sdk.get_attestation(evidence_id)
                direct_attestation = attestation.json()
                assert datetime.fromisoformat(sdk_attestation.pop("attested_at"))
                assert datetime.fromisoformat(direct_attestation.pop("attested_at"))
                assert sdk_attestation == direct_attestation
                with pytest.raises(GovernanceRequestError) as missing_detail:
                    await sdk.get_evidence(evidence_id)
                assert missing_detail.value.status_code == 404
            await sdk.revoke_delegation(key_id, reason="Local journey finished")
            revoked = await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose="automated-test")
            assert revoked.denied and not revoked.completed
            assert (await _typescript_call(origin, key))["denied"] is True
        finally:
            server.should_exit = True
            await asyncio.wait_for(task, timeout=30)
            sock.close()
