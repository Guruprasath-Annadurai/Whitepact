// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { extractClaims, root } from '../../web/tooling/public-claims.mjs';
const register = JSON.parse(fs.readFileSync(path.join(root, 'docs/website/truth/public-claims.json'), 'utf8'));
const classes = new Set(['PROVEN', 'OWNER_INPUT_REQUIRED', 'PACKAGE_DEPENDENT', 'CLOUD_DEPENDENT', 'SECURITY_DEPENDENT', 'LEGAL_DEPENDENT', 'COMMERCIAL_DEPENDENT', 'REMOVE_OR_REWRITE']);
test('all current textual claim fragments have unchanged exact-location coverage', () => {
  assert.deepEqual(register.claims.map(({ id, file, line, text, routes }) => ({ id, file, line, text, routes })), extractClaims());
  assert.equal(new Set(register.claims.map(c => c.id)).size, register.claims.length);
});
test('all 15 public routes are registered', () => {
  assert.equal(register.publicRoutes.length, 15);
  for (const route of register.publicRoutes) assert.ok(register.claims.some(c => c.routes.includes(route)), route);
});
test('each decision requires real evidence locators and a release condition', () => {
  for (const claim of register.claims) {
    assert.ok(classes.has(claim.classification));
    assert.ok(claim.releaseCondition.length > 40);
    for (const locator of claim.evidence) {
      const split = locator.lastIndexOf(':');
      const file = locator.slice(0, split), line = Number(locator.slice(split + 1));
      assert.ok(fs.existsSync(path.join(root, file)), locator);
      assert.ok(line > 0 && line <= fs.readFileSync(path.join(root, file), 'utf8').split('\n').length, locator);
    }
    if (claim.classification === 'PROVEN') assert.equal(claim.evidenceScope, 'SOURCE_OR_BOUNDARY_ONLY');
  }
});
test('legal policy business promises cannot be marked proven by code', () => {
  const policies = register.claims.filter(c => c.file.endsWith('commerce.json') && c.routes.some(r => ['/terms', '/privacy', '/refund-policy'].includes(r)));
  assert.ok(policies.length > 40);
  assert.ok(policies.every(c => c.classification === 'LEGAL_DEPENDENT'));
});
test('package gate defaults closed and public copy no longer asserts stale publication', () => {
  const docs = fs.readFileSync(path.join(root, 'web/src/features/marketing/PublicPages.tsx'), 'utf8');
  assert.ok(docs.includes('publishedPackageContent(packagePublication)'));
  assert.ok(!docs.includes('Published distribution 1.2.6'));
  assert.ok(!docs.includes('pip install whitepact'));
  const sov = fs.readFileSync(path.join(root, 'web/src/features/sovereign/SovereignPage.tsx'), 'utf8');
  assert.ok(!sov.includes('Authenticated live route'));
  assert.ok(sov.includes('deployment dependent'));
});
test('security-sensitive claims have explicit qualification gates and doctrine is bounded', () => {
  const security = register.claims.filter(c => c.classification === 'SECURITY_DEPENDENT');
  assert.ok(security.length > 20);
  assert.ok(security.every(c => c.releaseCondition.includes('exact') && c.evidenceScope === 'UNVERIFIED_RELEASE_GATE'));
  const files = ['web/src/content/commerce.json', 'web/src/content/corporate.json', 'web/src/content/public-info.json', 'web/src/features/marketing/HomePage.tsx', 'web/src/features/marketing/PublicPages.tsx', 'web/public/llms.txt'];
  for (const file of files) {
    const text = fs.readFileSync(path.join(root, file), 'utf8');
    assert.ok(!text.includes('But it cannot act outside independently enforced authority.'), file);
    assert.ok(text.includes('Direct calls outside those paths and compromised infrastructure are not universally controlled.'), file);
  }
});
