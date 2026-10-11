// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import {output,headers} from '../../web/tooling/launch-contract.mjs';
import {run} from '../../web/tooling/acceptance/run.mjs';
import {humanReport} from '../../web/tooling/acceptance/human-report.mjs';
import {checks,configuration,report,record,finish,containsSecret,safeLink,failureDiagnostic} from '../../web/tooling/acceptance/contract.mjs';
test('transport diagnostics preserve allowlisted cause codes without messages or arbitrary fields',() => {
  assert.deepEqual(failureDiagnostic({name:'TypeError',cause:{code:'CERT_HAS_EXPIRED'},message:'private response'}),{category:'TypeError',code:'CERT_HAS_EXPIRED'});
  assert.deepEqual(failureDiagnostic({name:'private name',code:'private code',message:'private response'}),{category:'Error',code:'UNCLASSIFIED'});
  const result = report({}); result.failure = {category:'TypeError',code:'CERT_HAS_EXPIRED'};
  assert.match(humanReport(result),/Transport failure: TypeError \/ CERT_HAS_EXPIRED/);
});
test('no implicit target/profile or external authority',() => {
  for (const input of [{},{target:'https://whitepact.com',profile:'production',origin:'https://whitepact.com'},{target:'https://user:secret@whitepact.com',profile:'production',origin:'https://whitepact.com',external:true},{target:'http://whitepact.com',profile:'production',origin:'https://whitepact.com',external:true},{target:'https://whitepact.com/?secret=1',profile:'production',origin:'https://whitepact.com',external:true}]) assert.throws(() => configuration(input));
});
test('explicit localhost permitted without external opt-in',() => assert.equal(configuration({target:'http://127.0.0.1:9876',profile:'local',origin:'https://whitepact.com'}).profile,'local'));
test('valid explicit staging HTTPS accepted as configuration not proof',() => { const config = configuration({target:'https://staging.whitepact.com',profile:'staging',origin:'https://staging.whitepact.com',external:true}); assert.equal(finish(report(config)).accepted,false); });
test('canonical scheme and external profile mismatch rejected before requests',() => {
  assert.throws(() => configuration({target:'http://localhost',profile:'local',origin:'ftp://whitepact.com'}));
  assert.throws(() => configuration({target:'https://staging.whitepact.com',profile:'staging',origin:'https://whitepact.com',external:true}));
  assert.throws(() => configuration({target:'https://whitepact.com',profile:'production',origin:'http://whitepact.com',external:true}));
});
test('every named requirement defaults unverified and acceptance fails closed',() => { const result = report({target:'http://localhost',profile:'local'}); assert.equal(result.checks.length,34); assert.equal(new Set(checks).size,34); assert.ok(result.checks.every(row => row.status === 'UNVERIFIED')); record(result,'routes',true,'fixture'); assert.equal(finish(result).accepted,false); });
test('human report preserves failures and uncertainty without response bodies',() => { const result = report({target:'http://localhost',profile:'local'}); record(result,'routes',false,'private response body should not be printed'); const text = humanReport(finish(result)); assert.match(text,/NOT ACCEPTED/); assert.match(text,/routes \| FAIL/); assert.match(text,/tls \| UNVERIFIED/); assert.doesNotMatch(text,/private response body/); });
test('human report exposes numerical zoom failure evidence, not arbitrary fields',() => {
  const result = report({target:'http://localhost',profile:'local'});
  record(result,'zoom-200',false,{overflowFailures:[{route:'/docs',width:375,mode:'zoom-200',diagnostic:{innerWidth:375,clientWidth:375,scrollWidth:640},responseBody:'must stay private'}]});
  const text = humanReport(finish(result));
  assert.match(text,/"route":"\/docs"/);assert.match(text,/"scrollWidth":640/);assert.doesNotMatch(text,/must stay private|responseBody/);
});
test('explicit failure cannot be mistaken for acceptance',() => { const result = report({}); for (const id of checks) record(result,id,true,'fixture'); record(result,'tls',false,'certificate rejected'); assert.equal(finish(result).accepted,false); });
test('human HTTP failures expose exact safe status but not private response diagnostics',() => {
  const result = report({});
  result.httpFailures = [{route:'/docs',errors:['status 503, expected 200','private body must not be printed']}];
  const text = humanReport(finish(result));
  assert.match(text,/HTTP \/docs: status 503, expected 200/);
  assert.doesNotMatch(text,/private body must not be printed/);
});
test('secret signatures detected without returning material',() => { assert.equal(containsSecret('pdl_sdbx_apikey_sensitive'),true); assert.equal(containsSecret('BEGIN PRIVATE KEY'),true); assert.equal(containsSecret('WhitePact API key instructions'),false); });
test('external link validation rejects credentials and nonHTTP',() => { assert.throws(() => safeLink('https://user:secret@example.com','https://whitepact.com')); assert.throws(() => safeLink('javascript:alert(1)','https://whitepact.com')); assert.equal(safeLink('/docs','https://whitepact.com').pathname,'/docs'); });
test('unknown result identifiers rejected',() => assert.throws(() => record(report({}),'made-up',true,'not evidence')));
test('real local artifact HTTP fixture verifies evidence but never claims external acceptance',async () => {
  const inventory = JSON.parse(fs.readFileSync(output+'/public-routes.json','utf8'));
  const server = http.createServer((req,res) => {
    const resource = new URL(req.url,'http://localhost').pathname;
    if (resource === '/refunds') { res.writeHead(308,{Location:'/refund-policy'}).end(); return; }
    // The linked generated API reference is authentication-protected, not a
    // static website file. Model the documented unauthenticated boundary.
    if (resource === '/api/docs') { res.writeHead(401,{'Cache-Control':'private, no-store'}).end(); return; }
    const known = inventory.routes.includes(resource), asset = resource.startsWith('/static/whitepact/'), discovery = ['/robots.txt','/sitemap.xml','/llms.txt'].includes(resource), privateContent = ['/login','/dashboard/evidence','/sovereign/workbench'].includes(resource);
    const name = privateContent ? 'pages/private.html' : asset ? resource.slice('/static/whitepact/'.length) : discovery ? resource.slice(1) : known ? 'pages/'+(resource === '/' ? 'home' : resource.slice(1))+'.html' : 'pages/not-found.html';
    const file = path.resolve(output,name);
    if (!file.startsWith(output+path.sep) || !fs.existsSync(file)) { res.writeHead(404,headers(resource)).end(); return; }
    const mime = {'.html':'text/html','.js':'application/javascript','.css':'text/css','.json':'application/json','.webp':'image/webp','.png':'image/png','.svg':'image/svg+xml','.woff2':'font/woff2'};
    res.writeHead(known || asset || discovery || privateContent ? 200 : 404,{...headers(resource,{privateContent}),'Content-Type':mime[path.extname(file)] ?? 'application/octet-stream'}); fs.createReadStream(file).pipe(res);
  });
  await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
  try {
    const config = configuration({target:'http://127.0.0.1:'+server.address().port,profile:'local',origin:inventory.origin});
    const result = await run(config,{browser:process.env.RUN_ACCEPTANCE_BROWSER === '1' && !process.env.ACCEPTANCE_FOCUS});
    if (process.env.RUN_ACCEPTANCE_BROWSER === '1' && process.env.ACCEPTANCE_FOCUS) { const {browserChecks} = await import('../../web/tooling/acceptance/browser.mjs'); await browserChecks(config,result,['/']); }
    assert.equal(result.error,undefined);
    for (const id of ['routes','canonical','source-maps','secrets','asset-versioning','internal-links']) assert.equal(result.checks.find(row => row.id === id).status,'PASS',id);
    for (const id of ['tls','https','hsts','rollback','maintenance','security-contact','external-links']) assert.equal(result.checks.find(row => row.id === id).status,'UNVERIFIED',id);
    assert.equal(result.accepted,false);
    if (process.env.RUN_ACCEPTANCE_BROWSER === '1') {
      assert.ok(result.reflowEvidence.every(row => row.pass));
      assert.deepEqual(result.checks.filter(row => ['no-js','blocked-assets','accessibility','screen-reader-semantics','keyboard','mobile','zoom-200','reduced-motion','slow-network','offline-after-load','lab-cwv'].includes(row.id) && row.status !== 'PASS'),[]);
      for (const id of ['no-js','blocked-assets','accessibility','screen-reader-semantics','keyboard','mobile','zoom-200','reduced-motion','slow-network','offline-after-load','lab-cwv']) { const row = result.checks.find(row => row.id === id); assert.equal(row.status,'PASS',JSON.stringify(row)); }
    }
  } finally { await new Promise(resolve => server.close(resolve)); }
});
