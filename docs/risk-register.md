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
| Repeated capability transaction sequence is mislabeled as duplicate telemetry | Separate semantics implemented | Track continuity only for AFE `TEL`; validate repeated capability sequence inside the transaction aggregator |
| Profile-native capability names disagree with adapter/workflow channel names | Explicit Step 6 debt | Keep frozen wire safety vocabulary now; require a reviewed, tested adapter projection instead of string guessing |
| MSP430 unavailable sentinels or fault-time zeros become false measurements | Host mapping implemented | Preserve raw fields; map `-32768` and INA219 communication-fault voltage/current to `None + INVALID + MISSING`; freeze fault fixtures |
| MSP430 command surface leaks into a read-only integration | Default-deny profile | Parse only device outputs, provide no command encoder, advertise no output or `SAFE_SHUTDOWN`, and prove output runners remain zero-write in Step 6 |
| Peer tests or hardware evidence are inherited by this repository | Separate fixture provenance | Record only the frozen public interface source; use repository-owned tests/reports and separate any future Analog-owned HIL evidence |
