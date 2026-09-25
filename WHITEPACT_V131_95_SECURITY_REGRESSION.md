# Security regression subset

```json
{
  "cmd": [
    "/workspace/.venv/bin/python",
    "-m",
    "pytest",
    "tests/test_mcp_argument_validation.py",
    "tests/test_trust_client.py",
    "tests/test_mcp_trust_check.py",
    "tests/test_mcp_server_gating.py",
    "tests/test_enterprise_saas_layer1.py",
    "tests/test_tenant_isolation.py",
    "tests/test_paddle_billing_service.py",
    "tests/test_dns_egress_security.py",
    "tests/test_checkpoint6_transport_boundary.py",
    "tests/test_mcp_governance_dispatch.py",
    "tests/test_phase1_release_gate.py",
    "tests/test_auth_canonical_seams.py",
    "-q",
    "--tb=no"
  ],
  "exit": 0,
  "tail": " 10      0     0%   16-173\nsrc/responsibleai/supplychain/__init__.py                         4      0      0      0   100%\nsrc/responsibleai/supplychain/models.py                          37      3      0      0    92%   37, 77, 80\nsrc/responsibleai/supplychain/scanner.py                         43     29     18      0    23%   101, 113-132, 139-155, 170-178, 190, 201-204\nsrc/responsibleai/trust/__init__.py                               3      0      0      0   100%\nsrc/responsibleai/trust/badge.py                                 16     10      0      0    38%   34, 44-54\nsrc/responsibleai/trust/passport.py                              52     14      2      0    70%   64, 68-76, 79-90, 163-168\nsrc/responsibleai/trust/score.py                                 66     15     22      8    74%   30, 32, 36, 42, 47, 108, 113, 156, 202-211\nsrc/responsibleai/trust_fabric/__init__.py                       17      0      0      0   100%\nsrc/responsibleai/trust_fabric/authority_graph.py                81     65     32      0    14%   50, 67-103, 119-133, 157-204, 228-242, 261-310\nsrc/responsibleai/trust_fabric/bootstrap.py                     107     91     38      0    11%   53, 65-180, 193-305, 318-329\nsrc/responsibleai/trust_fabric/challenge.py                      52     38     12      0    22%   47, 59-99, 110-199\nsrc/responsibleai/trust_fabric/conflict.py                      113     98     40      0    10%   62-89, 96, 109-140, 159-289, 295-296\nsrc/responsibleai/trust_fabric/decision.py                       52     40     10      0    19%   41-45, 49-185\nsrc/responsibleai/trust_fabric/directory.py                      97     75     28      0    18%   52-76, 83, 95-117, 121-136, 159-232, 256-281, 294-314, 337-351\nsrc/responsibleai/trust_fabric/enums.py                         101      0      0      0   100%\nsrc/responsibleai/trust_fabric/errors.py                         26      0      0      0   100%\nsrc/responsibleai/trust_fabric/federation.py                    135    104     48      0    17%   60-64, 79-81, 85, 89, 93-105, 109-112, 135-184, 209-359\nsrc/responsibleai/trust_fabric/models.py                        271     43     14      0    80%   33, 38, 63-65, 77, 108, 139, 172, 209-213, 216, 253-260, 263, 295, 322, 326, 329, 353, 383-385, 388, 423, 456, 459, 495-497, 500, 535-548, 564\nsrc/responsibleai/trust_fabric/monitor.py                        88     68     12      0    20%   40-42, 46, 50, 59-93, 102-142, 152-168, 177-189, 196-257, 267-302, 311-356, 365-381, 385-395, 399-402\nsrc/responsibleai/trust_fabric/passport.py                      147    113     60      0    16%   69-73, 86-89, 93, 97, 101-112, 116-127, 139-226, 244-261, 265-287, 297-339, 348-419\nsrc/responsibleai/trust_fabric/proofs.py                        122    108     70      0     7%   40, 44-88, 98-135, 144-193, 202-224, 238-258, 269-291\nsrc/responsibleai/trust_fabric/provenance.py                     86     72     22      0    13%   48, 60-77, 102-155, 181-226, 235-322\nsrc/responsibleai/trust_fabric/provider.py                       54     14      4      0    69%   55, 94, 98, 102, 113-148\nsrc/responsibleai/webhooks/__init__.py                            3      0      0      0   100%\nsrc/responsibleai/webhooks/manager.py                           222     80     76     14    59%   68-69, 75, 88-89, 122, 125, 130->exit, 137->exit, 151, 154-157, 162-170, 173, 178-180, 183-189, 228->227, 249, 260-261, 266, 278-279, 294-295, 312-313, 322->exit, 325-336, 347-348, 353-357, 360-362, 365-367, 371, 375, 386, 388, 390, 399-408, 431-432, 448-453\nsrc/responsibleai/webhooks/models.py                             45      2      0      0    96%   43, 69\n---------------------------------------------------------------------------------------------------------\nTOTAL                                                         25855  13327   6004    598    43%\nCoverage HTML written to dir htmlcov\nCoverage JSON written to file coverage.json\n284 passed, 5 warnings in 90.22s (0:01:30)\n"
}
```
