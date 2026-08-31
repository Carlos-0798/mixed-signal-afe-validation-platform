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
| Corrupt serial input grows memory | Host-tested bounds only | Bounded reads/records, discard overlong data through LF, bounded raw log and eviction counters |
| Reconnect joins bytes from different connections | Host-tested reset | Clear partial/overlong state before every reconnect and return before reading the new connection |
| Port identity is mistaken for device capability | Explicit profile required | Never infer profile, firmware, safe range, or output ability from COM/USB identity |
| Raw frames expose device/configuration details | Memory-only host model | Count/byte/metadata limits, logical port only, no automatic persistence/upload, explicit future export review |
| Host serial tests are presented as hardware proof | HOST_TEST only | Real OS backend and owner-approved HIL have separate later gates; `VERIFIED_BENCH` remains zero |
