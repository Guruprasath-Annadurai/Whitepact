# M13 final source conflict resolution

## Current checkpoint: 851f5288 (2026-10-19)

The authoritative current evidence and limitations are in
[M13_FINAL_CORRECTIVE_CHECKPOINT.md](M13_FINAL_CORRECTIVE_CHECKPOINT.md).
Candidate HEAD is `851f52888a57df35619b9d75ab3d6f61c4f53bc7`, tree
`c66bed85ac9bbaff54af9c5a08e29f82f441ec99`, parent
`39461fec883aeb18a14f486ba9d65a2c02b20d06`. New exact-head CI is pending;
completed predecessor receipts must not be transferred to it. Subsequent
historical/interim sections retain their original checkpoint scope.
**BLOCKED — ENGINEERING OR SECURITY GATES REMAIN. M13 OPEN. GLOBAL PRODUCTION NO-GO.**

Candidate under qualification: HEAD `bb6e263fc271a07f58484ce1fd1445cc201b24b0`, tree `93f36747cd00610850c8cf0ace13de107b145da5`, parent `2bde48d4abe20312dd6408cf62366d68ca69746e`. [Draft PR223](https://github.com/Guruprasath-Annadurai/Whitepact/pull/223). Reports/evidence are maintained separately from the tested implementation. M13 OPEN. GLOBAL PRODUCTION NO-GO.

Status: IN PROGRESS; exact-head matrices pending.

## Hunk decisions

| File or contract | Selective decision |
|---|---|
|container_backend.py|Preserve IRONCLAD private0700 receipt, trusted64-hex ACK, owned spawn/register/cleanup and bounded PIPE drainage. Add daemon creation labels and optional acknowledged immutable CID/execution association. No owner wholesale overwrite.|
|in_flight.py tracking scan|Reject owner unreadable-record filename attribution/suppression; retain unknown uncertainty.|
|in_flight.py detached verification|Reject rm-by-name before ownership proof. Require acknowledged CID and matching daemon Id,Name,tenant hash,execution label. Remove exactCID only; reused name cannot target an ABA replacement. Plugin/inspect uncertainty denies without rm.|
|in_flight.py detached admission|No callback/task is not containment proof. Preserve unresolved until positive callback or qualified immutable identity termination. Preserve remote registration generation for compare/delete. Missing file never clears in-memory unresolved state.|
|backup_defense.py|Integrate reviewed FK-safe authority purge/forensic retention, canonical governance epoch floor, Store B integrity/readiness and DB recovery markers. Add fresh asynchronous database admission rather than accepting startup cache.|
|dashboard/app.py|Bind current DB; startup check/error fencing. Operator status checks live marker. Public restore both aliases remain503 and disabled.|
|dashboard/middleware.py|Check live DB before every non-recovery HTTP admission. A pending marker cannot dispatch using cached READY. Narrow existing health/recovery path allowlist unchanged.|
|Seven existing consequential consumers|Await live restore admission in privileged IAM, internal/upstream execution, webhook delivery, erasure, retention and deletion orchestration. No privilege flags or root/A2 bypass added.|
|data_governance/__init__.py|Integrate owner provider/startup helpers; existing SDK/package contracts require regression qualification.|
|Original H4 and Fortress tests|Remain byte-for-byte IRONCLAD originals. Owner fixture and assertion changes reviewed separately, not silently imported.|
|Owner focused new20 cases|Imported unchanged for integrated qualification; their name-only recovery expectation is not allowed to override ownership invariants.|

## Trust boundaries and limits

Docker daemon/client and same-UID host are trusted as in IRONCLAD. Workload cannot write host-private receipts or Docker metadata. CID acknowledgement is read using the existing strict descriptor checks. A name or legacy record alone grants no removal authority. If acknowledgement was not available at registration, automatic detached recovery may remain blocked; no finite absence window or erased record substitutes for proof. This availability limitation remains explicit pending qualified operator recovery.

## Independent evidence

[Four owner-source counterexamples](https://github.com/Guruprasath-Annadurai/Whitepact/blob/bb6e263fc271a07f58484ce1fd1445cc201b24b0/scripts/engineering/reproducers/test_m13_final_owner_review.py):4FAIL4.14s on exacte7e24dee. Integrated focused45PASS12.48s (component, not native). Additional HTTP200-vs503 counterexample1FAIL2.66s; stale operator status2FAIL14.04s SQLite/PostgreSQL. Corrected actual HTTP/status4PASS25.54s across both backends. Live-marker7PASS39.52s. Full source mypy427PASS before HTTP successor; modified HTTP2 files mypyPASS. All are local receipts; exact-head Linux qualification remains separate.

Source links: [integrated comparison](https://github.com/Guruprasath-Annadurai/Whitepact/compare/ccf4e8cc80f1de52a0a9b445298055ac581f53e1...bb6e263fc271a07f58484ce1fd1445cc201b24b0), [owner comparison](https://github.com/Guruprasath-Annadurai/Whitepact/compare/7939341fd9d98d0f1fa39ce4421318dbc1dac33e...e7e24dee0c828bbbe8c08db6e519aedf3cc0a0d2).

