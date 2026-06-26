"""v1.0 — Production Hardening tests.

Covers: API versioning middleware, OIDC module, support endpoints,
        auth provider listing, version endpoint.
"""

from __future__ import annotations

import base64
import json

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

# ── OIDC module unit tests ────────────────────────────────────────────────────

class TestJWTClaims:
    def test_from_payload_basic(self) -> None:
        from responsibleai.auth.oidc import JWTClaims
        p = {"sub": "user-1", "email": "a@b.com", "name": "Alice", "roles": ["admin"]}
        c = JWTClaims.from_payload(p)
        assert c.sub == "user-1"
        assert c.email == "a@b.com"
        assert c.name == "Alice"
        assert "admin" in c.roles

    def test_roles_as_string_coerced_to_list(self) -> None:
        from responsibleai.auth.oidc import JWTClaims
        c = JWTClaims.from_payload({"sub": "x", "roles": "viewer"})
        assert isinstance(c.roles, list)
        assert "viewer" in c.roles

    def test_groups_fallback(self) -> None:
        from responsibleai.auth.oidc import JWTClaims
        c = JWTClaims.from_payload({"sub": "x", "groups": ["ops"]})
        assert "ops" in c.roles

    def test_org_id_from_tenant_id(self) -> None:
        from responsibleai.auth.oidc import JWTClaims
        c = JWTClaims.from_payload({"sub": "x", "tenant_id": "t-42"})
        assert c.org_id == "t-42"

    def test_missing_optional_fields(self) -> None:
        from responsibleai.auth.oidc import JWTClaims
        c = JWTClaims.from_payload({"sub": "bare"})
        assert c.email is None
        assert c.name is None
        assert c.org_id is None
        assert c.roles == []

    def test_raw_payload_preserved(self) -> None:
        from responsibleai.auth.oidc import JWTClaims
        p = {"sub": "u", "custom_field": "xyz"}
        c = JWTClaims.from_payload(p)
        assert c.raw["custom_field"] == "xyz"

    def test_claims_frozen(self) -> None:
        from responsibleai.auth.oidc import JWTClaims
        c = JWTClaims.from_payload({"sub": "u"})
        with pytest.raises(AttributeError):
            c.sub = "other"  # type: ignore[misc]


class TestOIDCProviderUnverified:
    def _make_jwt(self, payload: dict) -> str:
        header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256"}).encode()).decode().rstrip("=")
        body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        return f"{header}.{body}.fakesig"

    @pytest.mark.asyncio
    async def test_decode_unverified_basic(self) -> None:
        from responsibleai.auth.oidc import OIDCProvider
        token = self._make_jwt({"sub": "user-99", "email": "x@y.com"})
        p = OIDCProvider("https://example.com", "client-id", skip_verification=True)
        claims = await p.validate_token(token)
        assert claims.sub == "user-99"
        assert claims.email == "x@y.com"

    @pytest.mark.asyncio
    async def test_malformed_jwt_raises(self) -> None:
        from responsibleai.auth.oidc import OIDCProvider
        p = OIDCProvider("https://example.com", "client-id", skip_verification=True)
        with pytest.raises(ValueError, match="Malformed JWT"):
            await p.validate_token("notajwt")

    @pytest.mark.asyncio
    async def test_bad_base64_raises(self) -> None:
        from responsibleai.auth.oidc import OIDCProvider
        p = OIDCProvider("https://example.com", "client-id", skip_verification=True)
        with pytest.raises(ValueError):
            await p.validate_token("aaa.!!!.bbb")

    def test_authorization_url_contains_client_id(self) -> None:
        from responsibleai.auth.oidc import OIDCProvider
        p = OIDCProvider("https://idp.example.com", "my-client", skip_verification=True)
        url = p.authorization_url("https://app/cb", "state-xyz", ["openid", "email"])
        assert "my-client" in url
        assert "state-xyz" in url
        assert "openid" in url

    def test_authorization_url_contains_redirect_uri(self) -> None:
        from responsibleai.auth.oidc import OIDCProvider
        p = OIDCProvider("https://idp.example.com", "c", skip_verification=True)
        url = p.authorization_url("https://myapp/callback", "s", ["openid"])
        assert "myapp" in url or "redirect_uri" in url


