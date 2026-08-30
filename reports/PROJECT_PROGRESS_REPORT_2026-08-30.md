# Project Progress Report and Forward Plan — Analog Validation Studio

**Report date:** 2026-08-30 (America/New_York)<br>
**Product:** Configurable Analog Front-End & Validation Platform / Analog Validation Studio<br>
**Current milestone:** Software Phase 4, Step 2 of 8 complete<br>
**Release maturity:** pre-MVP<br>
**Highest accepted evidence:** HOST_TEST<br>
**Verified AFE hardware claims:** 0

## 1. Executive summary

Analog Validation Studio is an independent, controller-neutral validation and test-automation product. Software Phases 1–3 are complete within host, synthetic, and replay evidence boundaries. They provide versioned data models, protocol/configuration contracts, adapter lifecycles, deterministic simulation, CSV replay, safety-gated runners, DC/hysteresis/calibration/frequency analysis, acceptance mapping, and structured result export.

Software Phase 4 started from the exact Phase 3 baseline commit `9ac23494b86212928185de9b0eef1c1a82a8c0ea`. Step 1 is complete at commit `299a1407a025f30c954b1387883a43e3f224de91`: a profile-neutral bounded byte-stream state machine and 2–64-bit modular sequence tracker are implemented and fully host-tested. Step 2 now adds a namespace-neutral token/CRC envelope, retains the frozen AFE wrapper unchanged at its public boundary, freezes explicit AFE channel naming conversion, and connects fragmented byte-stream input to envelope decoding in a mixed-profile host integration test.

The software core is mature and well-tested, but the end-user product is not complete. OS serial access, independent controller profiles, SerialAdapter orchestration, CLI, Dashboard, human-readable reports, release automation, and physical AFE validation remain. No hardware performance claim is made.

## 2. Product identity and peer-project boundary

Analog Validation Studio and MSP430 Equipment Health Controller are peer, independent products. Neither is a subordinate, accessory, host, or required runtime component of the other, and there is no plan to merge their repositories or product identities.

- Analog Validation Studio owns generic acquisition, adapters, Measurements, validation algorithms, test execution, evidence handling, and reports.
- MSP430 Equipment Health Controller owns its firmware, sensing, FRAM behavior, thermal-control policy, device state, and UART business protocol.
- Compatibility is provided only through public, versioned interfaces and an independent `msp430-equipment-health.v1` profile/adapter in this repository.
- Each project retains its own repository, version, README, tests, release evidence, portfolio narrative, and future product roadmap.
- MSP430 test counts, FRAM results, and soak results are not counted as Analog Validation Studio acceptance evidence.
- OSU Lab Bench Monitor Capstone remains separate from both independent projects and is not copied or merged into either one.

## 3. Repository baseline

- Repository: `https://github.com/Carlos-0798/mixed-signal-afe-validation-platform`
- Current branch: `phase4/serial-profiles`
- Phase 3 baseline: `9ac23494b86212928185de9b0eef1c1a82a8c0ea`
- Phase 4 Step 1 implementation: `299a1407a025f30c954b1387883a43e3f224de91`
- Phase 4 Step 2 implementation: `95c1432febdce70007daba013cae4cce47cf8556`
- Package version: `0.1.0.dev0`
- License status: all rights reserved; no open-source license selected
- Python support target: 3.10 or later
- Current verified environment: Python 3.12 on Windows

## 4. Completed software phases

| Phase | Status | Main outcome | Strongest evidence |
|---|---|---|---|
| 0 — foundation | Complete | Independent repository, assumptions, theory, simulation plan, UART/CRC baseline, simulator/parser/tests | HOST_TEST |
| 1 — domain/protocol/config | Complete, 8/8 | Installable package, evidence-aware models, AFE v1, strict config, frozen protocol compatibility | HOST_TEST / SYNTHETIC |
| 2 — adapters/replay/workflow | Complete, 8/8 | DeviceAdapter safety lifecycle, Simulator, CSV Replay, shared read workflow | HOST_TEST / SYNTHETIC / CSV_REPLAY |
| 3 — analysis/runners/results | Complete, 8/8 | DC/hysteresis runners and criteria, calibration, frequency analysis, JSON/CSV results | HOST_TEST / SYNTHETIC / CSV_REPLAY |
| 4 — serial/profiles | In progress, 2/8 | Profile-neutral stream/sequence, CRC envelope, AFE wrapper compatibility, and channel mapping | HOST_TEST |
| 5 — CLI/Dashboard/reports | Planned | End-user workflow and human-readable product experience | None yet |
| 6 — product release | Planned | Installation, CI, user/developer docs, release candidate | None yet |

