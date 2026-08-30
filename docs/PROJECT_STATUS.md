# Project Status

**Last updated:** 2026-08-29  
**Current milestone:** Software Phase 1 — Step 6 of 8 complete  
**Release maturity:** pre-MVP / architecture and protocol foundation  
**Highest evidence level:** HOST_TEST  
**Verified hardware claims:** 0

## Current product baseline

The repository currently provides an installable, controller-neutral Python core for Analog Validation Studio. It includes explicit measurement provenance, device capabilities and safe ranges, test-run conclusion semantics, one CRC/framing implementation, and the versioned AFE v1 profile.

It does not yet provide a complete adapter, test runner, CLI, dashboard, serial transport, or validated physical AFE.

## Software Phase 1 checkpoints

| Step | Deliverable | Status | Evidence |
|---:|---|---|---|
| 1 | Installable `src/analog_validation` package and reproducible wheel | Complete | HOST_TEST |
| 2 | Stable public error hierarchy | Complete | HOST_TEST |
| 3 | Provenance-aware immutable Measurement model | Complete | HOST_TEST |
| 4 | Capability, safe range, and TestRun models | Complete | HOST_TEST |
| 5 | Single CRC implementation and bounded ASCII framing | Complete | HOST_TEST |
| 6 | Versioned AFE v1 telemetry, commands, capability exchange, and mappings | Complete | HOST_TEST |
| 7 | Versioned configuration models and safe validation | Next | Not run |
| 8 | Golden AFE messages, legacy migration, and Phase 1 closure | Planned | Not run |

## Current verification snapshot

| Gate | Result |
|---|---|
| Full pytest suite | 224 passed |
| Formal package statement coverage | 100% of 899 statements |
| Ruff | Passed on formal package and tests |
| mypy | Passed on formal package and tests |
| Package build and external install | Passed; external AFE v1 round trip returned true |
| Hardware bench validation | Not performed |

## Public claim boundary

Safe to claim now:

- designed and tested a controller-neutral Python protocol/domain foundation;
- implemented CRC-16/CCITT-FALSE and bounded ASCII framing;
- implemented a versioned AFE v1 profile with strict host-side validation;
- implemented explicit provenance and capability/safety semantics;
- maintained reproducible automated host tests and engineering reports.

Not safe to claim now:

- built or validated the physical analog front end;
- demonstrated ADC/DAC accuracy or UART reliability on hardware;
- verified any 0–3.3 V hardware range;
- completed an MSP430 hardware integration;
- released a software MVP or production-ready product.

## Next checkpoint

Software Phase 1 Step 7 will define versioned configuration models for profile selection, channels, units, safe output boundaries, timeouts, source labels, and schema validation. Configuration files will not be allowed to execute Python code.

## GitHub and LinkedIn presentation policy

- Update the repository README and this status page only after a checkpoint passes its real quality gates.
- Keep implemented, planned, and hardware-verified features visibly separate.
- Link every numerical claim to a report or reproducible test command.
- Present this as an independent personal product project; do not merge it with the OSU Lab Bench Monitor Capstone or the separate MSP430 equipment-health project.
- Prepare final LinkedIn wording only after the repository has a stable public demo and the owner has reviewed what will be public.
