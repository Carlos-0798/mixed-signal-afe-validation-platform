# Software Phase 4 Step 8 and Closure Report

**Date:** 2026-08-31<br>
**Milestone:** golden compatibility, packaging, and Software Phase 4 closure<br>
**Software evidence:** HOST_TEST / SYNTHETIC / CSV_REPLAY<br>
**Separate physical evidence:** Step 7 `BENCH_CONTROLLER` UART compatibility only<br>
**Step 8 hardware operation:** no port opened; no HIL repeated<br>
**Verified AFE hardware performance claims:** 0

**Compatibility implementation commit:**
`269b9141e791d247b053ea38b3ee2da8d49a5a37`

## Outcome

Software Phase 4 is complete: 8 of 8 checkpoints passed. The product now has a
bounded controller-neutral byte/serial transport, raw provenance, independent
AFE and MSP430 business profiles, a receive-only serial adapter, an optional
pyserial operating-system boundary, a narrowly scoped physical controller UART
record, and executable public compatibility contracts.

Step 8 did not add product behavior. It froze the approved interfaces and exact
representative results, reran every historical contract, built isolated source
and wheel artifacts, and installed the wheel in clean environments with and
without the optional serial dependency. No serial port was opened in Step 8.

## Completed checkpoints

| Step | Delivered | Evidence |
|---:|---|---|
| 1 | Bounded LF byte stream and 2–64-bit modular sequence tracking | HOST_TEST |
| 2 | Namespace-neutral CRC envelope, AFE wrapper compatibility, and explicit channel mapping | HOST_TEST |
| 3 | Driver-neutral discovery/session lifecycle, finite reconnect, and bounded raw events | HOST_TEST |
| 4 | Stateful AFE v1 profile, canonical Measurements, capabilities, and 16-bit continuity | HOST_TEST |
| 5 | Independent read-only MSP430 profile, sentinels/faults, and 32-bit continuity | HOST_TEST |
| 6 | Receive-only SerialAdapter, AFE/MSP workflows, failure bounds, and zero-write runner degradation | HOST_TEST |
| 7 | Optional pyserial backend and owner-authorized five-record passive MSP430 UART capture | BENCH_CONTROLLER — limited |
| 8 | Public API/composite freeze, full regression, isolated build, external installs, and closure | HOST_TEST |

## Frozen compatibility contract

`phase4_public_api.json` freezes:

- 121 public exports across seven Phase 4 namespaces;
- three schema versions and four stable identity/privacy constants;
- 12 enum/flag member sets;
- 21 primary public constructor/function shapes;
- 17 error inheritance relationships;
- five golden fixture hashes;
- package ownership and the optional backend's no-write surface.

`phase4_composite_v1.json` freezes two external-backend product chains:

- AFE capability exchange plus two telemetry records across `65535 -> 0`, four
  canonical Measurements, and one retained CRC rejection;
- MSP430 records across `4294967295 -> 0`, valid values, explicit unavailable
  sentinels/fault mapping, and one retained CRC rejection.

Both exact composites are `HOST_TEST`; neither uses or upgrades physical data.

| Frozen file | SHA-256 |
|---|---|
| `afe_v1_invalid.csv` | `cd480cf37d07ddfdda0e8d4686411418bbf5d301265ddf06c74258be19f9fbd6` |
| `afe_v1_valid.csv` | `a1875a35c20241b277890ddb5af3ec25c7e977c6c91ce295e5502ae89e229095` |
| `msp430_equipment_health_v1.json` | `779e434ffbd7c052723b5069aa34ccafb569826312c24108381ba3ff54488516` |
| `profile_neutral_envelope_v1.json` | `2fc6b57b79afe1bbb328f8e3983f0a6856920922823cbdff7c126423b31e1762` |
| `phase4_composite_v1.json` | `9059a4fd1abff086c0f633dab2d17a07467966c1617aa830868245ed16cad1e5` |
| `phase4_public_api.json` (not self-hashed) | `72ff9b1dfed4b27672a17f65133fef966fa8668f0489d6ac45988bcf11a4d7f2` |

## Executed verification

