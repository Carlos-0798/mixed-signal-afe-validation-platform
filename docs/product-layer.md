# Product layer contracts, services, CLI, worker, and reports

**Implemented:** Software Phase 5 Steps 1–8, 2026-08-31<br>
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
user intent
   |--------------------|
   v                    v
analog-validation CLI   local Dashboard
   |--------------------|
             v
analog_validation_app   request, catalog, services, worker, presentation
             |
             v
analog_validation       protocols, adapters, analysis, results
```

The dependency is one-way. The core and optional pyserial backend may not import
the product layer. Architecture tests reject copied protocol or analysis
implementations in `analog_validation_app`; the Step 2 worker additionally may
not import adapters, profiles, serial code, analysis, exports, or GUI modules.

## Versioned product contracts

| Contract | Purpose | Important safety rule |
|---|---|---|
| `product-job.v1` | Immutable user job intent | `allow_output` must be `false`; profile name and version are explicit |
| `product-result.v1` | Immutable terminal product state | Source and evidence must agree; limitations are mandatory and bounded |
| `product-job-event.v1` | Immutable worker state/progress event | Index is positive and monotonic; text and queue are bounded; only failures carry a safe issue |
| `product-catalog.v1` | Reviewed sources and profiles | Lookup is exact; an unknown profile is rejected rather than guessed |
| `user-issue.v1` | Stable user-facing failure explanation | Expected errors map by type; unexpected internal details are not exposed |
| `product-cli-output.v2` | Versioned machine-readable CLI output | Adds calibration result/coefficient artifacts while retaining schema/software, source, worker/product/engineering state, limitations, and an explicit no-hardware-performance claim |
| `product-workflow-config.v1` | Shared CLI/Dashboard typed workflow intent | Source-specific resources are mutually exclusive; Serial requires explicit receive-only confirmation |
| `live-monitor.v1` | Immutable bounded live points and control snapshot | Finite duration, bounded memory, cooperative pause/resume, and no engineering PASS/FAIL |
| `dashboard-wizard.v1` | Immutable six-step UI state | A reviewed request is invalidated by navigation/editing; finalized analyses and calibration coefficients use separate create-new exports |
| `human-report.v1` | Immutable presentation-only copy of a finalized result | No analysis methods; evidence/outcome/limitations remain unchanged |
| `human-report-manifest.v1` | Identity of one five-file report publication | Canonical input hash and rendered artifact hashes; explicit no-new-hardware-validation claim |

A product result is an engineering conclusion only when its finalized core
outcome is `PASS` or `FAIL`. `CANCELLED`, `INCOMPLETE`, `UNSUPPORTED`, and `ERROR`
cannot be displayed as successful validation.

## Worker lifecycle and ownership

`ProductJobWorker` is generic orchestration shared by the future CLI and
Dashboard. It does not know how to parse a profile, fit a line, open a serial
port, or draw a widget. A caller injects a `ProductJobService` factory; the
worker thread creates exactly one service, runs it, and calls `cleanup()` on
every path after creation.

```text
IDLE -> STARTING -> RUNNING -> SUCCEEDED
                    |  |        FAILED
                    |  +-----> CANCELLED
                    v
                CANCELLING
