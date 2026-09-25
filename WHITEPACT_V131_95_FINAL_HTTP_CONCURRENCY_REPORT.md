# HTTP-layer multi-worker concurrency (Phase 0C)

**Verdict:** **PASS**

Primary cross-replica HTTP evidence: `tests/test_v1_two_process_replicas.py` (approval quorum, exactly-one execute, API-key revoke, rate-limit 429).

```json
{
  "workers": 4,
  "scenarios": [
    {
      "scenario": "approval_resolution",
      "codes": [
        409,
        409,
        409,
        200,
        409,
        409,
        409,
        409,
        409,
        409,
        409,
        409,
        409,
        409,
        409,
        409
      ],
      "ok_200": 1,
      "conflict": 15
    },
    {
      "scenario": "approval_execute",
      "codes": [
        422,
        422,
        422,
        422,
        422,
        422,
        422,
        422,
        422,
        422,
        422,
        422
      ],
      "success": 0
    },
    {
      "scenario": "api_key_revoke_race",
      "during": [
        401,
        200
      ],
      "after_revoke": 401
    }
  ],
  "approval_final_status": "APPROVED",
  "nonce_replay_pytest": true,
  "two_replica_journey": true,
  "two_replica_tail": "\nsrc/responsibleai/trust_fabric/federation.py                    135    104     48      0    17%   60-64, 79-81, 85, 89, 93-105, 109-112, 135-184, 209-359\nsrc/responsibleai/trust_fabric/models.py                        271     43     14      0    80%   33, 38, 63-65, 77, 108, 139, 172, 209-213, 216, 253-260, 263, 295, 322, 326, 329, 353, 383-385, 388, 423, 456, 459, 495-497, 500, 535-548, 564\nsrc/responsibleai/trust_fabric/monitor.py                        88     68     12      0    20%   40-42, 46, 50, 59-93, 102-142, 152-168, 177-189, 196-257, 267-302, 311-356, 365-381, 385-395, 399-402\nsrc/responsibleai/trust_fabric/passport.py                      147    113     60      0    16%   69-73, 86-89, 93, 97, 101-112, 116-127, 139-226, 244-261, 265-287, 297-339, 348-419\nsrc/responsibleai/trust_fabric/proofs.py                        122    108     70      0     7%   40, 44-88, 98-135, 144-193, 202-224, 238-258, 269-291\nsrc/responsibleai/trust_fabric/provenance.py                     86     72     22      0    13%   48, 60-77, 102-155, 181-226, 235-322\nsrc/responsibleai/trust_fabric/provider.py                       54     14      4      0    69%   55, 94, 98, 102, 113-148\nsrc/responsibleai/webhooks/__init__.py                            3      0      0      0   100%\nsrc/responsibleai/webhooks/manager.py                           222    169     76      0    18%   66-94, 112, 116, 121-126, 130-132, 136-139, 146-147, 151, 154-157, 162-170, 173, 178-180, 183-189, 210-231, 241-318, 322-348, 353-357, 360-362, 365-367, 371, 375, 385-391, 399-408, 431-432, 448-453\nsrc/responsibleai/webhooks/models.py                             45      2      0      0    96%   43, 69\n---------------------------------------------------------------------------------------------------------\nTOTAL                                                         25855  16664   6004     44    29%\nCoverage HTML written to dir htmlcov\nCoverage JSON written to file coverage.json\n1 passed, 12 warnings in 20.75s\n",
  "verdict": "PASS"
}
```
