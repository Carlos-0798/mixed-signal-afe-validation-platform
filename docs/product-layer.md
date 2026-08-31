# Product layer contracts and CLI foundation

**Implemented:** Software Phase 5 Step 1, 2026-08-31<br>
**Evidence:** HOST_TEST and repository-external package installation<br>
**Hardware claim:** none

## Why this layer exists

`analog_validation` is the engineering core: it owns measurements, protocols,
adapters, analysis, criteria, and result meaning. `analog_validation_app` is the
product-facing layer: it translates a user's request into a controlled product
operation and translates expected failures into understandable guidance.

Keeping these responsibilities separate matters because a CLI or future GUI
should never become a second implementation of CRC, gain fitting, saturation
exclusion, or hysteresis math. There must be one engineering truth, with multiple
replaceable user interfaces above it.

```text
user / future Dashboard
          |
          v
analog-validation CLI
          |
          v
analog_validation_app     request, catalog, issue, future service/worker
          |
          v
analog_validation         protocols, adapters, analysis, results
```

The dependency is one-way. The core and optional pyserial backend may not import
the product layer. Step 1 architecture tests also reject copied protocol or
analysis implementations in `analog_validation_app`.

## Versioned product contracts

| Contract | Purpose | Important safety rule |
|---|---|---|
| `product-job.v1` | Immutable user job intent | `allow_output` must be `false`; profile name and version are explicit |
| `product-result.v1` | Immutable terminal product state | Source and evidence must agree; limitations are mandatory and bounded |
| `product-catalog.v1` | Reviewed sources and profiles | Lookup is exact; an unknown profile is rejected rather than guessed |
| `user-issue.v1` | Stable user-facing failure explanation | Expected errors map by type; unexpected internal details are not exposed |
| `product-cli-output.v1` | Deterministic machine-readable CLI output | JSON identifies schema and software version; hardware claim is explicitly `NONE` where applicable |

A product result is an engineering conclusion only when its finalized core
outcome is `PASS` or `FAIL`. `CANCELLED`, `INCOMPLETE`, `UNSUPPORTED`, and `ERROR`
cannot be displayed as successful validation.

## Reviewed catalog

| Source | Evidence allowed by the contract | Jobs declared in Step 1 | Notes |
|---|---|---|---|
| `SIMULATOR` | `SYNTHETIC` | read, DC analysis, hysteresis analysis | Default; never a physical measurement |
| `CSV_REPLAY` | `CSV_REPLAY` | read, DC analysis, hysteresis analysis | Local replay; preserves lineage |
| `SERIAL_READ_ONLY` | `HOST_TEST` or `BENCH_CONTROLLER` | read only | Requires optional serial extra; exposes no product write command |

Two exact profile identities are reviewed:

- `afe/1` supports Simulator, CSV Replay, and receive-only serial sources.
- `msp430-equipment-health/1` is an independent peer-product telemetry profile
  and supports receive-only serial source only.

Catalog support states a software compatibility boundary. It does not prove that
a physical AFE, MSP430 firmware image, sensor, fan, wiring, or instrument works.

## Current CLI

After installation:

```powershell
analog-validation --help
analog-validation version
analog-validation version --json
analog-validation profiles
analog-validation profiles --json
python -m analog_validation_app profiles
```

Step 1 deliberately exposes only product identity and reviewed profiles. It does
not yet run Simulator, replay, analysis, report, Dashboard, or serial jobs. Those
commands require the service and owning worker built in later checkpoints.

For an unknown command the CLI exits with code `2`, writes no result to stdout,
and explains:

1. what happened;
2. a possible cause;
3. a safe next step.

The default path does not print a Python traceback. This makes expected mistakes
actionable while keeping unexpected internal details out of normal user output.

## Installation and evidence boundary

The Step 1 wheel was installed in a fresh directory outside the repository with
`--no-deps`. `help`, `version`, `profiles`, and the module entry point ran while
`pyserial` was absent; neither `serial`, `analog_validation_pyserial`, nor
`tkinter` was imported. No COM port was enumerated or opened, and no window was
created.

This proves packaging, dependency isolation, deterministic CLI behavior, and
host-side product-contract logic. It does not add hardware evidence. The earlier
receive-only MSP430 UART capture remains a separate, narrowly scoped
`BENCH_CONTROLLER` result.

## Next checkpoint

Software Phase 5 Step 2 will add a bounded single-owner worker with cooperative
cancellation and deterministic cleanup. It will use injected host-side services
only: no real COM access, report generation, or Dashboard window is part of that
checkpoint.