```

The diagram is a simplified lifecycle: factory, run, contract, or cleanup
failures end in `FAILED`; a cancellation request during startup or running ends
in `CANCELLED` after cleanup. Only one active job may exist. A second `start()`
is rejected instead of silently replacing the owner.

Cancellation is cooperative. The worker sets a thread-safe token, and a service
checks it at safe finite checkpoints. Python cannot safely kill an arbitrary
thread while it owns a file, adapter, or COM handle, so `join()` and `close()`
have explicit upper bounds and report timeout rather than pretending cleanup
happened. The non-daemon worker thread also prevents process exit from silently
abandoning a live resource owner.

Events use a bounded FIFO snapshot. When a slow future UI falls behind, the
oldest event is dropped and a cumulative dropped count is retained; memory does
not grow without limit. Event indexes remain globally increasing, so consumers
can detect a missed update.

Worker state and engineering outcome are deliberately separate:

- `SUCCEEDED` means orchestration ended normally; inspect the result, which may
  still be `INCOMPLETE` or `UNSUPPORTED`;
- a cancellation observed before terminal publication cannot produce PASS;
- a cleanup failure overrides apparent success and produces `FAILED`/`ERROR`;
- expected errors become bounded `UserIssue` guidance, while detailed exception
  text stays in the developer-only diagnostic field.

## Reviewed catalog

| Source | Evidence allowed by the contract | Jobs declared in Step 1 | Notes |
|---|---|---|---|
| `SIMULATOR` | `SYNTHETIC` | read, live monitor, DC, hysteresis, calibration, frequency response | Default; never a physical measurement |
| `CSV_REPLAY` | `CSV_REPLAY` | read, live monitor, DC, hysteresis, calibration, frequency response | Local replay; preserves lineage |
| `SERIAL_READ_ONLY` | `HOST_TEST` or `BENCH_CONTROLLER` | read only | Requires optional serial extra; exposes no product write command |

Two exact profile identities are reviewed:

- `afe/1` supports Simulator, CSV Replay, and receive-only serial sources.
- `msp430-equipment-health/1` is an independent peer-product telemetry profile
  and supports receive-only serial source only.

Catalog support states a software compatibility boundary. It does not prove that
a physical AFE, MSP430 firmware image, sensor, fan, wiring, or instrument works.

## Application services and current CLI

Step 3 adds one explicit adapter factory for each source. The post-beta
increments add calibration, frequency-response, and finite live-monitor
services alongside bounded read, formal DC evaluation, and formal hysteresis
evaluation. Calibration
acquires paired observed/reference records and publishes a finalized result plus
versioned coefficients. Frequency response acquires explicit Hz/input/output
triples, computes amplitude ratio and dB through the core, and evaluates a
reviewed cutoff target and minimum evidence size.
Live monitoring interleaves enabled channel reads by cycle and publishes copied
measurements into a bounded ring buffer. It exposes pause/resume only at safe
cooperative checkpoints and never maps successful orchestration to an
engineering PASS or FAIL.
The factory validates the exact catalog request before constructing a resource;
the worker thread then owns that resource through cleanup. A thread-safe output
slot publishes detailed read/export data only after a safe service checkpoint.

The service layer calls the frozen engineering APIs. It does not parse wire
fields, calculate a second line fit, infer saturation, estimate another
threshold, or reinterpret PASS/FAIL. Simulator and Replay analysis operate on
read-only observations and never invoke an output runner.

After installation:

```powershell
analog-validation --help
analog-validation version --json
analog-validation profiles
analog-validation simulate read --samples 3
analog-validation simulate dc --points 12 --json
analog-validation simulate hysteresis
analog-validation simulate calibration --points 8 --json
analog-validation simulate frequency --points 21 --json
analog-validation simulate monitor --cycles 10 --sample-interval 0.1 --json
analog-validation replay read --input .\data.csv --samples 2 --json
```

Calibration is available for Simulator and CSV Replay, not the receive-only
serial path. Its coefficient JSON uses strict bounded parsing, includes fit
lineage and source labels, and is written create-new by default. Loading a file
through `coefficients inspect` or the Dashboard validates and displays it but
does not automatically apply it to observations or firmware.

Frequency response is also available only for Simulator and CSV Replay. Its
deterministic Simulator has an explicit model cutoff independent of the
acceptance target; Replay requires three explicit same-source channel series.
Neither path generates a waveform, controls an instrument, calculates phase,
or authorizes serial output.

Live monitoring is likewise available only for Simulator and CSV Replay. It is
finite, limits total measurements and retained points, and treats its visible
time window as presentation state. Memory eviction, worker-event drops, and
measurement-quality failures remain three separate counters/meanings. See
[`live-monitoring.md`](live-monitoring.md).

`ports` performs discovery without opening a port. `observe` is the only real
serial entry and requires an exact port, profile, channel, unit, record/poll
bound, and `--confirm-read-only`. The product exposes no serial write operation.
Tests inject a memory backend with a write trap; the connected MSP430 was not
opened during Step 3.

Step 4 implements `report`. It loads one strict finalized JSON/CSV result, builds
an immutable display view, and creates text, Markdown, HTML, SVG, and manifest
files in a new directory. The DC line uses exported predicted values, the
hysteresis chart uses exported direction/transition data and copied threshold
metrics, the calibration chart uses exported before/after signed errors, and
the frequency chart uses exported gain dB/cutoff values on a logarithmic axis;
none calls an analysis or evaluator. `demo` remains the stable one-command
synthetic DC portfolio workflow and does not silently substitute another test.

Step 5 adds `analog_validation_app.dashboard` as a headless-first presentation
boundary. Immutable state/actions and the owner-thread presenter copy only the
reviewed catalog, product request/result/event, structured issue, and finalized
human-report view. The controller polls the existing bounded worker and performs
cooperative cancel/close; it does not construct an adapter or engineering
service. Widgets render the six text/table regions and emit callbacks only.
`app.py` imports Tk lazily after the explicit `dashboard` command.

Step 6 adds `product_workflows.py` as the single typed compiler used by CLI and
Dashboard, `dashboard/wizard.py` as the fixed source/test/configure/review/run/
result state machine, and `dashboard/application.py` as the reviewed handoff to
the worker. Simulator remains default. Replay is fully parsed before Run. Serial
requires exact port/profile/bounds/confirmation and is not opened during Review.
The widgets expose criteria and callbacks but still do not own service creation,
analysis, PASS/FAIL, or I/O.

For an unknown command the CLI exits with code `2`, writes no result to stdout,
and explains:

1. what happened;
2. a possible cause;
3. a safe next step.

The default path does not print a Python traceback. Complete engineering FAIL,
incomplete evidence, unavailable capability/dependency, operation error,
unexpected defect, and interrupt use distinct exits 1, 3, 4, 5, 70, and 130.
See the [CLI guide](product-cli.md) for exact commands and semantics.

## Installation and evidence boundary

The current wheel was installed in a fresh short-path directory outside the
repository with `--no-deps`. Base import left both Tk and pyserial unloaded; the
installed CLI generated two byte-identical 12-artifact `SYNTHETIC` demos in
normal and Unicode destinations. The same code also passed real Windows Tk
focus/scaling smoke at 1.0, 1.5, and 2.0; no port was accessed.
`ports` still fails before discovery when the optional serial dependency is
absent. A subprocess interpreter interrupt reached `CANCELLED`, cleanup, and exit
130. No COM port was enumerated or opened in Step 7. A first installation under
the repository's unusually deep `work/` path hit Windows `WinError 206`; the
same wheel passed from the shorter repository-external path, so the path-length
condition is documented rather than hidden.

This proves packaging, dependency isolation, deterministic CLI behavior, and
host-side product-contract logic. It does not add hardware evidence. The earlier
receive-only MSP430 UART capture remains a separate, narrowly scoped
`BENCH_CONTROLLER` result.

## Phase closure and next checkpoint

Software Phase 5 Step 8 freezes the product public exports, schemas, CLI and
exit-code surface, worker states, report fields, demo manifest, and issue
families. The isolated build, repository-external base/serial installation
matrix, installed deterministic demos, and real Windows Dashboard launch/close
passed without operating a physical port. The phase is closed as Software Beta.

Software Phase 6 now owns hosted CI, supported-environment testing,
release-candidate versioning, documentation/publication audit, and any
owner-approved GitHub release. Hardware is not required by default. See the
[Phase 5 compatibility contract](phase5-public-api.md),
[software demo](software-demo.md), [product-quality acceptance](product-quality-acceptance.md),
and [Step 8 closure report](../reports/software-phase5-step8.md).
