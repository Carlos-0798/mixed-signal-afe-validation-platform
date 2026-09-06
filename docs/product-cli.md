# Analog Validation Studio CLI

**Implemented:** Software Phase 5 plus calibration, frequency-response, and bounded live-monitor product increments<br>
**Schema:** `product-cli-output.v2`<br>
**Default source:** deterministic software-only Simulator<br>
**Physical AFE claim:** none

## What the CLI is for

The `analog-validation` command turns the existing engineering core into a
repeatable product workflow. It does not contain a second CRC, line fit,
saturation rule, hysteresis calculation, or PASS/FAIL implementation. Instead,
it validates the user's intent, constructs one explicit adapter, and sends the
observations through the already tested workflow, analysis, criteria, and export
layers.

```text
CLI or reviewed Dashboard configuration
   -> shared product workflow compiler
   -> explicit source/profile factory
   -> owning cancellable worker
    -> DeviceAdapter + ReadWorkflow
    -> formal analysis + criteria + ResultExportBundle
    -> CLI result and optional presentation-only human report
```

This separation is important: changing the UI must not change the engineering
answer.

## First commands to run

From an activated development environment:

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
analog-validation demo --output .\analog-validation-demo
analog-validation dashboard
```

These Simulator commands are the safest beginner starting point. They use
deterministic synthetic observations, open no COM port, and send no bytes. A
Simulator PASS proves that the software pipeline produced the expected answer
for its model; it does not prove that a physical circuit has that gain,
saturation level, threshold, or cutoff frequency.

## Command map

| Command | Current behavior | Resource boundary |
|---|---|---|
| `version` | Show installed software identity | No adapter or optional dependency |
| `profiles` | List exact reviewed profile identities | Software support only; no device detection |
| `ports` | Discover minimal logical serial-port descriptions | Does not open a port; needs the optional `serial` extra |
| `simulate read` | Run a bounded deterministic read workflow | Synthetic software only |
| `simulate dc` | Read synthetic input/output observations, run formal DC analysis and criteria | No physical stimulus; no output runner |
| `simulate hysteresis` | Read a synthetic rising/falling cycle, run formal threshold analysis and criteria | No physical stimulus; no output runner |
| `simulate calibration` | Fit and evaluate a versioned linear mapping from paired synthetic channels | Synthetic software evidence; coefficients are not instrument-traceable |
| `simulate frequency` | Evaluate a deterministic single-pole amplitude response against an independent cutoff target | Explicit synthetic frequency/amplitude points; no waveform source or instrument |
| `simulate monitor` | Present a finite set of recent synthetic input/output/state observations | Bounded memory and duration; no engineering PASS/FAIL or hardware claim |
| `replay read` | Read an explicit local `csv-replay.v1` file | Preserves replay lineage; does not contact hardware |
| `replay dc` | Project two explicit analog channels and run formal DC analysis | File evidence only |
| `replay hysteresis` | Project explicit analog/state channels and direction counts | File evidence only |
| `replay calibration` | Fit paired observed/reference channels from one strict replay dataset | `CSV_REPLAY`; does not repeat or upgrade the original measurement |
| `replay frequency` | Evaluate three explicit replay channels containing Hz, input amplitude, and output amplitude | `CSV_REPLAY`; no physical sweep is performed |
| `replay monitor` | Present finite recent points from explicit replay channels | `CSV_REPLAY`; no port is opened and original evidence is not upgraded |
| `coefficients inspect` | Strictly load and display one `calibration-coefficients.v1` JSON file | Inspection only; never applies coefficients or contacts hardware |
| `observe` | Run one bounded receive-only serial read | Exact port/profile/channel plus `--confirm-read-only`; no write API |
| `report` | Turn one finalized JSON/CSV result export into five deterministic human-report files | No adapter, serial port, analysis, or hardware operation |
| `dashboard` | Launch the local six-step Tkinter/ttk validation workflow | Defaults to Simulator; Replay validates before Run; Serial remains explicit, bounded, and receive-only |
| `demo` | Run the fixed 24-point synthetic DC product chain and publish the exact portfolio package | Create-new local output only; no serial, network, physical stimulus, or hardware claim |

Run any command with `--help` to see its exact options. Sample and record counts
are bounded at the parser boundary, numeric values must be finite, and profile
identity is exact rather than guessed from a filename or USB description.

## Dashboard command

`analog-validation dashboard` lazily imports Tk and opens the six-step workflow
described in the [Dashboard guide](dashboard.md). Source, test, configuration,
review, Run, and result/export all use the same `prepare_product_job()` compiler
and worker services as the CLI. Closing the window first closes its bounded
worker owner. After safe closure, the optional `--json` view reports the selected
source/profile, final worker state, session schema, and
`NO_NEW_HARDWARE_VALIDATION`.

If Tk is unavailable, the CLI gives a structured explanation and suggests using
the existing terminal workflows rather than printing a traceback. Dashboard Run
does not change evidence class: Simulator remains `SYNTHETIC`, Replay remains
`CSV_REPLAY`, and a host-side memory serial test remains `HOST_TEST`.

## One-command software demo

```powershell
analog-validation demo `
  --output .\analog-validation-demo `
  --json
