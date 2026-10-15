# Evidence witness runbook

The database hash chain does not detect a rewritten chain. Signed
publication does. Live object-lock storage is not provisioned.

## What is implemented

- Ed25519 head signatures in `responsibleai.governance.evidence_witness`.
- Append-only JSON publication in
  `responsibleai.governance.evidence_publication.AppendOnlyWitnessLog`.
- Private keys in a `0700` directory, file mode `0600`. Group or world
  access fails closed.
- Rotation keeps the previous public key.
- Verification reads only the publication directory.
- Rollback, a missing file, a hash mismatch, and a rewritten publication
  body fail verification.
- `WHITEPACT_EVIDENCE_WITNESS_REQUIRED=1` turns a publication failure
  into `WitnessRequiredUnavailableError`.
- Agent containers do not receive the witness key directory or the
  object-store secret. `build_isolated_environment` drops those names.
- `scripts/verify_evidence_publication.py` checks a head without opening
  the application database.

`LIVE_ANCHOR_STATUS` remains `EXTERNAL_BLOCKER`.
`live_object_store_status()` is `NOT_PROVISIONED` until endpoint,
bucket, and keys are all set, and then only `CONFIGURED_UNVERIFIED`.
Neither value means a live witness exists.

## Local proof

```bash
python scripts/verify_evidence_publication.py \
  --log /var/lib/whitepact/evidence-witness \
  --organization org-a \
  --sequence 1 \
  --head-hash "$HEAD"
```

A changed head hash exits 1. A new process can reopen the same
directory. Tests covering this are in `tests/test_evidence_publication.py`.

## Owner action for a live witness

1. Create a Cloudflare R2 bucket with object lock enabled at creation.
   Lock cannot be added later.
2. Create a token that can put objects and cannot delete them.
3. Set a retention rule of at least the audit retention period.
4. Put the signing key on the authority host only, mode `0600`, not on
   execution hosts and not in the agent environment.
5. Set `WHITEPACT_EVIDENCE_S3_ENDPOINT`, `WHITEPACT_EVIDENCE_S3_BUCKET`,
   `WHITEPACT_EVIDENCE_S3_ACCESS_KEY_ID`, and
   `WHITEPACT_EVIDENCE_S3_SECRET_ACCESS_KEY` on the authority host.
6. Publish one head with `put_object_lock` and have an auditor read that
   object back with a different credential that cannot change the
   database.
7. Only after that read-back may anyone call the witness live.

No R2 bucket was created in this candidate. No credential was used.
A successful header test against an injected HTTP transport is not that
read-back.
