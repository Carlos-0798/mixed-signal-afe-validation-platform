# Reproducible software demo

## Purpose

The portfolio demo answers a simple product question: can a new user install the
base package, run one command, and receive a complete, inspectable validation
package without owning hardware?

It deliberately uses deterministic `SYNTHETIC` observations. The software runs
the same reviewed product configuration, single-owner worker, read workflow,
formal DC analysis, acceptance criteria, result export, and presentation-only
reporting used by the CLI and Dashboard. The demo is therefore an end-to-end
software acceptance path, not a prewritten screenshot or copied result.

## Run it

```powershell
analog-validation demo --output .\analog-validation-demo
```

The destination must be a new directory inside an existing writable parent.
The command never overwrites a prior demo. Add `--json` for the versioned CLI
machine response.

## Generated package

```text
analog-validation-demo/
├── README.md
├── demo-config.json
├── result.json
├── result.csv
├── manifest.json
├── examples/
│   ├── replay-dc.csv
│   └── replay-faults.csv
└── report/
    ├── report.txt
    ├── report.md
    ├── report.html
    ├── chart.svg
    └── manifest.json
```

- `result.json` and `result.csv` represent the same finalized result.
- `report.html` is self-contained and loads no script, font, image, or style
  resource from the network.
- `chart.svg` copies finalized report values; it does not refit the data.
- the top-level manifest records every other artifact's relative path, media
  type, byte count, and SHA-256 hash;
- the clean replay example can be passed back through the public Replay CLI;
- the fault example intentionally contains saturated, missing,
  communication-error, and non-finite synthetic records.

## Why it is reproducible

The demo freezes its job identity, run timestamps, simulator behavior,
configuration, point count, serialization, filenames, and manifest ordering.
The output directory is not embedded in any artifact. Two runs in different,
including Unicode, directories therefore produce byte-identical files.

The exact `portfolio-demo.v1` artifact hashes are frozen in
[`phase5_demo_v1.json`](../test-data/golden/phase5_demo_v1.json). A change is a
reviewed compatibility change rather than an unnoticed presentation drift.

## Safety, privacy, and evidence boundary

During this demo:

- output permission is `DENIED`;
- serial ports opened is `0`;
- application bytes written is `0`;
- network access is `NONE`;
- absolute local paths and raw serial bytes are excluded from artifacts;
- evidence remains `SYNTHETIC`;
- the hardware claim remains `NO_NEW_HARDWARE_VALIDATION`.

A `PASS` proves that the fixed software model satisfied the declared software
criteria. It does not prove physical gain, offset, saturation, threshold,
bandwidth, protection, wiring, calibration, or long-duration reliability.

## Replay the examples

Run from inside the generated directory:

```powershell
analog-validation replay dc --input examples\replay-dc.csv --points 24 --json
analog-validation replay read --input examples\replay-faults.csv --channel afe.ch0.input --samples 2 --json
```

Replay evidence is labeled `CSV_REPLAY`; the source declared inside the example
remains auditable but is not authenticated as physical evidence.

## Common failures

- `OUTPUT_EXISTS`: choose a new directory name; deleting evidence is not an
  automatic recovery action.
- `OUTPUT_PATH`: create or select an existing writable parent directory.
- `INPUT_DATA`: retain the generated files and compare their hashes with the
  frozen manifest before rerunning.
