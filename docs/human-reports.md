# Human reports and deterministic charts

**Implemented:** Software Phase 5 Step 4, 2026-08-31
**Schemas:** `human-report.v1`, `human-report-manifest.v1`
**Evidence:** HOST_TEST rendering from finalized `result-export.v1` inputs
**New hardware validation:** none

## What this feature does

The `report` workflow turns one already-finalized machine result into files that
a person can read and review. It does not collect measurements, control a board,
fit data, evaluate criteria, or change PASS/FAIL.

For a beginner, the separation is important:

1. the engineering core creates `result-export.v1` and owns the conclusion;
2. `presentation.py` copies that frozen content into an immutable display model;
3. `reporting.py` renders the copied values as text, Markdown, HTML, and SVG;
4. the publisher writes all files into one new directory and records hashes.

This is similar to printing a lab result that has already been signed: changing
the layout must not change the signed result.

## Run it

Create a result with the software-only Simulator, then create a report:

```powershell
.\.venv\Scripts\analog-validation.exe simulate dc --points 6 --output work\dc-result.json --json
.\.venv\Scripts\analog-validation.exe report --input work\dc-result.json --output work\dc-report --json
```

The input may be the strict JSON or CSV form of `result-export.v1`. With
`--input-format auto`, only `.json` and `.csv` suffixes are accepted. The output
must be a new directory; existing files or directories are never overwritten.

The report command deliberately preserves the finalized engineering outcome in
its exit code:

| Outcome | Exit code |
|---|---:|
| `PASS` | 0 |
| `FAIL` | 1 |
| CLI usage error | 2 |
| `INCOMPLETE` | 3 |
| `UNSUPPORTED` | 4 |
| `ERROR` or report operation error | 5 |
| `ABORTED` | 130 |

## Output directory

Every successful publication contains exactly five UTF-8 artifacts:

| File | Purpose |
|---|---|
| `report.txt` | Terminal- and plain-text-friendly complete summary |
| `report.md` | Reviewable Markdown with identity, metrics, criteria, limits, and point lineage |
| `report.html` | Self-contained local report with inline CSS and the exact embedded SVG |
| `chart.svg` | Deterministic, scalable chart with text labels and legends |
| `manifest.json` | Schema, outcome, evidence, canonical input hash, and hashes/sizes of the four rendered files |

The CLI also reports the hash of `manifest.json`. The manifest does not hash
itself, avoiding an impossible circular self-reference.

The files show the source run's start/end UTC times. They deliberately omit the
current wall-clock report-generation time so the same finalized input produces
the same bytes; generator version, canonical input hash, and artifact hashes
identify the publication reproducibly.

## What the charts mean

### DC sweep

The chart shows included, excluded, and invalid points with different shapes and
text legends. The fitted line is made only from each point's already-exported
`predicted_output`. Changing the displayed gain metric cannot refit or move that
line.

### Hysteresis

The chart separates rising and falling observations, marks adjacent exported
state-transition brackets, and copies the finalized mean high and low threshold
metrics. It does not search for new transitions or recalculate a threshold.

### Calibration

The calibration chart plots the signed error before and after correction for
each finalized point. Both series are copied from the result bundle, so report
generation cannot refit the line, change coefficients, or recalculate
PASS/FAIL. The report also lists coefficient identity/version, scale, offset,
before/after error metrics, criteria, provenance, and point lineage. A
`SYNTHETIC` or `CSV_REPLAY` calibration report is not a traceable instrument
calibration certificate.

### Frequency response

The frequency-response chart copies each finalized frequency and gain value and
plots gain in dB against a logarithmic frequency axis. It marks the copied
target gain drop and estimated cutoff frequency. It does not re-interpolate the
crossing, recalculate PASS/FAIL, or infer phase. The report preserves the three
record references behind every point and explicitly identifies Simulator or
Replay evidence.

The chart is an amplitude-response view only. It is not an oscilloscope trace,
FFT result, phase plot, or proof of physical filter bandwidth.

If a result has no supported specialized analysis schema, the report remains
readable and explicitly says that no supported chart is available.

## Safety, privacy, and determinism

- Input parsing reuses the strict, bounded `result-export.v1` loaders.
- A report is limited to 10,000 points.
- Text is normalized and escaped before Markdown, HTML, or SVG rendering.
- HTML contains no script, remote CSS, remote font, upload, listener, or network
  dependency.
- A caller cannot substitute arbitrary SVG into the HTML renderer.
- Default reports contain record identities and hashes, not raw serial bytes,
  usernames, USB identities, or an absolute output path.
- Files are rendered in memory, written to a staging directory, flushed, and
  renamed as one create-new directory. A concurrent existing destination fails
  rather than being replaced.
- Every view and manifest states `NO_NEW_HARDWARE_VALIDATION` and includes a
  visible “Not verified” section.

An input labelled `SYNTHETIC` remains synthetic. A future bench-labelled input
may be displayed as declared, but generating the report does not repeat that
bench test or promote controller telemetry to analog-front-end performance.

## Verification and current limits

The Phase 5 golden fixture freezes the exact sizes and SHA-256 values of ten
artifacts generated from the standard synthetic DC and hysteresis results. Unit
tests cover escaping, missing data, invalid/non-finite display values, plot
semantics, atomic publication, path races, write failures, strict SVG embedding,
CLI format detection, and outcome-preserving exit codes.

Specialized charts currently cover DC sweep, hysteresis, calibration, and
frequency-response result bundles. PDF generation remains later work.
Dashboard display, the beginner wizard, and the one-command portfolio demo now
reuse this presentation-only report boundary; none of them promotes synthetic
or replay evidence into a hardware claim.

See the [result export contract](result-exports.md),
[product CLI](product-cli.md), and
[Step 4 evidence report](../reports/software-phase5-step4.md).
