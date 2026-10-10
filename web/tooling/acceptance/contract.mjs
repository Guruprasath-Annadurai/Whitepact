// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
export const checks = ['https', 'redirects', 'tls', 'headers', 'csp', 'hsts', 'canonical', 'robots', 'sitemap', 'llms', 'structured-data', 'security-contact', '404', 'routes', 'no-js', 'blocked-assets', 'asset-versioning', 'cache', 'source-maps', 'secrets', 'accessibility', 'screen-reader-semantics', 'keyboard', 'mobile', 'zoom-200', 'reduced-motion', 'slow-network', 'offline-after-load', 'lab-cwv', 'internal-links', 'external-links', 'github-docs-links', 'maintenance', 'rollback'];
export function configuration({target, profile, origin, external = false, securityContact, maintenanceTarget, rollbackManifest, rollbackTarget} = {}) {
  if (!['local', 'staging', 'production'].includes(profile)) throw new Error('Explicit profile required');
  let url; try { url = new URL(target); } catch { throw new Error('Explicit target origin required'); }
  if (url.username || url.password || url.search || url.hash || url.pathname !== '/') throw new Error('Target must be an origin without credentials');
  const local = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
  if (profile === 'local' ? !local || !['http:', 'https:'].includes(url.protocol) : local || url.protocol !== 'https:' || !external) throw new Error('External HTTPS requires explicit opt-in; local profile requires loopback');
  if (profile !== 'local' && (/^[\d.]+$|:|\.(local|internal|invalid|test)$/.test(url.hostname) || !url.hostname.includes('.'))) throw new Error('External target requires public hostname');
  if (maintenanceTarget && (!maintenanceTarget.startsWith('/') || maintenanceTarget.startsWith('//') || /[?#]/.test(maintenanceTarget))) throw new Error('Maintenance target must be a same-origin path');
  if (process.env.NODE_TLS_REJECT_UNAUTHORIZED === '0') throw new Error('TLS validation must remain enabled');
  let canonical; try { canonical = new URL(origin); } catch { throw new Error('Explicit expected origin required'); }
  if (canonical.origin !== origin || canonical.username || canonical.password) throw new Error('Expected origin must be canonical');
  if (!['http:','https:'].includes(canonical.protocol)) throw new Error('Expected origin must be HTTP(S)');
  if (profile !== 'local' && (canonical.protocol !== 'https:' || canonical.origin !== url.origin)) throw new Error('External profile requires target-matching HTTPS origin');
  if (rollbackTarget && (!rollbackTarget.startsWith('/') || rollbackTarget.startsWith('//') || /[?#]/.test(rollbackTarget))) throw new Error('Rollback target must be same-origin path');
  return {target: url.origin, profile, origin, securityContact, maintenanceTarget, rollbackManifest, rollbackTarget};
}
export function report(config) { return {schema: 1, target: config.target, profile: config.profile, checks: checks.map(id => ({id, status: 'UNVERIFIED', evidence: 'Not executed'})), limitations: ['Laboratory observations are not field CWV or INP', 'No deployment or mutation is performed']}; }
export function record(result, id, pass, evidence) { const item = result.checks.find(row => row.id === id); if (!item) throw new Error('Unknown check'); item.status = pass ? 'PASS' : 'FAIL'; item.evidence = evidence; }
export function finish(result) { result.accepted = result.checks.every(row => row.status === 'PASS'); return result; }
export function safeLink(value, base) { const url = new URL(value, base); if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password) throw new Error('Unsafe link'); return url; }
export function containsSecret(text) { return /pdl_(live|sdbx)_apikey_|sk_live_[A-Za-z0-9]|BEGIN (RSA |OPENSSH )?PRIVATE KEY|\/Users\/|\/home\/runner\//.test(text); }
export function failureDiagnostic(error) {
  const categories = ['Error','TypeError','AbortError','TimeoutError','AssertionError'];
  const codes = ['ECONNREFUSED','ECONNRESET','ETIMEDOUT','ENOTFOUND','EAI_AGAIN','EPROTO','CERT_HAS_EXPIRED','ERR_TLS_CERT_ALTNAME_INVALID','DEPTH_ZERO_SELF_SIGNED_CERT','SELF_SIGNED_CERT_IN_CHAIN','UNABLE_TO_VERIFY_LEAF_SIGNATURE','UNABLE_TO_GET_ISSUER_CERT_LOCALLY'];
  const code = error?.code ?? error?.cause?.code;
  return {category:categories.includes(error?.name) ? error.name : 'Error',code:codes.includes(code) ? code : 'UNCLASSIFIED'};
}
