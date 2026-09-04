# Media and Evidence Register

This directory keeps portfolio visuals and future physical evidence
classifiable by source. A screenshot of software output is not a photograph or
measurement of hardware.

## Current software screenshots

| File | Captured | Source | What it shows | What it does not show |
|---|---|---|---|---|
| `dashboard-dc-result.png` | 2026-09-03 | `SYNTHETIC` Simulator | Current Windows Dashboard, completed 24-point DC workflow, save-location control, reviewed source, and run status | A physical AFE, controller output, instrument reading, or electrical performance |
| `dashboard-dc-evidence.png` | 2026-09-03 | `SYNTHETIC` Simulator | Finalized point table, software PASS, evidence source, `NO_NEW_HARDWARE_VALIDATION`, and full not-verified block | Hardware validation, safety certification, calibration, or long-duration reliability |

Both PNGs are 1196×819 pixels. Their SHA-256 identities are:

- `dashboard-dc-result.png`:
  `0bc310ae673226a47c47a71eefdd8af50a3a0bf73a81c79e04af0c20b67a9c05`
- `dashboard-dc-evidence.png`:
  `b7413756950af4f865566680d8bf7026d97045940334c3b8310f6bbe6c80dd2b`

Both screenshots were captured from the current local application in an
isolated Simulator-only session. The session did not enumerate, open, read, or
write a serial port and did not access the connected MSP430.

These images may be used in the repository README because their evidence class
and limitations are visible. They must not be relabeled as bench results or
used to imply that a physical front end exists.

## Future physical media

When hardware work begins, keep it under a separately documented bench-evidence
path and record:

- date, operator, device/profile identity, firmware identity, and test plan;
- schematic revision, power limits, wiring diagram, and clear setup photos;
- instrument models, settings, calibration status, and raw exported data;
- exact `BENCH_*` evidence class, acceptance criteria, result, exclusions, and
  limitations;
- hashes or immutable references linking media to the corresponding report.

No configurable AFE hardware photograph, oscilloscope capture, DMM dataset, or
physical AFE plot is present today.
