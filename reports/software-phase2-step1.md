# Software Phase 2 Step 1 Report

**Date:** 2026-08-29<br>
**Milestone:** DeviceAdapter contract and lifecycle safety gates<br>
**Evidence class:** HOST_TEST<br>
**Hardware used:** none

## Outcome

Software Phase 2 Step 1 is complete. The formal package now exposes a controller-neutral `DeviceAdapter` base contract and six explicit lifecycle states. Public methods own common safety and validation behavior; later Simulator, CSV, serial, MSP430, and instrument adapters implement only protected source-specific hooks.

This is an adapter foundation, not a complete adapter or software MVP.

## Implemented contract

```text
DISCONNECTED
  -> CONNECTED_READ_ONLY
  -> CAPABILITIES_CONFIRMED
  -> ARMED
  -> RUNNING
  -> SAFE_SHUTDOWN
  -> DISCONNECTED
```

- connection cannot implicitly authorize output;
- reads require explicit capabilities and declared channels/commands;
- returned measurements must match the requested channel, declared unit, and adapter evidence source;
- arming requires `allow_output=true`, matching profile/version/source, safe ranges, output capability, and safe-shutdown capability;
- stimulus is limited by both configuration and device ranges;
- safe shutdown is idempotent and clears authorization;
- disconnect from `ARMED`/`RUNNING` attempts safe shutdown first and resets logical state even when a hook reports an error;
- unexpected adapter-hook exceptions are chained into stable adapter error families.

## Executed verification

| Gate | Result |
|---|---|
| New adapter unit tests | PASS — 36 |
| Full pytest suite | PASS — 360 |
| Formal package statement coverage | PASS — 1,392/1,392, 100% |
| Full-repository Ruff | PASS |
| mypy on `src dashboard tools tests` | PASS — 47 source files |
| Isolated sdist and wheel build | PASS |
| Repository-external wheel install and public adapter API smoke | PASS |
| Installed-package dependency check | PASS — no broken requirements |
| Hardware connection | NOT RUN |

Tests cover state transitions, premature operations, capability caching, bad channels, unsupported commands, wrong models/units/sources, configuration mismatch, unsafe output, hook failures, idempotent shutdown, and disconnect cleanup.

## Explicit evidence boundary

No serial port, microcontroller, ADC, DAC, PWM, instrument, AFE circuit, or external voltage was used. `SAFE_SHUTDOWN` currently proves only the software contract and hook sequencing. It is not evidence that physical hardware reached a safe state.

## Next checkpoint

Step 2 will extract reusable adapter contract tests. Each concrete Simulator and CSV Replay adapter must pass the same behavior suite before it can be used by a shared upper-layer workflow.
