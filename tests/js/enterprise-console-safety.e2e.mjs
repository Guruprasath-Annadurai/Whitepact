// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
// Rendered UI contract qualification only. API responses are explicitly isolated
// fixtures, not production identity, Core authorization or downstream-effect proof.
import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";
import { mkdtempSync, readFileSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const evidenceDir = mkdtempSync(path.join(tmpdir(), "whitepact-console-safety-"));
const session = {user:{full_name:"Local Test Reviewer",email:"reviewer@example.invalid"},organization:{id:"local-fixture",name:"UI Contract Fixture",plan:"FREE",role:"OWNER"}};
const detail = {approval_id:"approval-fixture",status:"PENDING",action_type:"supported.action",target:"reviewed-target",required_approvals:1,current_vote_count:0,votes:[],purpose:"local-ui-contract"};
// Serve the existing production build at the same /static/whitepact asset mount
// as the backend. Vite preview's base-prefixed SPA does not mirror /dashboard.
const bundle=path.join(root,"src/responsibleai/dashboard/static/whitepact");
const mime={".js":"text/javascript",".css":"text/css",".png":"image/png",".svg":"image/svg+xml",".webp":"image/webp",".woff2":"font/woff2",".html":"text/html"};
const server=createServer((req,res)=>{
  const pathname=new URL(req.url,"http://localhost").pathname;
  const relative=pathname.startsWith("/static/whitepact/")?pathname.slice("/static/whitepact/".length):"index.html";
  const filename=path.resolve(bundle,relative);
  if(!filename.startsWith(bundle+path.sep)){res.writeHead(403);res.end();return;}
  try{const contents=readFileSync(filename);res.writeHead(200,{"Content-Type":mime[path.extname(filename)]??"application/octet-stream"});res.end(contents);}
  catch{res.writeHead(404);res.end();}
});
await new Promise(resolve=>server.listen(0,"127.0.0.1",resolve));
const origin=`http://127.0.0.1:${server.address().port}`;
let browser;
const checks = [];
try {
  let ready=false;
  for(let i=0;i<120;i++){try {if((await fetch(origin)).ok){ready=true;break;}}catch{} await new Promise(r=>setTimeout(r,250));}
  assert(ready,"Local frontend preview did not start");
  assert.equal((await fetch(origin+"/static/whitepact/m12c-deliberately-missing.js")).status,404,"Missing asset must return 404 without crashing the test server");
  browser=await chromium.launch({headless:true});
  for(const width of [375,768,1024,1440]) {
    for(const failure of ["lost","503","malformed","contradictory","vote-lost"]) {
      const context=await browser.newContext({viewport:{width,height:1000},reducedMotion:"reduce"});
      const page=await context.newPage();const pageErrors=[];let executes=0;let votes=0;
      page.on("pageerror",e=>pageErrors.push(e.message));
      await context.addCookies([{name:"wp_csrf",value:"local-csrf-fixture",url:origin}]);
      await context.route("**/*",async route=>{
        const request=route.request();const url=new URL(request.url());
        if(url.origin!==origin)return route.abort();
        if(!url.pathname.startsWith("/api/"))return route.continue();
        let body=session;
        if(url.pathname.endsWith("/dashboard/approvals"))body={items:[detail],source:"explicit-ui-fixture"};
        else if(url.pathname.endsWith("/resolve")) {
          votes++;assert.equal(request.headers()["x-wp-csrf"],"local-csrf-fixture");
          assert.deepEqual(request.postDataJSON(),{outcome:"APPROVED"});
          if(failure==="vote-lost")return route.abort();body={status:"APPROVED"};
        } else if(url.pathname.endsWith("/execute")) {
          executes++;assert.deepEqual(request.postDataJSON(),{});
          if(failure==="lost")return route.abort();
          if(failure==="503")return route.fulfill({status:503,json:{detail:"Unavailable"}});
          body=failure==="malformed"?null:{approval_id:detail.approval_id,execution_status:"SUCCEEDED",reconciliation_required:true,message:"Contradictory fixture",evidence_id:null,outcome_id:null};
        } else if(url.pathname.includes("/approvals/"))body=detail;
        return route.fulfill({json:body});
      });
      await page.goto(origin+"/dashboard/approvals");
      await page.getByRole("button",{name:"Approve",exact:true}).click();
      await page.getByRole("dialog").waitFor();
      assert(await page.getByRole("dialog").evaluate(node=>node.contains(document.activeElement)),"Dialog did not move keyboard focus");
      await page.getByRole("button",{name:"Confirm approved"}).click();
      await page.getByRole("heading",{name:failure==="vote-lost"?"Approval outcome is uncertain":"Execution outcome is uncertain",exact:true}).waitFor();
      assert(await page.getByRole("button",{name:"Approve",exact:true}).isDisabled());
      assert(await page.getByRole("button",{name:"Deny",exact:true}).isDisabled());
      assert.equal(votes,1);assert.equal(executes,failure==="vote-lost"?0:1);
      assert.equal(pageErrors.length,0,pageErrors.join("\n"));
      assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1)),"Horizontal overflow");
      const axe=await new AxeBuilder({page}).withTags(["wcag2a","wcag2aa","wcag21aa"]).analyze();
      assert.equal(axe.violations.length,0,JSON.stringify(axe.violations.map(v=>({id:v.id,impact:v.impact}))));
      if(failure==="lost")await page.screenshot({path:path.join(evidenceDir,`uncertain-${width}.png`),fullPage:true});
      checks.push({width,failure,votes,executes,axeViolations:0});await context.close();
    }
    const context=await browser.newContext({viewport:{width,height:1000}});const page=await context.newPage();const errors=[];
    page.on("pageerror",e=>errors.push(e.message));
    await context.route("**/api/**",route=>route.fulfill({json:{...session,organization:null}}));
    await page.addInitScript(()=>sessionStorage.setItem("whitepact-onboarding-draft",JSON.stringify({step:999,data:"corrupt"})));
    await page.goto(origin+"/onboarding");
    await page.getByRole("heading",{name:"Tell us about your organization"}).waitFor();
    assert.equal(errors.length,0,errors.join("\n"));
    assert(!(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1)),"Onboarding overflow");
    const axe=await new AxeBuilder({page}).withTags(["wcag2a","wcag2aa","wcag21aa"]).analyze();assert.equal(axe.violations.length,0);
    checks.push({width,onboardingCorruptDraft:true,axeViolations:0});await context.close();
  }
  console.log(JSON.stringify({kind:"UI_CONTRACT_FIXTURES_NOT_CORE_QUALIFICATION",checks:checks.length,viewports:[375,768,1024,1440],evidenceDir,results:checks}));
} catch (cause) {
  // This server permits only synthetic local fixtures, never real sessions.
  const failedPage=browser?.contexts().at(-1)?.pages().at(-1);
  if(failedPage){
    await failedPage.screenshot({path:path.join(evidenceDir,"failure.png"),fullPage:true});
    console.error(JSON.stringify({kind:"SYNTHETIC_UI_FAILURE",evidenceDir,url:failedPage.url(),body:(await failedPage.locator("body").innerText()).slice(0,3000)}));
  }
  throw cause;
} finally {if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
