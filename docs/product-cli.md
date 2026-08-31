# Analog Validation Studio CLI

**Implemented:** Software Phase 5 Steps 3–4, 2026-08-31<br>
**Schema:** `product-cli-output.v1`<br>
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
CLI request
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
```

These Simulator commands are the safest beginner starting point. They use
deterministic synthetic observations, open no COM port, and send no bytes. A
Simulator PASS proves that the software pipeline produced the expected answer
for its model; it does not prove that a physical circuit has that gain,
saturation level, or threshold.

## Command map

| Command | Current behavior | Resource boundary |
|---|---|---|
| `version` | Show installed software identity | No adapter or optional dependency |
| `profiles` | List exact reviewed profile identities | Software support only; no device detection |
| `ports` | Discover minimal logical serial-port descriptions | Does not open a port; needs the optional `serial` extra |
| `simulate read` | Run a bounded deterministic read workflow | Synthetic software only |
| `simulate dc` | Read synthetic input/output observations, run formal DC analysis and criteria | No physical stimulus; no output runner |
| `simulate hysteresis` | Read a synthetic rising/falling cycle, run formal threshold analysis and criteria | No physical stimulus; no output runner |
| `replay read` | Read an explicit local `csv-replay.v1` file | Preserves replay lineage; does not contact hardware |
| `replay dc` | Project two explicit analog channels and run formal DC analysis | File evidence only |
| `replay hysteresis` | Project explicit analog/state channels and direction counts | File evidence only |
| `observe` | Run one bounded receive-only serial read | Exact port/profile/channel plus `--confirm-read-only`; no write API |
| `report` | Turn one finalized JSON/CSV result export into five deterministic human-report files | No adapter, serial port, analysis, or hardware operation |
| `dashboard` | Reserved for Step 5 | Returns exit code 4 without creating a window |
| `demo` | Reserved for Step 7 | Returns exit code 4 without fabricating demo artifacts |

Run any command with `--help` to see its exact options. Sample and record counts
are bounded at the parser boundary, numeric values must be finite, and profile
identity is exact rather than guessed from a filename or USB description.

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

DC and hysteresis commands can write the finalized core result bundle:

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

## Human report example

After creating a DC or hysteresis result export, build a readable report:

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
redetect a hysteresis transition, evaluate criteria, or change evidence. The
command returns the finalized outcome's exit code, so a successfully written
FAIL report still exits `1`. See the [human-report guide](human-reports.md).

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
| `4` | `UNSUPPORTED`, a still-reserved feature, or missing optional dependency |
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

Step 3 serial integration tests used a memory backend with a write trap. They
proved the product path made zero write calls, but they did not open a real port.
The MSP430 connected during development was deliberately left untouched in
Steps 3–4.

## Cancellation and current evidence limit

The worker checks a completion event at 50 ms intervals, requests cooperative
cancellation, waits for bounded cleanup, and maps `KeyboardInterrupt` to exit
code 130. A real subprocess test injects a main-thread interpreter interrupt and
verifies `CANCELLED`, cleanup, and no traceback. Windows console-process-group
signal delivery under the Codex/pytest host was not treated as a stable product
claim; a normal interactive-terminal smoke remains a later release check.

See the [product layer](product-layer.md),
[worker design](product-worker.md), and
[Step 4 evidence report](../reports/software-phase5-step4.md).
