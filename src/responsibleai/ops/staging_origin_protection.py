# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Inventory Cloudflare-to-origin client-certificate artifacts in the staging tree.

A nginx file with ssl_verify_client on is necessary and not sufficient. Staging
is not protected until the missing artifacts below are supplied outside this
offline check. This module does not call Cloudflare or start a listener.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ORIGIN_NGINX = REPO_ROOT / "deploy" / "origin" / "nginx-cloudflare-aop.conf"
STAGING_MAIN = REPO_ROOT / "infra" / "terraform" / "environments" / "staging" / "main.tf"
EDGE_DIR = REPO_ROOT / "infra" / "terraform" / "modules" / "cloudflare-edge"
FOUNDATION = REPO_ROOT / "infra" / "terraform" / "modules" / "whitepact-hetzner-foundation"

# These must all be present before the client-certificate control is enforced.
ENFORCEMENT_ARTIFACTS: tuple[str, ...] = (
    "origin_nginx_requires_client_certificate",
    "origin_config_staged_on_saas",
    "saas_listener_not_started_without_material",
    "staging_cloudflare_edge_module",
    "staging_authenticated_origin_pulls",
    "per_hostname_aop_certificate_resource",
    "cloudflare_aop_ca_bundle",
    "origin_server_certificate",
    "origin_server_private_key",
    "staging_proxied_dns_record",
    "staging_zone_tls_strict",
    "saas_nginx_package",
    "real_origin_hostname",
)


@dataclass(frozen=True)
class OriginArtifact:
    artifact_id: str
    state: str
    detail: str


def client_certificate_required(config: str) -> bool:
    """True only for a listener that rejects missing and optional client certificates."""
    if "ssl_verify_client on;" not in config:
        return False
    if "ssl_verify_client off" in config or "ssl_verify_client optional" in config:
        return False
    if "ssl_client_certificate" not in config:
        return False
    return True


def origin_protection_inventory(root: Path | None = None) -> tuple[OriginArtifact, ...]:
    repo = root or REPO_ROOT
    nginx_path = repo / "deploy" / "origin" / "nginx-cloudflare-aop.conf"
    staging = (repo / "infra" / "terraform" / "environments" / "staging" / "main.tf").read_text(
        encoding="utf-8"
    )
    edge = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (repo / "infra" / "terraform" / "modules" / "cloudflare-edge").glob("*.tf")
    )
    foundation = repo / "infra" / "terraform" / "modules" / "whitepact-hetzner-foundation"
    locals_text = (foundation / "locals.tf").read_text(encoding="utf-8")
    main_text = (foundation / "main.tf").read_text(encoding="utf-8")
    nginx = nginx_path.read_text(encoding="utf-8") if nginx_path.is_file() else ""
    items: list[OriginArtifact] = []

    def add(artifact_id: str, present: bool, detail: str) -> None:
        items.append(OriginArtifact(artifact_id, "present" if present else "missing", detail))

    add(
        "origin_nginx_requires_client_certificate",
        client_certificate_required(nginx),
        "deploy/origin/nginx-cloudflare-aop.conf must set ssl_verify_client on.",
    )
    add(
        "origin_config_staged_on_saas",
        "saas_origin_write_files" in locals_text
        and "nginx-cloudflare-aop.conf" in locals_text
        and "extra_write_files = local.saas_origin_write_files" in main_text,
        "SaaS cloud-init stages the origin nginx file. Authority and execution do not.",
    )
    runcmd_start = locals_text.find("saas_origin_runcmd")
    runcmd = locals_text[runcmd_start:] if runcmd_start >= 0 else ""
    add(
        "saas_listener_not_started_without_material",
        "ORIGIN_AOP_MATERIAL_MISSING" in runcmd and "nginx" not in runcmd.casefold(),
        "Cloud-init records missing certificate material and does not start nginx.",
    )
    add(
        "staging_cloudflare_edge_module",
        'source = "../../modules/cloudflare-edge"' in staging or 'module "edge"' in staging,
        "The staging root does not instantiate the Cloudflare edge module.",
    )
    add(
        "staging_authenticated_origin_pulls",
        "enable_authenticated_origin_pulls" in staging
        and "plan_allows_authenticated_origin_pulls" in staging,
        "Staging does not enable zone authenticated origin pulls.",
    )
    add(
        "per_hostname_aop_certificate_resource",
        "cloudflare_authenticated_origin_pulls_certificate" in edge,
        "The edge module has no per-hostname authenticated origin pull certificate.",
    )
    add(
        "cloudflare_aop_ca_bundle",
        (repo / "deploy" / "origin" / "cloudflare-aop-ca.pem").is_file(),
        "The Cloudflare client CA bundle is not in the staging tree.",
    )
    add(
        "origin_server_certificate",
        (repo / "deploy" / "origin" / "server.crt").is_file(),
        "The origin certificate is not provisioned.",
    )
    add(
        "origin_server_private_key",
        False,
        "The origin private key must be supplied from the operator secret store and must not be committed.",
    )
    add(
        "staging_proxied_dns_record",
        "cloudflare_record" in staging,
        "Staging does not plan a proxied DNS record. DNS stays unchanged.",
    )
    add(
        "staging_zone_tls_strict",
        "cloudflare_zone_settings_override" in staging or 'ssl              = "strict"' in staging,
        "Staging does not apply Full (strict) zone TLS.",
    )
    cloud_init = (foundation / "templates" / "cloud-init-nftables.yaml").read_text(encoding="utf-8")
    add(
        "saas_nginx_package",
        "nginx" in cloud_init and "packages:" in cloud_init,
        "The Ubuntu image cloud-init does not install nginx. Package install also needs an approved mirror CIDR.",
    )
    add(
        "real_origin_hostname",
        "server_name staging.example.invalid" not in nginx and "server_name " in nginx,
        "The origin server_name is still the staging.example.invalid placeholder.",
    )
    return tuple(items)


def missing_artifact_ids(items: tuple[OriginArtifact, ...] | None = None) -> tuple[str, ...]:
    inventory = items if items is not None else origin_protection_inventory()
    return tuple(item.artifact_id for item in inventory if item.state == "missing")


def origin_client_certificate_enforced(items: tuple[OriginArtifact, ...] | None = None) -> bool:
    inventory = items if items is not None else origin_protection_inventory()
    by_id = {item.artifact_id: item.state for item in inventory}
    return all(by_id.get(artifact_id) == "present" for artifact_id in ENFORCEMENT_ARTIFACTS)
