// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

export const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
export const files = [
  'web/src/content/commerce.json', 'web/src/content/corporate.json', 'web/src/content/public-info.json',
  'web/src/features/marketing/HomePage.tsx', 'web/src/features/marketing/PublicPages.tsx',
  'web/src/features/marketing/CorporatePages.tsx', 'web/src/features/sovereign/SovereignPage.tsx',
  'web/public/llms.txt', 'web/index.html',
];
const corporateRoutes = ['/product', '/architecture', '/developers', '/security', '/enterprise'];
const functionRoutes = { DocsPage: ['/docs'], AboutPage: ['/about'], ContactPage: ['/contact'], TrustCenterPage: ['/trust'],
  LegalPage: ['/pricing', '/terms', '/privacy', '/refund-policy'], NotFoundPage: ['/404'], BillingResultPage: ['/billing/success', '/billing/cancelled'] };
function routeFor(file, node, jsonRoutes) {
  if (file.endsWith('HomePage.tsx') || file.endsWith('index.html')) return ['/'];
  if (file.endsWith('SovereignPage.tsx')) return ['/sovereign'];
  if (file.endsWith('CorporatePages.tsx')) {
    const variables = { productControls: ['/product'], architecturePlanes: ['/architecture'], enterpriseControls: ['/enterprise'], developerReferences: ['/developers'] };
    for (let parent = node.parent; parent; parent = parent.parent) {
      if (ts.isVariableDeclaration(parent) && variables[parent.name.text]) return variables[parent.name.text];
      if (ts.isBinaryExpression(parent) && parent.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken) {
        const match = parent.left.getText().match(/pageKey === "(product|architecture|developers|security|enterprise)"/);
        if (match) return [`/${match[1]}`];
      }
    }
    return corporateRoutes;
  }
  for (let parent = node.parent; parent; parent = parent.parent) {
    if (ts.isFunctionDeclaration(parent) && parent.name && functionRoutes[parent.name.text]) return functionRoutes[parent.name.text];
    if (ts.isFunctionDeclaration(parent) && ['ResultGuide', 'CodeExample'].includes(parent.name?.text)) return ['/docs'];
    if (jsonRoutes && ts.isPropertyAssignment(parent) && parent.parent === node.getSourceFile().statements[0]?.expression) return [jsonRoutes[parent.name.text]];
  }
  return ['SHARED_PUBLIC'];
}
export function extractClaims() {
  const claims = [];
  for (const file of files) {
    const raw = fs.readFileSync(path.join(root, file), 'utf8');
    if (file.endsWith('.txt') || file.endsWith('.html')) {
      raw.split('\n').forEach((text, i) => {
        if ((file.endsWith('.txt') && !text.startsWith('#')) || /description|application\/ld\+json/.test(text)) {
          if (text.trim().length > 20) claims.push(make(file, i + 1, text.trim(), file.endsWith('.html') ? ['/'] : ['SHARED_PUBLIC']));
        }
      });
      continue;
    }
    const source = ts.createSourceFile(file, raw, ts.ScriptTarget.Latest, true, file.endsWith('.json') ? ts.ScriptKind.JSON : ts.ScriptKind.TSX);
    const json = file.endsWith('.json') ? JSON.parse(raw) : null;
    function visit(node) {
      if (ts.isStringLiteral(node) || ts.isJsxText(node) || ts.isNoSubstitutionTemplateLiteral(node)) {
        const text = node.text.replace(/\s+/g, ' ').trim();
        const isAttribute = node.parent && ts.isJsxAttribute(node.parent);
        const skippedAttribute = isAttribute && !['title', 'description', 'alt'].includes(node.parent.name.text);
        const materialStatus = /^(Available|Free source|MIT license|Source implemented|Source and tests|Repository automation|Written quote|Terms by agreement|Not externally certified|Availability not verified|Deployment dependent|Contract dependent)$/i.test(text);
        if (((text.length > 20 && /\s/.test(text)) || materialStatus) && /[a-z]/i.test(text) && !skippedAttribute && !text.startsWith('http')) {
          let routes = routeFor(file, node);
          if (json) {
            for (let parent = node.parent; parent; parent = parent.parent) {
              if (ts.isPropertyAssignment(parent) && json[parent.name.text]?.path) { routes = [json[parent.name.text].path]; break; }
            }
          }
          claims.push(make(file, source.getLineAndCharacterOfPosition(node.getStart()).line + 1, text, routes));
        }
      }
      ts.forEachChild(node, visit);
    }
    visit(source);
  }
  return claims;
}
function make(file, line, text, routes) {
  return { id: crypto.createHash('sha256').update(`${file}:${line}:${text}`).digest('hex').slice(0, 16), file, line, text, routes };
}
if (process.argv[1] === fileURLToPath(import.meta.url)) console.log(JSON.stringify(extractClaims()));
