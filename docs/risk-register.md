# Risk register

| Risk | Current state | Mitigation / gate |
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
| Raw frames expose device/configuration details | Bounded memory model plus explicit local HIL evidence | Count/byte/metadata limits; discovery excludes hardware IDs; HIL persistence is create-new, local, Git-ignored, and never uploaded automatically |
| Narrow controller UART HIL is presented as AFE or peripheral proof | COM4 receive-only compatibility accepted | Keep `BENCH_CONTROLLER` scope explicit; exact firmware, sensors, fan, wiring, and every AFE performance claim remain unverified |
| Repeated capability transaction sequence is mislabeled as duplicate telemetry | Separate semantics implemented | Track continuity only for AFE `TEL`; validate repeated capability sequence inside the transaction aggregator |
| Profile-native capability names disagree with adapter/workflow channel names | Host-tested explicit projection | Retain native AFE snapshot; alias every declared channel through the reviewed Step 6 projector; reject identity/count/range/command escalation |
| MSP430 unavailable sentinels or fault-time zeros become false measurements | Host mapping implemented | Preserve raw fields; map `-32768` and INA219 communication-fault voltage/current to `None + INVALID + MISSING`; freeze fault fixtures |
| MSP430 command surface leaks into a read-only integration | Host-tested zero-write boundary | Parse only device outputs, provide no command encoder or adapter write escape hatch, advertise no output or `SAFE_SHUTDOWN`, and keep DC/hysteresis runners zero-write `UNSUPPORTED` |
| Peer tests or hardware evidence are inherited by this repository | Separate fixture provenance | Record only the frozen public interface source; use repository-owned tests/reports and separate any future Analog-owned HIL evidence |
| Reconnect reuses stale Measurements or capabilities | Host-tested fail-closed invalidation | Clear profile state, derived buffers, native/projected capabilities, and require capability reconfirmation before another read |
| In-memory backend behavior is mistaken for OS-driver support | Optional pyserial backend and one COM4 HIL complete | Keep pyserial outside the formal core; state the exact five-frame/one-port result and do not generalize it to long-duration timing, reconnect, other bridges, or AFE hardware |
| Known no-CRC legacy heartbeat is either accepted as production protocol or mislabeled as corruption | Exact peer behavior reviewed in Step 7 | Keep the core parser strict; classify only exact documented HB syntax in HIL evidence and require TEL sequence/uptime alignment; malformed or unaligned lines remain anomalies |
| Passive telemetry is used to assert an exact firmware image | Protocol v1 has no version field | Record the frozen interface commit separately and label current firmware `UNCONFIRMED_PASSIVE_ONLY` until active identity or flash evidence is explicitly authorized |
| USB driver toggles RTS/DTR despite a receive-only API | Not electrically excluded | Construct pyserial with no port, request DTR/RTS inactive before open, send no application bytes, and require separate device-specific review when control lines affect reset/boot |
| A golden file is edited together with a regression and hides compatibility drift | Phase 4 contract frozen | Reconstruct manifests/results in tests, hash independent fixtures, require schema/version migration for breaking changes, and never regenerate expectations merely to make a failure pass |
| Phase 5 UI duplicates profile or device business logic | Phase 4 boundaries frozen | Make CLI/worker/Dashboard consume public adapters/workflows; keep device parsing in profiles and enforce dependency/compatibility tests |