```

The demo runs a real reviewed product job with fixed software inputs and then
publishes deterministic JSON/CSV results, a self-contained report, SVG,
clean/fault replay examples, and SHA-256 manifests. It refuses to replace an
existing directory. Two tested normal and Unicode output directories produced
byte-identical artifacts.

The manifest explicitly records `SYNTHETIC`, output permission `DENIED`, zero
serial ports, zero application bytes, no network access, no absolute embedded
paths, and `NO_NEW_HARDWARE_VALIDATION`. See the
[software-demo guide](software-demo.md) before presenting its PASS result.

## CSV Replay example

```powershell
analog-validation replay read `
  --input .\test-data\golden\csv_replay_v1_valid.csv `
  --channel afe.ch0.input `
  --operation analog `
  --unit mV `
  --samples 2 `
  --json
```

The replay loader validates the versioned 13-column format before the adapter
publishes measurements. The current source becomes `CSV_REPLAY` even if a row
contains a historical source label; replaying a file cannot become a new bench
measurement.

## Result exports

DC, hysteresis, calibration, and frequency-response commands can write the
finalized core result bundle:

```powershell
analog-validation simulate dc `
  --points 12 `
  --output .\dc-result.json `
  --format json `
  --json
```

`--format csv` selects the versioned row-oriented export. The CLI uses the
existing atomic export writer and refuses an existing destination by default.
It reports the absolute artifact path, byte count, and SHA-256 after successful
publication. A failed or data-insufficient job cannot be hidden by an artifact
error; the original job state remains visible.

## Calibration coefficients

The calibration workflow produces two deliberately separate artifacts:

1. a `result-export.v1` bundle containing the finalized criteria, before/after
   errors, point dispositions, lineage, evidence source, and limitations; and
2. a `calibration-coefficients.v1` JSON file containing the mapping identity,
   version, scale, offset, unit, source labels, and all fit record IDs.

```powershell
analog-validation simulate calibration `
  --points 8 `
  --coefficient-id afe-linear-calibration `
  --coefficient-version 1 `
  --output .\calibration-result.json `
  --coefficients-output .\calibration-coefficients.json `
  --json

analog-validation coefficients inspect `
  --input .\calibration-coefficients.json `
  --json
```

Both destinations must be new files and must differ. Inspection validates the
strict bounded schema but reports `applied: false`; this increment does not
silently alter later observations or write coefficients into firmware. The
Dashboard exposes the same create-new save and load-for-inspection behavior.
For the v1 product workflow, observed and reference channels must come from the
same Simulator run or replay dataset because one `TestRun` has one evidence
source. The lower-level analysis API still supports separately sourced batches.

## Frequency response

The Simulator creates a bounded logarithmic frequency grid and deterministic
single-pole amplitudes. The model cutoff and reviewed target are separate:

```powershell
analog-validation simulate frequency `
  --points 21 `
  --frequency-minimum-hz 10 `
  --frequency-maximum-hz 100000 `
  --simulated-cutoff-hz 1000 `
  --target-cutoff-hz 1000 `
  --cutoff-relative-tolerance 0.15 `
  --output .\frequency-result.json `
  --json
```

The result contains the reference gain, target gain drop, estimated cutoff,
target cutoff and relative error, plus every frequency/input/output reference.
`replay frequency` consumes the same three-channel contract from one strict CSV
dataset. Both paths can produce PASS, FAIL, or INCOMPLETE without changing the
evidence class.

This is an amplitude-response workflow. It does not generate a sine wave,
sample raw waveforms, calculate phase, perform an FFT, control an instrument,
or authorize a serial output. A software PASS therefore validates only the
selected synthetic/replay dataset and criteria.

## Bounded live monitor

The live monitor is a finite observation workflow, not an analysis or an
unbounded logger. For example:

```powershell
analog-validation simulate monitor `
  --cycles 10 `
  --sample-interval 0.1 `
  --time-window 1 `
  --max-buffer-points 20 `
  --json
```