## 5. Current verified results

- 1,130 pytest tests pass.
- Formal `src/analog_validation` package coverage is 5,846/5,846 statements, 100%.
- Step 1 adds 32 focused tests and covers 158/158 new transport statements.
- Step 2 adds 51 tests; envelope, channel mapping, and AFE wrapper cover 176/176 statements.
- CRC-16/CCITT-FALSE is frozen with `123456789 -> 0x29B1`.
- AFE v1 retains 20 valid and 9 invalid golden wire/error cases.
- Phase 2 and Phase 3 public APIs and exact representative results remain frozen.
- Full-repository Ruff passes; mypy passes on all 110 source/test files under `src`, `dashboard`, `tools`, and `tests`.
- The sdist/wheel build includes transport, envelope, and channel-mapping modules; a clean repository-external virtual environment installs the wheel and passes mixed-profile envelope, bounded-feed, and 32-bit-wrap smoke tests.
- No serial port or physical hardware was used by the accepted Steps 1–2 checkpoints.

The original Phase 4 baseline test command first reached 1,040 passes and seven pytest setup errors because its requested generated `work/` parent directory did not exist. No product assertion failed. The unchanged baseline then passed 1,047/1,047 after creating the ignored generated directory. This corrected rerun is the authoritative pre-change result; the original setup failure is not hidden or relabeled as a PASS.

The first wheel-install path was too deep for the current Windows long-path configuration, so that installation was rejected as evidence even though the package build succeeded. The authoritative external smoke used a new short system-temporary path, installed the built wheel in a clean virtual environment, and passed. An initially mis-escaped newline in the smoke expression was diagnosed rather than treated as a product failure; the corrected bytes expression passed in the same installed environment.

## 6. End-to-end and integration audit

The existing internal chains are connected and tested at the library level:

- AFE record -> protocol model -> Measurement -> analysis -> criteria -> structured export;
- Simulator -> ReadWorkflow -> analysis -> structured export;
- CSV Replay -> ReadWorkflow -> analysis/export-compatible Measurements;
- output-capable reference adapter -> safety preflight -> DC/hysteresis runner -> cleanup -> TestRun result.
- fragmented mixed AFE/MSP record bytes -> bounded LF stream -> neutral CRC envelope -> ordered fields.

Two product-level gaps remain important:

1. there is no stable end-user orchestration entry that connects configuration, adapter selection, acquisition, analysis, criteria, export, and report in one command;
2. Simulator and CSV Replay are intentionally read-only, so output-controlled DC/hysteresis runners correctly return `UNSUPPORTED`; a separate explicitly synthetic output-capable product path or an offline demonstration workflow is still required for the final user demo.

The previous channel-name gap is now closed by `afe-channel-map.v1`. Historical `telemetry_to_measurements()` output remains unchanged; future serial profiles must cross the explicit mapping boundary before using canonical adapter/workflow names.

These are integration/productization gaps, not evidence that the implemented Phase 1–3 algorithms are failing.

## 7. MSP430 alignment status

The separate MSP430 project provides a useful, already-stable interoperability target:

- ASCII UART at 115200 baud, 8-N-1, LF/CRLF, maximum 128-byte records;
- the same CRC-16/CCITT-FALSE parameters;
- `TEL/CMD/ACK/STS/CFG/LOG` message families;
- 32-bit telemetry sequence and device `uptime_ms`;
- frozen reference commit `151fdcfa60661bce1ba04af13c1d3509706f7d4a`;
- frozen normal firmware `0.3.2-phase6-protocol`.

The two protocols share transport principles but not business messages. AFE remains `AFE,1,...` with its own 16-bit sequence and capabilities. The first MSP430 compatibility profile will be read-only, will preserve raw frames and device faults, and will not expose fan PWM as AFE stimulus.

A prior exploratory read-only COM4 capture proved feasibility by receiving five consecutive valid `TEL` frames with no parser/CRC errors. It is not yet an accepted Analog Validation Studio HIL result because it did not run through the future SerialAdapter/profile path. The reported unavailable sentinels and fault `0x0015` are device availability state, not measured temperature/current values.

## 8. Evidence and claim boundary

Safe to claim now:

- designed and host-tested a controller-neutral, evidence-aware analog validation software core;
- implemented deterministic simulation, strict CSV replay, versioned AFE protocol/configuration, safety-gated test runners, explainable analysis, and structured results;
- implemented a profile-neutral bounded byte-stream and modular sequence foundation;
- implemented a namespace-neutral CRC envelope, frozen AFE compatibility wrapper, and explicit legacy/canonical channel mapping;
- preserved compatibility through golden records, frozen public contracts, full coverage, and reproducible reports;
- designed a peer-project MSP430 compatibility path through an independent versioned adapter.

