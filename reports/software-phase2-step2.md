# Software Phase 2 Step 2 Report

**Date:** 2026-08-29<br>
**Milestone:** reusable DeviceAdapter contract tests<br>
**Evidence class:** HOST_TEST<br>
**Hardware used:** none

## Outcome

Software Phase 2 Step 2 is complete. The repository now has a reusable read-only adapter contract that concrete Simulator and CSV Replay test classes can inherit instead of copying behavioral tests.

The contract is test infrastructure. The reference adapter used in this step is not a product adapter and does not provide a software demo or physical measurement.

## Shared contract

Every conforming read-capable adapter must pass the same checks for:

1. initial `DISCONNECTED` state and explicit provenance;
2. connection entering `CONNECTED_READ_ONLY`;
3. explicit, cached, typed capabilities;
4. rejection of reads before capability confirmation;
5. typed Measurement channel, unit, and evidence-source consistency;
6. unknown-channel classification as `CapabilityError`;
7. idempotent safe shutdown and blocked post-shutdown reads;
8. idempotent disconnect, state cleanup, reconnect, and resumed reading.

Concrete tests provide an `AdapterContractSpec` with a factory, evidence source, analog channel, and unit. Pytest inherits the suite through `ReadOnlyAdapterContract`.

## Executed verification

| Gate | Result |
|---|---|
| Reusable contract against HOST_TEST reference adapter | PASS — 8 shared checks |
| Full pytest suite | PASS — 368 tests |
| Formal package statement coverage | PASS — 1,392/1,392, 100% |
| Full-repository Ruff | PASS |
| mypy on `src dashboard tools tests` | PASS — 50 source files |
| Isolated sdist and wheel build | PASS |
| Three reusable contract files present in sdist | PASS |
| Wheel excludes repository test infrastructure | PASS |
| Hardware connection | NOT RUN |

## Explicit evidence boundary

`ContractReferenceAdapter` is a test double with deterministic in-memory HOST_TEST data. It is not the planned `SimulatorAdapter`, a CSV replay, serial device, MSP430 connection, or laboratory instrument. No physical input, output, timing, shutdown, or electrical behavior was tested.

## Next checkpoint

Step 3 will add the first real product adapter: a deterministic, read-capable `SimulatorAdapter` with explicit `SYNTHETIC` Measurements. Its tests must inherit all eight shared contract checks in addition to simulator-specific reproducibility tests.
