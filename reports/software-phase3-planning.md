# Software Phase 3 Planning Checkpoint

**Date:** 2026-08-30<br>
**Milestone:** file-level analysis and runner plan<br>
**Evidence class:** HOST_TEST<br>
**Hardware used:** none

## Outcome

The Software Phase 3 implementation plan is defined and ready for owner review. Implementation remains 0 of 8 checkpoints. No analysis API, runner, decision engine, export format, serial transport, controller integration, or hardware behavior was added by this planning checkpoint.

## Baseline audit

The audit found four important boundaries:

1. the legacy DC sweep implementation accepts bare floats, uses two points as sufficient, and reports only the number of excluded saturation points;
2. the legacy hysteresis implementation uses first-transition midpoints but does not verify sweep direction, repeated cycles, bounce, measurement quality, provenance, or record lineage;
3. Phase 2 `ReadWorkflowResult.COMPLETED` means acquisition completed and deliberately does not mean PASS;
4. the frozen production Simulator and CSV Replay adapters are read-only, while `DeviceAdapter` already supplies the output capability, configuration, range, and safe-shutdown gates needed by a future output-capable adapter.

These findings make a direct copy of the legacy functions unsafe for the formal product core.

## Frozen planning decisions

- pure analysis, runner lifecycle, acceptance decisions, and result export are separate layers;
- every included or excluded point keeps input record references and an explicit disposition;
- structural errors are rejected; measurement-quality problems are represented rather than silently discarded;
- analysis alone never produces an engineering PASS;
- output-controlled tests must preflight all setpoints and use existing DeviceAdapter safety gates;
- the Phase 2 read-only adapters and workflow compatibility contract remain unchanged;
- output runner behavior is tested with a host-only reference adapter, not physical equipment;
- calibration creates derived records and does not mutate raw evidence;
- frequency response is offline amplitude-point analysis only in this phase;
- Phase 3 closes only after golden compatibility, full regression, build, and external-install gates pass.

## Planned checkpoints

| Step | Deliverable | Current status |
|---:|---|---|
| 1 | Common analysis vocabulary and quality policy | Planned |
| 2 | Provenance-aware DC sweep analysis | Planned |
| 3 | Versioned DC criteria and TestRun mapping | Planned |
| 4 | Controller-neutral, safety-gated DC sweep runner | Planned |
| 5 | Directional hysteresis analysis and runner | Planned |
| 6 | Calibration and offline frequency response | Planned |
| 7 | Versioned CSV/JSON result export | Planned |
| 8 | Golden compatibility, packaging, and closure | Planned |

## Evidence boundary

This planning checkpoint does not validate an algorithm implementation or physical behavior. No serial port, microcontroller, ADC, DAC, PWM, instrument, AFE, wiring, voltage, accuracy, bandwidth, timing, or shutdown behavior was used or verified. Verified hardware claims remain zero.

## Executed baseline verification

| Gate | Final result |
|---|---|
| Full pytest suite | PASS — 644 tests |
| Formal package coverage | PASS — 2,230/2,230 statements, 100% |
| Full-repository Ruff | PASS |
| mypy on `src`, `dashboard`, `tools`, and `tests` | PASS — 67 source files |
| Dependency consistency | PASS — no broken requirements |
| Hardware bench validation | NOT RUN |

The project `.venv` launcher could not start under the restricted execution account because it referenced the interactive user's Python executable. The final run used the bundled Python 3.12.13 runtime with the already-installed project development packages. An initial retry reached 641 passes but three `tmp_path` fixtures could not access a stale user-owned pytest directory; the authoritative run used a new isolated writable base temp and completed 644/644. Neither incomplete attempt is reported as a product PASS.

These gates prove only that the existing Phase 2 software baseline remains healthy after the documentation/planning change. They do not prove that any planned Phase 3 feature exists.

## Next checkpoint

After owner continuation, Software Phase 3 Step 1 will implement only the common analysis vocabulary, point dispositions/exclusion reasons, record lineage, voltage normalization, and default quality policy. DC fitting and PASS/FAIL logic remain outside Step 1.