class TestAsyncJWKSClient:
    def test_constructor_sets_uri(self) -> None:
        from responsibleai.auth.oidc import AsyncJWKSClient
        c = AsyncJWKSClient("https://example.com/.well-known/jwks.json")
        assert c._uri == "https://example.com/.well-known/jwks.json"

    def test_initial_state_empty(self) -> None:
        from responsibleai.auth.oidc import AsyncJWKSClient
        c = AsyncJWKSClient("https://example.com/jwks")
        assert c._keys == []
        assert c._fetched_at == 0.0


# ── API versioning tests ───────────────────────────────────────────────────────

@pytest.fixture()
async def client():
    from responsibleai.dashboard.app import app
    async with LifespanManager(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c


class TestAPIVersionEndpoint:
    @pytest.mark.asyncio
    async def test_version_returns_200(self, client: AsyncClient) -> None:
        r = await client.get("/api/version")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_version_body(self, client: AsyncClient) -> None:
        r = await client.get("/api/version")
        d = r.json()
        assert d["version"] == "1.0.0"
        assert d["stable"] is True
        assert d["major"] == 1
        assert d["minor"] == 0
        assert d["patch"] == 0

    @pytest.mark.asyncio
    async def test_api_versions_list(self, client: AsyncClient) -> None:
        r = await client.get("/api/version")
        assert "1.0" in r.json()["api_versions"]

    @pytest.mark.asyncio
    async def test_x_api_version_header(self, client: AsyncClient) -> None:
        r = await client.get("/api/health")
        assert r.headers.get("x-api-version") == "1.0.0"

    @pytest.mark.asyncio
    async def test_v1_prefix_routes_to_health(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/health")
        assert r.status_code == 200
        assert r.json()["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_v1_prefix_routes_to_version(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/version")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_health_reports_stable_since(self, client: AsyncClient) -> None:
        r = await client.get("/api/health")
        d = r.json()
        assert d["stable_since"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_health_modules_includes_sso(self, client: AsyncClient) -> None:
        r = await client.get("/api/health")
        assert "sso_oidc" in r.json()["modules"]

    @pytest.mark.asyncio
    async def test_health_modules_includes_support(self, client: AsyncClient) -> None:
        r = await client.get("/api/health")
        assert "support" in r.json()["modules"]


# ── Support endpoints ─────────────────────────────────────────────────────────

class TestSupportEndpoints:
    @pytest.mark.asyncio
    async def test_support_info_200(self, client: AsyncClient) -> None:
        r = await client.get("/api/support")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_support_has_three_tiers(self, client: AsyncClient) -> None:
        r = await client.get("/api/support")
        d = r.json()
        assert len(d["tiers"]) == 3

    @pytest.mark.asyncio
    async def test_support_tier_names(self, client: AsyncClient) -> None:
        r = await client.get("/api/support")
        names = {t["name"] for t in r.json()["tiers"]}
        assert "Standard" in names
        assert "Professional" in names
        assert "Enterprise" in names

    @pytest.mark.asyncio
    async def test_support_enterprise_uptime(self, client: AsyncClient) -> None:
        r = await client.get("/api/support")
        ent = next(t for t in r.json()["tiers"] if t["name"] == "Enterprise")
        assert "99.9" in ent["uptime_sla"]

    @pytest.mark.asyncio
    async def test_support_has_contact(self, client: AsyncClient) -> None:
        r = await client.get("/api/support")
        assert "contact" in r.json()
        assert "email" in r.json()["contact"]

    @pytest.mark.asyncio
    async def test_platform_status_200(self, client: AsyncClient) -> None:
        r = await client.get("/api/support/status")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_platform_status_version(self, client: AsyncClient) -> None:
        r = await client.get("/api/support/status")
        assert r.json()["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_platform_status_operational(self, client: AsyncClient) -> None:
        r = await client.get("/api/support/status")
        assert r.json()["status"] in ("operational", "degraded")


# ── SSO / auth endpoints ───────────────────────────────────────────────────────

class TestAuthProviderEndpoints:
    @pytest.mark.asyncio
    async def test_list_providers_200(self, client: AsyncClient) -> None:
        r = await client.get("/api/auth/providers")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_api_key_provider_always_present(self, client: AsyncClient) -> None:
        r = await client.get("/api/auth/providers")
        ids = [p["id"] for p in r.json()["providers"]]
        assert "api_key" in ids

    @pytest.mark.asyncio
    async def test_oidc_provider_absent_when_not_configured(self, client: AsyncClient) -> None:
        r = await client.get("/api/auth/providers")
        ids = [p["id"] for p in r.json()["providers"]]
        assert "oidc" not in ids

    @pytest.mark.asyncio
    async def test_login_unknown_provider_404(self, client: AsyncClient) -> None:
        r = await client.get("/api/auth/login/nonexistent")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_login_oidc_without_config_404(self, client: AsyncClient) -> None:
        r = await client.get("/api/auth/login/oidc")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_callback_without_config_501(self, client: AsyncClient) -> None:
        r = await client.get("/api/auth/callback?code=c&state=s")
        assert r.status_code == 501

    @pytest.mark.asyncio
    async def test_logout_requires_auth_disabled(self, client: AsyncClient) -> None:
        r = await client.post("/api/auth/logout")
        assert r.status_code in (200, 401)


# ── Python SDK model tests ────────────────────────────────────────────────────

class TestPythonSDKModels:
    def test_trust_score_from_dict(self) -> None:
        from sdk.python.rai_client.models import TrustScore
        d = {
            "overall": 82.5,
            "grade": "B",
            "dimensions": {"fairness": 0.85, "privacy": 0.90, "security": 0.80,
                           "robustness": 0.75, "compliance": 0.88, "authenticity": 0.82},
            "model_name": "gpt-4o",
            "provider": "openai",
        }
        s = TrustScore.from_dict(d)
        assert s.overall == 82.5
        assert s.grade == "B"
        assert s.fairness == 0.85

    def test_guardrail_scan_from_dict(self) -> None:
        from sdk.python.rai_client.models import GuardrailScan
        d = {"is_blocked": True, "pii_findings": [{"category": "EMAIL", "value": "a@b.com", "start": 0, "end": 7}],
             "toxicity_score": 0.0, "redacted_text": "[REDACTED]"}
        scan = GuardrailScan.from_dict(d)
        assert scan.is_blocked
        assert len(scan.pii_findings) == 1
        assert scan.pii_findings[0].category == "EMAIL"

    def test_cost_record_from_dict(self) -> None:
        from sdk.python.rai_client.models import CostRecord
        d = {"request_id": "r1", "provider": "openai", "model": "gpt-4o",
             "input_cost_usd": 0.005, "output_cost_usd": 0.015, "total_cost_usd": 0.020}
        r = CostRecord.from_dict(d)
        assert r.total_cost == 0.020
        assert r.provider == "openai"

    def test_eval_compare_result_from_dict(self) -> None:
        from sdk.python.rai_client.models import EvalCompareResult
        d = {"winner": "model_a", "score_a": 75.0, "score_b": 68.0,
             "model_a": "gpt-4o", "model_b": "claude-3", "prompts_evaluated": 5}
        r = EvalCompareResult.from_dict(d)
        assert r.winner == "model_a"
        assert r.score_a == 75.0

    def test_hallucination_analysis_from_dict(self) -> None:
        from sdk.python.rai_client.models import HallucinationAnalysis
        d = {"hallucination_risk": 0.1, "risk_level": "low", "hedging_score": 0.05, "consistency_score": 0.95}
        a = HallucinationAnalysis.from_dict(d)
        assert a.risk_level == "low"
        assert a.consistency_score == 0.95


# ── Config OIDC settings ───────────────────────────────────────────────────────

class TestSettingsOIDC:
    def test_oidc_defaults_to_none(self) -> None:
        from responsibleai.dashboard.config import Settings
        s = Settings()
        assert s.oidc_issuer is None
        assert s.oidc_client_id == ""

    def test_oidc_scopes_default(self) -> None:
        from responsibleai.dashboard.config import Settings
        s = Settings()
        assert "openid" in s.oidc_scopes

    def test_oidc_scopes_parsed_from_string(self) -> None:
        from responsibleai.dashboard.config import Settings
        s = Settings(oidc_scopes="openid,email,profile,groups")
        assert "groups" in s.oidc_scopes
        assert len(s.oidc_scopes) == 4

    def test_oidc_redirect_uri_default(self) -> None:
        from responsibleai.dashboard.config import Settings
        s = Settings()
        assert "callback" in s.oidc_redirect_uri

    def test_oidc_skip_verification_default_false(self) -> None:
        from responsibleai.dashboard.config import Settings
        s = Settings()
        assert s.oidc_skip_verification is False