| Gate | Actual result |
|---|---|
| New Phase 4 public/composite golden tests | PASS — 13 |
| Existing plus new golden suite | PASS — 133 |
| Phase 4 golden/integration focused selection | PASS — 149 |
| Architecture boundary | PASS — 6 |
| Full pytest suite | PASS — 1,526 tests |
| Formal + optional package coverage | PASS — 7,325/7,325 statements, 100% |
| Full-repository Ruff | PASS |
| mypy on `src`, `dashboard`, `tools`, and `tests` | PASS — 148 files |
| Local dependency check | PASS — no broken requirements |
| Isolated sdist and wheel build | PASS — `0.1.0.dev0` |
| Wheel contents | PASS — core/optional `py.typed`, optional backend, and serial-extra metadata |
| Sdist closure contents | PASS — both new fixtures/tests and the HIL tool included |
| External base wheel install | PASS — no pyserial present; installed external backend → MSP profile → adapter → workflow returned 42.1 °C as HOST_TEST |
| External `[serial]` wheel install | PASS — pyserial 3.5; read-only discovery returned COM5/COM4; no port opened |
| Installed dependency checks | PASS in both environments |
| Step 8 physical HIL | NOT RUN — Step 7 accepted evidence retained separately |

The isolated artifacts were:

| Artifact | Size | SHA-256 |
|---|---:|---|
| `mixed_signal_afe_validation_platform-0.1.0.dev0-py3-none-any.whl` | 156,305 bytes | `231173952C88A07D74F601609F066F81C2DD2446A9E4E3F8D717292189F9D223` |
| `mixed_signal_afe_validation_platform-0.1.0.dev0.tar.gz` | 286,807 bytes | `DEE50D20BE10C2CD169A69929740E4D440803DA6EF3EA77E91DE1F1507A5F089` |

Generated artifacts and clean virtual environments are verification outputs,
not committed release binaries.

## Phase 4 exit criteria

| Criterion | Result |
|---|---|
| Transport remains free of device business, analysis, GUI, and pyserial imports | PASS |
| AFE and MSP430 profiles retain independent identities, versions, fixtures, and capabilities | PASS |
| Fragmentation, coalescing, limits, CRC, sequence, timeout, disconnect, and bounded reconnect paths are tested | PASS |
| Raw bytes, errors, sequence, timestamp, profile, and provenance remain bounded and traceable | PASS |
| Read-only paths expose no write command or safe-shutdown capability | PASS |
| Host compatibility remains fully testable without hardware or pyserial | PASS |
| External structural backend works from an installed wheel | PASS |
| Public APIs, schemas, errors, fixtures, and representative product results are frozen | PASS |
| Step 7 physical and Step 8 host evidence remain separate | PASS |
| AFE and external MSP430 peripheral claims remain unverified | PASS — AFE hardware claims = 0 |
| Independent repository/product ownership remains intact | PASS |

## Safe claims after Phase 4

- implemented and fully host-tested bounded serial transport and raw provenance;
- implemented independent, versioned AFE and read-only MSP430 profiles without
  importing peer runtime code;
- composed both profiles through one receive-only DeviceAdapter/ReadWorkflow
  path;
- provided an optional packaged pyserial boundary while keeping the formal core
  driver-free;
- froze public exports, schemas, enums, signatures, errors, protocol fixtures,
  exact composite results, and evidence limits with executable tests;
- installed and exercised the package outside the repository with an
  independently defined structural backend;
- completed one separately reported five-record receive-only MSP430 UART
  compatibility capture in Step 7 with zero application writes.

## Explicitly not implemented or verified

- no owning serial worker, cancellation controller, product CLI, Dashboard,
  plotting, beginner wizard, or human-readable result report;
- no long-duration OS serial timing or deliberately induced physical
  disconnect/reconnect test;
- no exact passive firmware identity;
- no external MSP430 sensor, INA219, fan, MOSFET, 5 V supply, or wiring result;
- no physical AFE, ADC/DAC accuracy, gain, cutoff, hysteresis, saturation,
  protection, bandwidth, noise, repeatability, or electrical-safety result;
- no production-ready software or v1.0 release claim.

## Next milestone

Software Phase 5 has not started. Its first checkpoint must be a file-level plan
for a stable CLI, owning/cancellable serial worker, evidence-visible Dashboard,
plots, human-readable reports, beginner workflow, and at least one end-to-end
demo. The plan must reuse the frozen core rather than putting device-specific
logic into the UI, and physical operations must remain separately authorized.
