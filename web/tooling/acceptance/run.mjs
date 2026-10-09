// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import fs from 'node:fs';
import tls from 'node:tls';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
import {configuration, report, record, finish, safeLink, containsSecret, failureDiagnostic} from './contract.mjs';
import {humanReport} from './human-report.mjs';
import {output, smoke, validateSecurityContact, manifest} from '../launch-contract.mjs';
export async function run(config, {browser = true, verifyExternalLinks = false, fetcher = fetch} = {}) {
  const result = report(config);
  const get = async path => fetcher(new URL(path, config.target), {redirect: 'manual', signal: AbortSignal.timeout(15000)});
  try {
    const basic = await smoke(config.target, {local: config.profile === 'local', expectedOrigin: config.origin, staging: config.profile === 'staging'});
    result.httpFailures = basic.results.filter(row => !row.pass);
    for (const id of ['redirects','headers','csp','canonical','robots','sitemap','llms','404','routes','cache', ...(config.profile === 'local' ? [] : ['hsts'])]) record(result, id, basic.pass, basic.pass ? 'Existing strict HTTP smoke passed' : 'Strict HTTP smoke failed; inspect local reproduction');
    if (config.profile !== 'local') {
      record(result, 'https', true, 'Explicit HTTPS target; default certificate validation enabled');
      const target = new URL(config.target);
      await new Promise((resolve,reject) => { const socket = tls.connect({host: target.hostname, port: Number(target.port || 443), servername: target.hostname, rejectUnauthorized: true}, () => { record(result,'tls',socket.authorized && ['TLSv1.2','TLSv1.3'].includes(socket.getProtocol()), 'Hostname/CA verification and protocol >= TLS1.2'); socket.end(); resolve(); }); socket.setTimeout(15000, () => socket.destroy(new Error('TLS timeout'))); socket.on('error', reject); });
    }
    const inventory = JSON.parse(fs.readFileSync(output + '/public-routes.json','utf8'));
    const assets = new Set(), internal = new Set(), external = new Set();
    let structured = true, leaks = false, maps = false;
    for (const route of inventory.routes) {
      const response = await get(route), html = await response.text();
      leaks ||= containsSecret(html);
      const json = [...html.matchAll(/<script[^>]*type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/g)];
      structured &&= json.length > 0;
      for (const match of json) { try { const data = JSON.parse(match[1]); structured &&= data['@context'] === 'https://schema.org' && !!data['@type']; } catch { structured = false; } }
      for (const match of html.matchAll(/(?:href|src)="([^"#]+)"/g)) {
        if (/^(mailto:|tel:|data:|blob:)/.test(match[1])) continue;
        try { const url = safeLink(match[1], config.target); if (url.origin === config.target) { if (url.pathname.startsWith('/static/')) assets.add(url.pathname); else internal.add(url.pathname); } else external.add(url.href); } catch { structured = false; }
      }
    }
    const expected = manifest();
    if (browser) {
      const {browserChecks} = await import('./browser.mjs');
      for (const href of await browserChecks(config,result,inventory.routes)) {
        if (/^(mailto:|tel:)/.test(href)) continue;
        const url = safeLink(href,config.target);
        if (url.origin === config.target) internal.add(url.pathname); else external.add(url.href);
      }
    }
    for (const name of Object.keys(expected.sha256).filter(name => name.startsWith('assets/'))) assets.add('/static/whitepact/'+name);
    let assetOK = true, cacheOK = true;
    for (const asset of assets) {
      const response = await get(asset); assetOK &&= response.status === 200;
      const bytes = Buffer.from(await response.arrayBuffer());
      assetOK &&= crypto.createHash('sha256').update(bytes).digest('hex') === expected.sha256[asset.slice('/static/whitepact/'.length)];
      const cache = response.headers.get('cache-control') ?? '';
      if (/-[\w-]{8,}\.(js|css|woff2?)$/.test(asset)) cacheOK &&= /immutable/.test(cache) && /max-age=31536000/.test(cache);
      if (/\.(js|css)$/.test(asset)) { const text = bytes.toString(); leaks ||= containsSecret(text); maps ||= /sourceMappingURL/.test(text); const map = await get(asset + '.map'); maps ||= map.status === 200; }
    }
    record(result,'structured-data', structured, 'Present JSON-LD parsed; no fabricated schemas inferred');
    record(result,'secrets', !leaks,'Credential signatures/local paths scanned; values never reported');
    record(result,'source-maps', !maps,'JS/CSS references and adjacent .map requests checked');
    record(result,'asset-versioning', assetOK && cacheOK,'Referenced assets resolve; fingerprinted resources immutable');
    let linksOK = true; result.internalLinkFailures = [];
    for (const link of internal) {
      const response = await get(link);
      const valid = response.status >= 200 && response.status < 400 || link === '/api/docs' && [401,403].includes(response.status);
      linksOK &&= valid;
      if (!valid) result.internalLinkFailures.push({path:link,status:response.status});
    }
    record(result,'internal-links',linksOK,'All discovered same-origin HTTP links GET checked');
    if (verifyExternalLinks) { let ok = true, gh = true, redirected = false; for (const link of external) { const response = await fetcher(link,{method:'HEAD',redirect:'manual',signal:AbortSignal.timeout(15000)}); const valid = response.status >= 200 && response.status < 300; redirected ||= response.status >= 300 && response.status < 400; ok &&= valid; if (/github\.com|\/docs/.test(link)) gh &&= valid; } record(result,'external-links',ok,'Explicit external HEAD checks; redirects require separate destination review'); record(result,'github-docs-links',gh,'Discovered GitHub/docs targets checked'); if (redirected) result.checks.find(row => row.id === 'external-links').status = 'UNVERIFIED'; }
    if (config.securityContact) { validateSecurityContact(config.securityContact,Date.now()); const response = await get('/.well-known/security.txt'), text = await response.text(); record(result,'security-contact',response.status === 200 && text.includes('Contact: '+config.securityContact.contact) && text.includes('Expires: '+config.securityContact.expires),'Owner-approved contact/expiry compared'); }
    if (config.maintenanceTarget) { const response = await get(config.maintenanceTarget); record(result,'maintenance', response.status === 503 && /no-store/.test(response.headers.get('cache-control') ?? '') && !!response.headers.get('retry-after'), 'Read-only maintenance target: 503/no-store/Retry-After'); }
    if (config.rollbackManifest) { const prior = JSON.parse(fs.readFileSync(config.rollbackManifest,'utf8')); let ok = true; for (const [name,digest] of Object.entries(prior.sha256).filter(([name]) => name.startsWith('assets/'))) { const response = await get('/static/whitepact/'+name); ok &&= response.status === 200 && crypto.createHash('sha256').update(Buffer.from(await response.arrayBuffer())).digest('hex') === digest; } const item = result.checks.find(row => row.id === 'rollback'); item.status = ok ? 'UNVERIFIED' : 'FAIL'; item.evidence = 'Prior asset retention '+(ok ? 'verified' : 'failed')+'; actual activation/rollback response still requires independently observed rehearsal'; }
    if (config.rollbackManifest && config.rollbackTarget) { const prior = JSON.parse(fs.readFileSync(config.rollbackManifest,'utf8')); const response = await get(config.rollbackTarget), bytes = Buffer.from(await response.arrayBuffer()); const item = result.checks.find(row => row.id === 'rollback'); const previousHTML = prior.sha256['pages/home.html']; record(result,'rollback',item.status !== 'FAIL' && !!previousHTML && response.status === 200 && crypto.createHash('sha256').update(bytes).digest('hex') === previousHTML,'Read-only prior homepage bytes and retained prior asset hashes verified at explicitly supplied rehearsal path; no activation performed'); }
  } catch (error) { result.error = 'Acceptance operation failed; credentials and response bodies suppressed'; result.failure = failureDiagnostic(error); }
  return finish(result);
}
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  try { const config = configuration({target:process.env.BASE_URL,profile:process.env.SITE_PROFILE,origin:process.env.EXPECTED_SITE_ORIGIN,external:process.argv.includes('--authorize-external'),securityContact:process.env.SECURITY_CONTACT_CONTRACT ? JSON.parse(fs.readFileSync(process.env.SECURITY_CONTACT_CONTRACT,'utf8')) : undefined,maintenanceTarget:process.env.MAINTENANCE_PATH,rollbackManifest:process.env.ROLLBACK_MANIFEST,rollbackTarget:process.env.ROLLBACK_PATH}); const result = await run(config,{verifyExternalLinks:process.argv.includes('--authorize-link-targets'),browser:!process.argv.includes('--http-only')}); console.log(JSON.stringify(result,null,2)); console.error(humanReport(result)); if (!result.accepted) process.exitCode = 1; } catch { console.log(JSON.stringify({accepted:false,error:'Invalid explicit configuration; no target contacted'})); console.error('WHITEPACT WEBSITE ACCEPTANCE: NOT ACCEPTED; invalid configuration; no target contacted'); process.exitCode = 1; }
}
