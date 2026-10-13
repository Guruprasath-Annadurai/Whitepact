// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import {chromium} from 'playwright';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';
import {output} from '../launch-contract.mjs';
import {record} from './contract.mjs';
export async function browserChecks(config,result,routes) {
  const browser = await chromium.launch({headless:true});
  const navigationRoutes = JSON.parse(fs.readFileSync(output+'/public-routes.json','utf8')).routes;
  const outcomes = new Map(['no-js','blocked-assets','accessibility','screen-reader-semantics','keyboard','mobile','zoom-200','reduced-motion','slow-network','offline-after-load','lab-cwv'].map(id => [id,true]));
  const observations = [];
  const overflowFailures = [];
  const reflowEvidence = [];
  const renderedLinks = new Set();
  try {
    for (const mode of ['normal','no-js','blocked-assets','zoom-200','reduced-motion','slow-network','offline-after-load']) {
      for (const width of mode === 'zoom-200' ? [320,360,375,390,412,768,1024,1280,1440] : mode === 'normal' ? [375,768,1024,1440] : [375,1440]) {
        const context = await browser.newContext({viewport:{width,height:900},javaScriptEnabled:mode !== 'no-js',reducedMotion:mode === 'reduced-motion' ? 'reduce' : 'no-preference'});
        await context.route('**/*',async route => {
          const url = new URL(route.request().url());
          if (url.origin !== config.target || mode === 'blocked-assets' && /\.(js|css|woff2?|webp|png|svg)$/.test(url.pathname)) return route.abort();
          return route.continue();
        });
        const page = await context.newPage();
        if (mode === 'slow-network') {
          const cdp = await context.newCDPSession(page);
          await cdp.send('Network.enable');
          await cdp.send('Network.emulateNetworkConditions',{offline:false,latency:150,downloadThroughput:200000,uploadThroughput:93750,connectionType:'cellular3g'});
        }
        await page.addInitScript(() => { window.__acceptanceVitals = {lcp:0,cls:0}; new PerformanceObserver(list => { for (const entry of list.getEntries()) window.__acceptanceVitals.lcp = entry.startTime; }).observe({type:'largest-contentful-paint',buffered:true}); new PerformanceObserver(list => { for (const entry of list.getEntries()) if (!entry.hadRecentInput) window.__acceptanceVitals.cls += entry.value; }).observe({type:'layout-shift',buffered:true}); });
        for (const route of routes) {
          await page.setViewportSize({width,height:900});
          await context.setOffline(false);
          const response = await page.goto(config.target+route,{waitUntil:'networkidle',timeout:30000});
          const visible = response.status() === 200 && await page.locator('h1').first().isVisible() && !!await page.title();
          if (mode === 'normal') for (const href of await page.locator('a[href]').evaluateAll(links => links.map(link => link.href))) renderedLinks.add(href);
          if (mode !== 'normal') outcomes.set(mode,outcomes.get(mode) && visible);
          if (mode === 'zoom-200') await page.evaluate(() => { document.documentElement.style.zoom = '2'; });
          if (mode === 'offline-after-load') { await context.setOffline(true); await page.keyboard.press('Tab'); outcomes.set(mode,outcomes.get(mode) && await page.locator('h1').first().isVisible()); }
          const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth+1);
          if (overflow) overflowFailures.push({mode,width,route,diagnostic:await page.evaluate(() => ({innerWidth,clientWidth:document.documentElement.clientWidth,scrollWidth:document.documentElement.scrollWidth,zoom:getComputedStyle(document.documentElement).zoom,elements:[...document.querySelectorAll('main *')].filter(element => element.getBoundingClientRect().right > innerWidth+1).slice(0,5).map(element => ({tag:element.tagName,class:element.className,width:Math.round(element.getBoundingClientRect().width)}))}))});
          if (!['blocked-assets','zoom-200'].includes(mode)) outcomes.set('mobile',outcomes.get('mobile') && !overflow);
          if (mode === 'zoom-200') outcomes.set(mode,outcomes.get(mode) && !overflow);
          if (mode === 'zoom-200') {
            const clippedControls = await page.locator('a,button,input,select,textarea').evaluateAll(elements => elements.filter(element => {
              const rect = element.getBoundingClientRect();
              return rect.width > 0 && rect.height > 0 && getComputedStyle(element).visibility !== 'hidden' && (rect.left < -1 || rect.right > innerWidth+1) && !element.closest('pre,table');
            }).map(element => ({tag:element.tagName,selector:element.id ? '#'+element.id : element.className,text:(element.textContent??'').trim().slice(0,80)})));
            if (clippedControls.length) overflowFailures.push({mode,width,route,clippedControls});
            outcomes.set(mode,outcomes.get(mode) && clippedControls.length === 0);
          }
          if (mode === 'zoom-200') {
            await page.evaluate(() => { document.documentElement.style.zoom = '1'; });
            const cssWidth = Math.max(320,Math.floor(width/2));
            await page.setViewportSize({width:cssWidth,height:900});
            const data = await page.evaluate(() => ({innerWidth,scrollWidth:document.documentElement.scrollWidth}));
            reflowEvidence.push({route,originalWidth:width,cssWidth,...data,pass:data.scrollWidth <= data.innerWidth+1,method:width >= 640 ? 'Equivalent 200% CSS viewport reduction; not native browser zoom' : '320px minimum reflow check; not 200% zoom'});
          }
          if (mode === 'reduced-motion') outcomes.set(mode,outcomes.get(mode) && await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches && document.getAnimations().every(animation => { const timing = animation.effect?.getComputedTiming(); return animation.playState !== 'running' || timing.duration <= 10; })));
          if (mode === 'normal') {
            const axe = await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze(); outcomes.set('accessibility',outcomes.get('accessibility') && axe.violations.length === 0);
            const semantics = await page.getByRole('main').count() === 1 && await page.getByRole('heading',{level:1}).count() === 1 && await page.getByRole('navigation',{name:'Primary navigation',includeHidden:true}).count() === 1 && (await page.locator('body').ariaSnapshot()).includes('heading');
            outcomes.set('screen-reader-semantics',outcomes.get('screen-reader-semantics') && semantics && axe.violations.length === 0);
            await page.keyboard.press('Tab');
            const focus = await page.evaluate(() => { const element = document.activeElement; return element && element !== document.body && element.getBoundingClientRect().width > 0; });
            outcomes.set('keyboard',outcomes.get('keyboard') && focus);
            const menu = page.getByRole('button',{name:'Open menu',exact:true});
            if (await menu.isVisible()) {
              await menu.focus(); await page.keyboard.press('Enter');
              await page.getByRole('button',{name:'Close menu',exact:true}).waitFor();
              await page.waitForFunction(() => document.querySelector('#corporate-navigation')?.contains(document.activeElement));
              await page.keyboard.press('Tab'); await page.keyboard.press('Escape');
              const restored = await page.getByRole('button',{name:'Open menu',exact:true}).evaluate(element => document.activeElement === element && element.getAttribute('aria-expanded') === 'false');
              outcomes.set('keyboard',outcomes.get('keyboard') && restored);
            }
            let reached = false;
            for (let step = 0; step < 35; step++) {
              const destination = await page.evaluate(() => document.activeElement?.getAttribute('href'));
              if (destination && navigationRoutes.includes(destination) && destination !== route) {
                await page.keyboard.press('Enter'); await page.waitForURL(config.target+destination);
                reached = await page.locator('h1').first().isVisible();
                await page.goto(config.target+route,{waitUntil:'networkidle'}); break;
              }
              await page.keyboard.press('Tab');
            }
            outcomes.set('keyboard',outcomes.get('keyboard') && reached);
            const vitals = await page.evaluate(() => window.__acceptanceVitals);
            outcomes.set('lab-cwv',outcomes.get('lab-cwv') && vitals.lcp > 0 && vitals.lcp <= 3000 && vitals.cls <= 0.1);
            observations.push({route,width,...vitals});
          }
        }
        await context.close();
        if (process.env.ACCEPTANCE_PROGRESS === '1') console.error(JSON.stringify({mode,width,routes:routes.length,completed:true}));
      }
    }
    result.degradedLayoutObservations = overflowFailures;
    result.reflowEvidence = reflowEvidence;
    for (const [id,pass] of outcomes) record(result,id,pass,id === 'lab-cwv' ? {observations,thresholds:{lcp:3000,cls:0.1},field:false,inp:'UNVERIFIED'} : id === 'mobile' ? {scope:'Styled layout only; blocked-CSS and zoom have separate observations',overflowFailures:overflowFailures.filter(row => !['blocked-assets','zoom-200'].includes(row.mode))} : id === 'zoom-200' ? {overflowFailures:overflowFailures.filter(row => row.mode === 'zoom-200'),zoom:'CSS reflow approximation, not native browser UI zoom'} : 'All public routes; isolated browser context; external resources blocked');
    return [...renderedLinks];
  } finally { await browser.close(); }
}
