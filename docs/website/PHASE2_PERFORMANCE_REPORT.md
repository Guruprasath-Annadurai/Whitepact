# Phase 2 corporate performance report

Comparison base: `f970e7c4e210f339c8c7af2104ea98546ad6b514`.
Branch: `codex/whitepact-global-website-phase2`.
This is local laboratory evidence, not production field Core Web Vitals.

## Bundles

Bytes are measured from built artifacts; gzip uses the same Node zlib defaults for both revisions, rather than comparing different bundler display algorithms.

| Artifact | Phase 1 raw / gzip bytes | Phase 2 raw / gzip bytes |
| --- | ---: | ---: |
| Main | 288,098 / 89,643 | 255,632 / 77,778 |
| Shared JSX/runtime | 8,557 / 3,274 | 50,051 / 17,834 |
| Combined initial main + shared | 296,655 / 92,917 | 305,683 / 95,612 |
| Corporate route | 13,226 / 4,734 | 23,908 / 7,735 |
| Stylesheet | 63,311 / 12,664 | 77,637 / 15,156 |
| TrustCore | 884,458 / 232,499 | Not emitted |

The main chunk alone shrinks, but common-chunk redistribution means combined initial JS increases by 9,028 raw bytes (3.04%) and 2,695 gzip bytes (2.90%). Expanded documentation and semantic editorial components have a real cost. This is not described as universal bundle reduction. Corporate CSS also grows. No unrelated console/Sovereign functionality was removed to reduce these numbers.

## Artwork and fonts

The primary corporate mechanical-head hero is replaced by a semantic authority-boundary figure. The original 336,750-byte WebP remains on disk but is no longer requested by that hero. Phase 1 already deferred its optional 3D: baseline initial navigation did not fetch TrustCore. Phase 2 removes the optional corporate 3D entry entirely; the source remains available for a separately justified future use.

The 1,200 × 388 wordmark is encoded as lossless WebP: 43,072 bytes versus the retained 89,222-byte PNG fallback. Only corporate navigation/footer opt in; console/auth default behavior is unchanged. Browser decoding confirms identical alpha and opaque interior pixels. At 4,524 of 465,600 partially transparent edge pixels, browser RGBA decoding differs; composited on the site's near-black background the maximum channel difference is 1/255. Therefore byte-for-byte decoded pixel identity is not claimed. Visual inspection found no observable degradation.

The 88,128-byte mark, 953,361-byte 1,200 × 675 social PNG and seven WOFF2 files totaling 101,868 bytes remain unchanged. The social image is not part of initial homepage navigation. Font weights are shared with the console and are not removed merely to improve an editorial score. No unused font format was introduced. Further social-image compression remains a non-blocking improvement, not a claimed completed optimization.

## Laboratory method

`tests/js/corporate-performance.mjs` serves the production-built homepage over uncompressed localhost HTTP. Chromium 151, cold cache disabled, reduced motion, viewport height 900. Three runs per profile:

- Mobile: 390px, 150ms latency, 200,000 bytes/second throughput, 4× CPU slowdown.
- Desktop: 1,440px, 40ms latency, 1,250,000 bytes/second throughput, 1× CPU.

PerformanceObserver captures LCP, CLS and long tasks. Long-task duration is an interaction-risk proxy, not measured INP. The baseline was measured from the exact Phase 1 build before rebuilding Phase 2. Raw JSON and review screenshots remain outside the repository under `/private/tmp`.

| Measurement | Phase 1 | Phase 2 |
| --- | ---: | ---: |
| Mobile LCP median | 5,524ms | 2,824ms |
| Desktop LCP median | 1,004ms | 620ms |
| Mobile CLS median | 0.067590 | 0.040949 |
| Desktop CLS | 0.064766 | 0.010960 |
| Initial transfer, uncompressed lab | 956,356 bytes | 626,572 bytes |
| Resource count | 11 | 12 |
| Optional 3D fetched initially | No | No |

Baseline mobile long-task totals: 253/256/173ms. Final mobile: 324/177/191ms (median 191ms versus baseline 253ms); the first final run is worse, so this is not a claim that every CPU measurement improved. Both desktop sets have no long tasks. Final mobile LCP runs: 3,236/2,824/2,816ms; desktop: 600/632/620ms. Initial transfer decreases 34.48% despite resource count increasing by one. Final decoded bytes: 622,672 versus 952,756. Six final runs completed successfully; raw results: `/private/tmp/whitepact-phase2-final-performance.json`. Baseline: `/private/tmp/whitepact-phase2-baseline-performance.json`.

Mobile LCP median remains above the usual 2.5-second good reference. This result demonstrates improvement under the stated lab profile, not a field CWV pass.

## Evidence-derived internal budget

Use the measured Phase 1 initial transfer and profile-median LCP as non-regression ceilings for the same harness. Optional 3D on initial corporate navigation must remain zero. Shared fonts must not grow above the existing 101,868-byte on-disk inventory without a demonstrated requirement. Accepting the disclosed 3.04% initial-JS growth requires lower overall transfer and no material LCP regression; it is not silently excluded from review. All these comparison gates pass in this laboratory. They are not promised production SLAs or arbitrary Lighthouse score targets.

## Unmeasured boundaries

Lighthouse was not executed. Field LCP/CLS/INP, production compression/CDN/cache behavior, real-device battery/CPU, geographic network conditions and production uptime were not measured. Chrome/Chromium laboratory evidence is not universal browser compatibility. Production rehearsal and field monitoring remain separate owner-controlled launch gates.
