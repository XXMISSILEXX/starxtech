# Risk register

| ID | Risk/evidence | Likelihood | Impact | Mitigation/owner | Block |
|---|---|---|---|---|---|
| R1 | V2 direct-upload contract (`create_v2.py`) | M | H | regression suite; engineering | yes |
| R2 | Category live labels change history | H | M | decide snapshot policy; product | yes |
| R3 | Legacy DB roles/grants | H | H | inventory/reconcile deliberately; security | yes |
| R4 | No category required enforcement | M | M | decide/enforce separately; product | no |
| R5 | Project status not create gate | M | H | choose policy/tests; product | yes |
| R6 | Missing-report dashboard denominator | H | H | Today scope service; engineering | yes |
| R7 | Partner domain collision | M | H | separate tables/prefixes; architect | yes |
| R8 | Existing hard report delete | M | H | no incompatible FKs; migration rehearsal | yes |
| R9 | stale pg statistics | M | M | operational ANALYZE approval; DBA | no |
| R10 | issue links/responsibility undefined | H | M | owner decisions; product | yes |
