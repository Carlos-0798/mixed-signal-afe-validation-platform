# Reports

No hardware validation report exists. Reports must preserve the evidence labels defined in `docs/test-plan.md`.

Software checkpoint reports (each report states its own evidence level):

- `software-phase4-step8.md` — Software Phase 4 closure: public API/composite golden freeze, full regression, isolated build, base/serial external installs, phase exit criteria, and strict separation of Step 7 UART evidence from AFE/peripheral claims.
- `software-phase4-step7.md` — optional pyserial backend, base/serial external installs, repository-owned receive-only COM4 HIL, CRC/sequence/uptime/fault evidence, legacy-HB classification, zero-write proof, and exact-firmware/AFE limitations. This report includes narrow `BENCH_CONTROLLER` evidence and is not a physical AFE report.
- `software-phase4-step6.md` — receive-only SerialAdapter composition, explicit AFE capability projection, AFE/MSP shared adapter/workflow contracts, bounded failure/reconnect behavior, zero-write runner degradation, package/install evidence, and no-COM boundary.
- `software-phase4-step5.md` — independent read-only MSP430 Equipment Health v1 profile, frozen peer-interface reference, repository-owned fixtures, sentinel/fault mapping, 32-bit continuity, build/install evidence, and no-COM boundary.
- `software-phase4-step4.md` — generic serial-profile contract, independent AFE v1 integration, canonical telemetry, capability/sequence semantics, golden migration, build/install evidence, and hardware limits.
- `software-phase4-step3.md` — driver-neutral serial lifecycle, finite reconnect, bounded memory-only raw events, failure injection, build/install evidence, and real-port limits.
- `software-phase4-step2.md` — namespace-neutral CRC envelope, frozen AFE wrapper compatibility, explicit channel mapping, composite stream path, build/install verification, and hardware limits.
- `software-phase4-step1.md` — profile-neutral bounded byte stream, modular sequence tracking, package verification, and serial/hardware evidence limits.
- `software-phase3-step8.md` — Software Phase 3 closure: public API and exact result golden freeze, full regression, external install, exit criteria, and remaining boundaries.
- `software-phase3-step7.md` — versioned result bundle, deterministic JSON/CSV, safe file publication, typed builders, and executed Step 7 verification.
- `software-phase3-step6.md` — immutable linear calibration, derived-record lineage, offline frequency response, cutoff semantics, packaging verification, and evidence limits.
- `software-phase3-step5.md` — directional hysteresis analysis/criteria/runner, transition lineage, cycle statistics, safety gates, and incomplete-evidence behavior.
- `software-phase3-step4.md` — safety-gated DC plan/runner, reference output lifecycle, partial evidence, read-only adapter degradation, packaging verification, and hardware limits.
- `software-phase3-step3.md` — versioned DC criteria, per-rule results, PASS/FAIL/INCOMPLETE mapping, evidence consistency, build/install verification, and hardware limits.
- `software-phase3-step2.md` — formal DC sweep pairing, point-level quality/saturation decisions, linear metrics, incomplete-analysis semantics, build/install verification, and evidence limits.
- `software-phase3-step1.md` — common analysis schema, record lineage, quality policy, voltage normalization, focused/full tests, build/install verification, and evidence limits.
- `software-phase3-planning.md` — Software Phase 3 file-level plan, architecture decisions, eight implementation checkpoints, approval boundary, and hardware evidence limits.
- `software-phase2-step8.md` — Software Phase 2 closure: public API and end-to-end golden compatibility freeze, full regression, external install, exit criteria, and remaining boundaries.
- `software-phase2-step7.md` — shared Simulator/CSV read workflow, atomic capability degradation, incomplete replay semantics, lifecycle cleanup, and evidence limits.
- `software-phase2-step6.md` — formal CsvReplayAdapter playback, timing, pause/resume, EOF, provenance conversion, shared contract, and packaging evidence.
- `software-phase2-step5.md` — strict immutable CSV Replay v1 models/parser, valid/invalid golden data, resource limits, and evidence boundaries.
- `software-phase2-step4.md` — configurable Simulator non-idealities, saturation/hysteresis behavior, fault injection, and deterministic regression.
- `software-phase2-step3.md` — deterministic read-only SimulatorAdapter, shared AFE generator migration, contract conformance, reproducibility, smoke output, and evidence limits.
- `software-phase2-step2.md` — reusable eight-check adapter contract, reference test execution, full regression, packaging, and evidence limits.
- `software-phase2-step1.md` — DeviceAdapter public contract, lifecycle/safety gates, typed adapter errors, and the first Software Phase 2 verification checkpoint.
- `software-phase1-step8.md` — Software Phase 1 closure: AFE golden compatibility, deterministic 100-frame provenance pipeline, legacy migration, architecture boundary, release-style gates, and remaining limits.
- `software-phase1-step7.md` — strict versioned JSON configuration, layered output gates, device-capability matching, hostile-input tests, package verification, and evidence limits.
- `software-phase1-step6.md` — versioned AFE v1 telemetry/commands/capability exchange, domain mappings, safety distinctions, package verification, and GitHub presentation update.
- `software-phase1-step5.md` — single CRC implementation, bounded strict framing, golden vectors, compatibility regression, package verification, and UART evidence limits.
- `software-phase1-step4.md` — explicit device capabilities, safe ranges, test-run conclusion semantics, package verification, and hardware evidence limits.
- `software-phase1-step3.md` — provenance-aware immutable measurement model, controlled units, quality consistency, package verification, and evidence limits.
- `software-phase1-step2.md` — stable public exception hierarchy, capture semantics, static checks, and migration boundary.
- `software-phase1-step1.md` — installable package, version, build, clean wheel import, and current limitations for Software Phase 1 Step 1.
- `software-phase0-baseline.md` — current Software Phase 0 execution baseline, audit outcome, limitations, and Software Phase 1 entry decision.
- `phase0-validation.md` — original design/synthetic/SPICE Phase 0 report retained for history.
