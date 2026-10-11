// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import {failureDiagnostic} from './contract.mjs';
export function humanReport(result) {
  const counts = Object.fromEntries(['PASS','FAIL','UNVERIFIED'].map(status => [status,(result.checks ?? []).filter(row => row.status === status).length]));
  const safe = value => String(value ?? '').replace(/[\r\n|\x00-\x1f]/g,' ');
  const transport = result.failure ? failureDiagnostic({name:result.failure.category,code:result.failure.code}) : null;
  const httpEvidence = (result.httpFailures ?? []).map(row => {
    const reasons = (row.errors ?? []).map(error => {
      if (/^status \d{3}, expected \d{3}$/.test(error) || /^header mismatch [A-Za-z-]+$/.test(error)) return error;
      if (['canonical mismatch','missing static heading','private indexing','robots profile mismatch','sitemap route/origin mismatch','private/error leakage','staging indexing','mixed content'].includes(error)) return error;
      return 'Additional HTTP/asset check failed; inspect structured diagnostic locally';
    });
    return `HTTP ${safe(row.route)}: ${reasons.map(safe).join('; ')}`;
  });
  const failureEvidence = (result.checks ?? []).filter(row => row.status === 'FAIL' && row.evidence && typeof row.evidence === 'object').map(row => {
    // Only locally generated layout evidence is suitable for human output.
    // Arbitrary response bodies, exception strings and credentials stay out.
    const overflows = Array.isArray(row.evidence.overflowFailures) ? row.evidence.overflowFailures.map(failure => ({
      route:failure.route,width:failure.width,mode:failure.mode,
      innerWidth:failure.diagnostic?.innerWidth,clientWidth:failure.diagnostic?.clientWidth,scrollWidth:failure.diagnostic?.scrollWidth,
    })) : [];
    return `${safe(row.id)}: ${JSON.stringify(overflows)}`;
  });
  return ['WHITEPACT WEBSITE ACCEPTANCE',`Target: ${safe(result.target)} (${safe(result.profile)})`,`Overall: ${result.accepted ? 'ACCEPTED' : 'NOT ACCEPTED'}`,`PASS ${counts.PASS}; FAIL ${counts.FAIL}; UNVERIFIED ${counts.UNVERIFIED}`,...(transport ? [`Transport failure: ${transport.category} / ${transport.code}`] : []),'','CHECK | RESULT',...(result.checks ?? []).map(row => `${safe(row.id)} | ${safe(row.status)}`),...failureEvidence,...httpEvidence,'','UNVERIFIED is not PASS. No deployment or mutation was performed.',...(result.limitations ?? []).map(safe)].join('\n')+'\n';
}