Not safe to claim now:

- completed a product-ready CLI, Dashboard, installer, or public v1.0 release;
- completed an MSP430 integration through this product's formal SerialAdapter;
- validated physical AFE gain, cutoff frequency, hysteresis, ADC/DAC accuracy, voltage range, bandwidth, noise, or reliability;
- validated MSP430 external sensors, INA219, MOSFET, fan, or full equipment-health behavior;
- inherited MSP430, OSU, simulated, or replay evidence as AFE hardware proof.

## 9. Forward software plan

### Software Phase 4 — serial transport and peer profiles

Estimated 5–8 effective development days for the full phase. Remaining Steps 3–8 will deliver a serial backend/lifecycle and raw-event boundary, AFE serial profile, independent read-only MSP430 profile, SerialAdapter integration, optional owner-approved read-only LaunchPad HIL, and Phase 4 compatibility closure.

### Software Phase 5 — product workflow and presentation

Estimated 5–8 effective development days. Deliver a stable CLI, Dashboard, beginner test wizard, charts, human-readable reports, example projects, and at least one reproducible end-to-end demonstration.

### Software Phase 6 — product release

Estimated 4–7 effective development days. Deliver clean-environment installation, CI, user/developer adapter documentation, examples, changelog/version/license review, privacy/evidence audit, and a release candidate suitable for GitHub presentation.

Risk-adjusted expectation for a mature independent software v1 is approximately 16–27 effective development days: about 2–3 focused weeks or 3–5 weeks at a beginner/part-time pace.

## 10. Future hardware plan

Hardware remains a second, optional product-development track after the software is mature:

1. freeze BOM, exact part variants, instruments, and safety assumptions;
2. perform unpowered receipt, continuity, polarity, rail-isolation, and common-ground checks;
3. assemble protected power/VBIAS and one block at a time;
4. validate buffer/gain stages, RC response, Schmitt thresholds/hysteresis, saturation, protection, and ADC conversion with real instruments;
5. run repeatability, fault, disconnect, and controller-independence tests;
6. integrate through the same public adapter/profile interfaces;
7. optionally create a PCB only after the breadboard evidence is stable.

A complete breadboard/BENCH program is expected to require roughly 8–14 weeks at a beginner part-time pace after parts and instruments are available. A PCB-quality version is likely 10–16 weeks or more. Software estimates do not include procurement lead time.

## 11. Main risks and controls

| Risk | Control |
|---|---|
| Protocols become coupled | Separate AFE/MSP profiles, explicit versions, no cross-repository runtime import |
| Upstream evidence is overclaimed | Repository-owned tests/reports and explicit evidence provenance |
| Damaged serial input grows memory | Bounded stream buffer and discard-to-LF recovery |
| Sequence wrap is misclassified | Profile-selected 16/32-bit tracker and half-range tests |
| Unavailable MSP data becomes false zero | Sentinel/fault-aware mapping with raw-field retention |
| Read-only device gains output capability | Default-deny capabilities; no `SAFE_SHUTDOWN` or stimulus in MSP v1 |
| Product demo remains fragmented | Phase 5 product orchestration and end-to-end acceptance gate |
| Hardware claims exceed instruments | Separate DMM/scope/controller evidence and explicit NOT RUN results |

## 12. Immediate next checkpoint

Software Phase 4 Step 3 will:

1. define a replaceable serial backend interface without coupling the core to one OS driver;
2. model discovery, deterministic open/read/timeout/close, bounded retry, disconnect, and reconnect behavior;
3. retain bounded raw receive events with UTC time, port identity, selected profile, parse outcome, and error context;
4. use an in-memory backend for the first acceptance path so every failure branch is deterministic and hardware optional;
5. keep actual COM access, command transmission, and the connected MSP430 outside this checkpoint.

Step 3 will not send a device command, flash a board, change firmware/FRAM, or claim physical compatibility.

## 13. Portfolio presentation plan

The GitHub presentation will continue to separate implemented, planned, and physically verified capabilities. Each completed checkpoint should update README/status, link a reproducible acceptance report, and preserve exact evidence boundaries. Final LinkedIn wording should present Analog Validation Studio and MSP430 Equipment Health Controller as two independent projects with a demonstrated public interoperability interface, not as one combined project or a parent/child system.
