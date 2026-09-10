# Private beta testing guide

## Goal

This 20–30 minute session checks whether a new user can install and understand
Analog Validation Studio without repository knowledge or hardware. It tests the
delivered software experience, not analog performance.

This installation/demo session does not measure time saved over manual work.
The next engineering-value evaluation uses the separate
[task-value protocol](TASK_VALUE_VALIDATION_PLAN.md): the same DC task, inputs,
criteria and deliverables for a manual/template baseline and AVS. Record setup,
data conversion, report preparation and actual operator time independently;
human measurements remain NOT_RUN until a person performs the task.

Use the matching [installation guide](INSTALLATION.md),
[checklist](BETA_TEST_CHECKLIST.md), [known limitations](KNOWN_LIMITATIONS.md),
and [troubleshooting guide](TROUBLESHOOTING.md).

## Before starting

Record only these non-sensitive facts:

- operating-system family/version;
- Python version and architecture;
- `analog-validation version --json` output;
- wheel filename and SHA-256;
- whether the required CLI path and optional Dashboard path were attempted.

Do not include a username, home directory, full local path, email address,
token, private repository URL, USB identifier, physical port name, or raw
serial frame in feedback. Replace local paths with placeholders such as
`<beta-root>`.

## Required base test

### 1. Candidate integrity

- The directory has one wheel, one sdist, and `release-manifest.json`.
- The manifest says `candidate_status: PASS`.
- Both artifact size/SHA-256 values match the local files.
- The manifest says `NO_NEW_HARDWARE_VALIDATION` and zero physical-port
  operations.

Stop if any identity differs. Do not try to repair or rename the package.

### 2. Clean installation

- Create a new short-path virtual environment.
- Install the wheel with `--no-deps`.
- Confirm `pip check` reports no broken requirements.
- Confirm version JSON reports `0.1.0b1` without a traceback.

This proves the base product has no required third-party runtime package. It
does not prove optional serial or GUI behavior.

### 3. Deterministic demo

Run one create-new demo directory. Expected results:

| Observation | Expected value |
|---|---|
| CLI exit | `0` |
| outcome | `PASS` |
| evidence source | `SYNTHETIC` |
| hardware claim | `NO_NEW_HARDWARE_VALIDATION` |
| top-level artifacts | 12 |
| serial ports opened | 0 |
| application bytes written | 0 |
| network access declared by demo | `NONE` |

Verify that the result contains JSON/CSV, a text/Markdown/HTML report, SVG,
two replay examples, and manifests. Open the local HTML report and answer:

1. Can you find the engineering outcome?
2. Can you identify that the source is synthetic?
3. Can you find what has not been physically verified?
4. Can you find the gain/offset/fit criteria without reading source code?

If the software says PASS but the evidence limitation is hard to find, submit
usability feedback even though the command technically succeeded.

### 4. Create-new safety

Run the same demo command against the already existing demo directory. Expected:

- the command refuses to overwrite it;
- the original files remain available;
- the error explains that a new path is required;
- no Python traceback appears in normal mode.

This is an intentional evidence-preservation feature, not a defect.

### 5. Optional desktop check

If a graphical Windows desktop and Tk are available, launch the Dashboard with
the default Simulator. Review the six steps, criteria, Run/Cancel controls,
result/evidence panel, and close behavior. Confirm that a short page stays at
the top without wheel movement, while a page taller than the window exposes a
working vertical scrollbar. For a finalized DC or hysteresis analysis, use
**Choose save location...**, cancel once to confirm the existing field is
unchanged, then choose a new JSON or CSV filename and save it. Confirm that the
picker suggests a matching filename and offers only the selected format. Before
saving, try **Finish & close** and **Start new test**: each must warn that the
only finalized copy is unsaved, and choosing No must preserve the Result page.
After saving, repeat one analysis and confirm that its destination starts empty.
Finally, select JSON but manually enter a `.csv` path; the app must explain the
suffix mismatch and create no file. Do not select Serial.
Record `NOT_RUN` when no suitable display exists; never convert a skipped GUI
test into PASS.

### 6. Calibration product check

Use Simulator, choose **Calibration analysis**, keep the default observed and
reference channels, set 8 points, review, and run. Expected:

- worker state is `SUCCEEDED` and engineering outcome is `PASS`;
- evidence remains `SYNTHETIC`; the Dashboard/report says
  `NO_NEW_HARDWARE_VALIDATION`, while the execution CLI JSON retains its frozen
  `NO_PERFORMANCE_VALIDATION` wording. Both explicitly deny physical proof;