`--secondary` and `--state` include the default secondary analog and boolean
state channels; `--no-secondary` or `--no-state` removes them. The reviewed
configuration bounds the number of cycles, total measurements, requested
duration, interval, and retained points. The terminal result is `COMPLETED`
with engineering outcome `none`, because merely observing values is not a
PASS/FAIL criterion.

The CLI JSON includes a `live_monitor` snapshot with retained points and
acquired/evicted/quality counts. The human output summarizes those counts. It
does not create a `ResultExportBundle` or human report. The Dashboard adds the
interactive plot and cooperative Pause/Resume controls described in the
[live-monitoring guide](live-monitoring.md).

`SERIAL_READ_ONLY` deliberately does not advertise this job yet. Real-device
monitoring requires separate disconnect/reconnect, soak, data-rate, and
evidence review before it can be enabled.

## Human report example

After creating a DC, hysteresis, calibration, or frequency-response result
export, build a readable report:

```powershell
analog-validation report `
  --input .\dc-result.json `
  --output .\dc-report `
  --json
```

`--input-format auto` accepts only `.json` or `.csv`; an explicit `json` or
`csv` value can be used when a valid file has a different suffix. The output
must be a new directory and contains `report.txt`, `report.md`, `report.html`,
`chart.svg`, and `manifest.json`.

The report renderer only copies finalized values. It does not refit a DC line,
redetect a hysteresis transition, refit calibration coefficients, re-estimate a
frequency cutoff, evaluate criteria, or change evidence. The command returns
the finalized outcome's exit code, so a successfully written FAIL report still
exits `1`. See the [human-report guide](human-reports.md).

## Understanding the three result levels

The output intentionally separates three ideas:

| Field | Meaning | Example |
|---|---|---|
| worker state | Did orchestration and cleanup finish normally? | `SUCCEEDED`, `FAILED`, `CANCELLED` |
| product status | Did the requested product operation have enough supported data? | `COMPLETED`, `INCOMPLETE`, `UNSUPPORTED` |
| engineering outcome | Did finalized evidence meet the declared criteria? | `PASS`, `FAIL`, `INCOMPLETE` |

`worker=SUCCEEDED` does not automatically mean engineering `PASS`. For example,
a cleanly handled short replay can be `SUCCEEDED + INCOMPLETE`. Every workflow
also emits `hardware_claim=NO_PERFORMANCE_VALIDATION`.

## Stable exit codes

| Code | Meaning |
|---:|---|
| `0` | Operation completed and no engineering criterion failed |
| `1` | A complete engineering evaluation produced `FAIL` |
| `2` | Invalid command, option, or request |
| `3` | Valid operation, but evidence was incomplete |
| `4` | `UNSUPPORTED` capability or missing optional dependency |
| `5` | Expected operation/adapter/data failure |
| `70` | Unexpected internal software defect |
| `130` | User/interpreter interrupt produced cooperative cancellation |

Normal human results use stdout. User guidance and errors use stderr. `--json`
keeps the same distinction and emits one versioned JSON document. Expected
errors do not print a Python traceback; `--debug` is only for diagnosing an
unexpected software defect.

## Optional serial access

The base installation does not require pyserial. From the repository checkout:

```powershell
python -m pip install -e ".[serial]"
analog-validation ports
```

`ports` performs discovery only and closes the backend; it never opens a listed
port. `observe` is deliberately harder to invoke because it can touch a real
device:

```powershell
analog-validation observe `
  --port COM4 `
  --profile msp430-equipment-health `
  --profile-version 1 `
  --channel msp430.health.bus_voltage `
  --operation analog `
  --unit mV `
  --max-records 5 `
  --confirm-read-only `
  --json
```

Treat this only as a syntax example until the exact port, firmware/profile,
wiring, voltage domain, and ownership are confirmed. The product serial adapter
has no application write method, but an OS driver can still affect control lines
on open; that physical behavior requires its own device-specific review.

Step 3 CLI and Step 6 Dashboard serial integration tests used memory backends
with write traps. They proved both product paths made zero write calls, but they
did not open a real port. The MSP430 connected during Step 6 was deliberately
left untouched.

## Cancellation and current evidence limit

The worker checks a completion event at 50 ms intervals, requests cooperative
cancellation, waits for bounded cleanup, and maps `KeyboardInterrupt` to exit
code 130. A real subprocess test injects a main-thread interpreter interrupt and
verifies `CANCELLED`, cleanup, and no traceback. Windows console-process-group
signal delivery under the Codex/pytest host was not treated as a stable product
claim; a normal interactive-terminal smoke remains a later release check.

See the [product layer](product-layer.md),
[worker design](product-worker.md),
[Dashboard guide](dashboard.md), and
[Step 8 closure report](../reports/software-phase5-step8.md).
