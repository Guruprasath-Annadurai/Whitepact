# Lost ACK / UNKNOWN reconciliation

**pytest** `test_v1_exactly_one_effect.py`: **PASS**

Exercises `fail_after_effect` synthetic executor → `OutcomeStatus.UNKNOWN`, no blind retry, persisted outcomes.

```
                  73     73     10      0     0%   16-173
src/responsibleai/supplychain/__init__.py                         4      0      0      0   100%
src/responsibleai/supplychain/models.py                          37      3      0      0    92%   37, 77, 80
src/responsibleai/supplychain/scanner.py                         43     29     18      0    23%   101, 113-132, 139-155, 170-178, 190, 201-204
src/responsibleai/trust/__init__.py                               3      0      0      0   100%
src/responsibleai/trust/badge.py                                 16     10      0      0    38%   34, 44-54
src/responsibleai/trust/passport.py                              52     21      2      0    57%   49, 64, 68-76, 79-90, 163-168, 179-190, 222-232
src/responsibleai/trust/score.py                                 66     33     22      2    40%   29-37, 41-47, 68, 71, 108, 113, 146-159, 202-211
src/responsibleai/trust_fabric/__init__.py                       17      0      0      0   100%
src/responsibleai/trust_fabric/authority_graph.py                81     65     32      0    14%   50, 67-103, 119-133, 157-204, 228-242, 261-310
src/responsibleai/trust_fabric/bootstrap.py                     107     91     38      0    11%   53, 65-180, 193-305, 318-329
src/responsibleai/trust_fabric/challenge.py                      52     38     12      0    22%   47, 59-99, 110-199
src/responsibleai/trust_fabric/conflict.py                      113     98     40      0    10%   62-89, 96, 109-140, 159-289, 295-296
src/responsibleai/trust_fabric/decision.py                       52     40     10      0    19%   41-45, 49-185
src/responsibleai/trust_fabric/directory.py                      97     75     28      0    18%   52-76, 83, 95-117, 121-136, 159-232, 256-281, 294-314, 337-351
src/responsibleai/trust_fabric/enums.py                         101      0      0      0   100%
src/responsibleai/trust_fabric/errors.py                         26      0      0      0   100%
src/responsibleai/trust_fabric/federation.py                    135    104     48      0    17%   60-64, 79-81, 85, 89, 93-105, 109-112, 135-184, 209-359
src/responsibleai/trust_fabric/models.py                        271     43     14      0    80%   33, 38, 63-65, 77, 108, 139, 172, 209-213, 216, 253-260, 263, 295, 322, 326, 329, 353, 383-385, 388, 423, 456, 459, 495-497, 500, 535-548, 564
src/responsibleai/trust_fabric/monitor.py                        88     68     12      0    20%   40-42, 46, 50, 59-93, 102-142, 152-168, 177-189, 196-257, 267-302, 311-356, 365-381, 385-395, 399-402
src/responsibleai/trust_fabric/passport.py                      147    113     60      0    16%   69-73, 86-89, 93, 97, 101-112, 116-127, 139-226, 244-261, 265-287, 297-339, 348-419
src/responsibleai/trust_fabric/proofs.py                        122    108     70      0     7%   40, 44-88, 98-135, 144-193, 202-224, 238-258, 269-291
src/responsibleai/trust_fabric/provenance.py                     86     72     22      0    13%   48, 60-77, 102-155, 181-226, 235-322
src/responsibleai/trust_fabric/provider.py                       54     14      4      0    69%   55, 94, 98, 102, 113-148
src/responsibleai/webhooks/__init__.py                            3      0      0      0   100%
src/responsibleai/webhooks/manager.py                           222    146     76      6    28%   66-94, 122, 125, 130->exit, 137->exit, 146-147, 151, 154-157, 162-170, 173, 178-180, 183-189, 222-231, 241-318, 322->exit, 325-336, 347-348, 353-357, 360-362, 365-367, 371, 375, 385-391, 399-408, 431-432, 448-453
src/responsibleai/webhooks/models.py                             45      2      0      0    96%   43, 69
---------------------------------------------------------------------------------------------------------
TOTAL                                                         25855  15046   6004    418    36%
Coverage HTML written to dir htmlcov
Coverage JSON written to file coverage.json
1 passed, 1 warning in 18.71s

```
