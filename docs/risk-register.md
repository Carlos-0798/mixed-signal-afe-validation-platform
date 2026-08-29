# Risk register

| Risk | Current Phase 0 state | Mitigation / gate |
|---|---|---|
| Input outside 0-3.3 V | No hardware connected | Series resistance, clamps, DMM check, current-limited supply |
| Wrong IC pinout or orientation | Unconfirmed | Exact package datasheet and marked wiring review before power |
| Op-amp common-mode/output limits | Idealized only | Replace ideal model, calculate margin, then bench-check |
| Comparator output/load changes thresholds | Unconfirmed | Verify exact part/output type and isolate LED load |
| Breadboard parasitics or oscillation | Not tested | Short wiring, local decoupling, scope check, conservative bandwidth |
| USB/lab instrument grounding | Permission and setup open | Confirm common ground and lab rules before connection |
| Synthetic/SPICE data mistaken for measurement | Controlled by labels | Keep source/evidence label in data and reports |
| Two personal projects become coupled | Interface only | Separate repository; only documented public interfaces |
| Capstone work becomes mixed with this project | Prohibited | No copied code, data, repository history, or team claims |
| Toolchain drift | Toolchain open | Pin CCS/compiler/libraries after user confirms environment |