- the finalized metrics show `scale = 2`, `offset = 12 mV`, and zero
  after-calibration error for the deterministic default model;
- the result table preserves both observed/reference lineage and shows copied
  before/after signed errors;
- **Choose new coefficient file...** and **Save coefficients** create one new
  `.json` file, while selecting the same existing file again is rejected;
- **Choose existing coefficient file...** and **Load & validate** identify the
  coefficient ID/version and explicitly say the file was not applied or rerun;
- saving the analysis result remains a separate action and neither output is
  silently overwritten.

The same host-only check can be run from PowerShell:

```powershell
& $Cli simulate calibration `
  --points 8 `
  --output (Join-Path $TestRoot "calibration-result.json") `
  --coefficients-output (Join-Path $TestRoot "calibration-coefficients.json") `
  --json

& $Cli coefficients inspect `
  --input (Join-Path $TestRoot "calibration-coefficients.json") `
  --json
```

Do not describe this deterministic mapping as DMM/ADC calibration evidence.

### 7. Frequency-response product check

Use Simulator, choose **Frequency response analysis**, keep the default
frequency/input/output-amplitude channels, set 21 points, review, and run.
Expected:

- worker state is `SUCCEEDED` and engineering outcome is `PASS`;
- evidence remains `SYNTHETIC`; the Dashboard/report says
  `NO_NEW_HARDWARE_VALIDATION`, while the execution CLI JSON retains its frozen
  `NO_PERFORMANCE_VALIDATION` wording. Both explicitly deny physical proof;
- the deterministic default model and independent acceptance target are both
  1000 Hz, so the estimated cutoff is 1000 Hz;
- each finalized point preserves frequency, input-amplitude, and
  output-amplitude lineage;
- the result report shows magnitude in dB on a logarithmic frequency axis and
  marks the copied target drop and estimated cutoff;
- saving JSON/CSV or a report still uses create-new behavior and never opens a
  serial port or controls a waveform source.

The same host-only check can be run from PowerShell:

```powershell
& $Cli simulate frequency `
  --points 21 `
  --simulated-cutoff-hz 1000 `
  --target-cutoff-hz 1000 `
  --output (Join-Path $TestRoot "frequency-result.json") `
  --json

& $Cli report `
  --input (Join-Path $TestRoot "frequency-result.json") `
  --output (Join-Path $TestRoot "frequency-report") `
  --json
```

As an optional negative acceptance check, use a 2000 Hz simulated model but
keep the target at 1000 Hz with 5% tolerance:

```powershell
& $Cli simulate frequency `
  --points 21 `
  --simulated-cutoff-hz 2000 `
  --target-cutoff-hz 1000 `
  --cutoff-relative-tolerance 0.05 `
  --json
```

Expected exit code is `1` with engineering `FAIL`, not an application error or
traceback. The current deterministic estimate is about 1948.015 Hz because it
is interpolated from the bounded log-frequency sample grid. Neither the PASS
nor deliberate FAIL is a measured Bode sweep, phase response, physical
bandwidth, signal-generator result, or oscilloscope result.

## Optional Replay check

The generated clean replay file can be consumed without hardware:

```powershell
& $Cli replay dc `
  --input (Join-Path $Demo "examples\replay-dc.csv") `
  --points 24 `
  --json
```

Expected evidence is `CSV_REPLAY`, not `SYNTHETIC` or `BENCH_*`. Replaying a
file creates a new software observation context; it cannot authenticate a past
physical measurement.

## Stop conditions

Stop the test and submit a sanitized bug report when:

- a candidate hash or version does not match;
- installation modifies an unrelated Python environment;
- the base install unexpectedly requires pyserial;
- a normal Simulator/demo command attempts port access;
- an existing artifact is overwritten;
- an expected error exposes a traceback without `--debug`;
- outcome/evidence/hardware-claim fields contradict each other;
- a process does not terminate after normal close/cancel.

Do not investigate by connecting hardware, changing execution policy, running
as administrator, disabling security software, or deleting existing evidence.

## Feedback outcome

Choose one overall result:

- `PASS`: every required base item matched and no blocking issue occurred;
- `PARTIAL`: the CLI path passed but an optional path was unavailable or a
  non-blocking usability issue was found;
- `BLOCKED`: integrity, install, required command, evidence, privacy, or cleanup
  did not meet the checklist.

Use the repository's **Private beta test feedback** issue form. Use **Bug
report** for one reproducible defect. Attach no candidate package, raw capture,
or private diagnostic archive to an issue.
