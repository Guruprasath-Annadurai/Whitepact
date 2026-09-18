# Hosted MCP authentication incident response

This runbook covers WhitePact API keys, built-in hosted-MCP OAuth credentials,
and deployments that validate tokens from an external OIDC provider. Never put
raw credentials in tickets, chat, logs, evidence bundles, or command history.

## Immediate containment

1. Identify the tenant, subject/key ID, OAuth client ID, incident window, and
   affected MCP resource from `oauth_auth_events` and normal access logs. Do not
   copy Authorization headers.
2. Revoke the underlying WhitePact API key with the existing org-key revocation
   operation. OAuth access-token validation rechecks that key on every request,
   so its derived sessions fail closed immediately.
3. Revoke a known OAuth access or refresh token through `POST /oauth/revoke`.
   Revoking a refresh token revokes its entire rotation family. A replayed
   refresh token also revokes the family automatically.
4. Revoke the OAuth client in `oauth_clients` when the public client registration
   itself is suspect. This stops new authorizations and refreshes.
5. Preserve relevant database and platform logs under the incident-retention
   policy before cleanup or rotation.

## Credential-specific actions

- **OAuth user session:** revoke the underlying tenant key. This invalidates all
  access and refresh tokens derived from that subject without needing plaintext
  token values.
- **Known refresh token:** call the revocation endpoint over HTTPS. Treat every
  token in that refresh family as compromised.
- **API key:** revoke it by key ID in WhitePact, issue a new least-privilege key,
  deliver it through the approved secret channel, and confirm the old key is
  rejected. Never edit its stored hash.
- **Built-in OAuth tokens:** these are opaque random values, so there is no OAuth
  signing secret or signing key to rotate. If the random generator or database
  is suspected, revoke all OAuth credentials and clients, rotate underlying API
  keys, then redeploy before reauthorization.
- **External OIDC signing key:** use the identity provider's emergency key
  rotation procedure, publish the new JWKS, revoke affected provider sessions,
  and confirm WhitePact rejects tokens signed by the retired key. WhitePact does
  not store the IdP private signing key.

## Investigation

Review `oauth_auth_events` for registration, authorization, issuance, access,
denial, replay, and revocation events. Correlate by tenant, subject, client ID,
and time. The table intentionally contains no raw codes, API keys, access
tokens, refresh tokens, or pending request handles. Check for callback changes,
unusual authorization failures, refresh replay, cross-tenant attempts, and
unexpected tool usage. Escalate confirmed exposure under the security incident
and breach-notification procedures.

## Safe restoration

Create a dedicated VIEWER or ANALYST key in the intended isolated tenant,
reauthorize the ChatGPT connection, confirm OAuth metadata and the 401 challenge
over public HTTPS, then run `initialize`, `tools/list`, `resources/list`, and the
five OpenAI review tool probes. Confirm old API keys, old access tokens, and the
old refresh family remain rejected. Record only identifiers, hashes, timestamps,
and pass/fail evidence.
