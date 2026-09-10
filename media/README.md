# Media and Evidence Register

This directory keeps portfolio visuals and future physical evidence
classifiable by source. A screenshot of software output is not a photograph or
measurement of hardware.

## CSV import preview screenshots (2026-09-09)

| File | Theme | Source | What it shows |
|---|---|---|---|
| `dashboard-import-workbench-20260909.jpg` | Workbench | `CSV_REPLAY` from a `SYNTHETIC` fixture | Explicit column/unit mapping, checked V-to-mV values, and the publish/load controls |
| `dashboard-import-daylight-20260909.jpg` | Daylight | Same fixture and checked preview | The same import state with the light appearance setting |
| `dashboard-import-midnight-20260909.jpg` | Midnight | Same fixture and checked preview | The same import state with the dark appearance setting |

These are unedited 1922 x 1548 JPEG captures of the actual Windows Tk window,
rendered from the current local worktree on 2026-09-09. The native capture tool
returned JPEG bytes; no cropping, recoloring, compositing, or format conversion
was applied. The page is scrolled to its mapping and converted-value review.
The synthetic mapping name and `CSV_REPLAY` evidence label remain visible.

The six-row example uses input values 0.25, 0.5, 0.75, 1, 1.25, and 1.5 V,
with output values exactly twice the input. Its timestamps are deterministic
fixture values, not claimed acquisition times. The source was created under
the neutral `C:\AVS-Demo\import-media-20260909-211601` directory; no personal
Windows profile path appears in the screenshots. The source CSV SHA-256 is
`e0872ac1024af51e55f2a0fed6f4a64463fcc593ef6fc61ff4f5d8e91b177703`.

Screenshot SHA-256 identities:

- `dashboard-import-workbench-20260909.jpg`:
  `47201f8d2056b26f10d2ed1dcb4f0bd711541d87349a9e381bf9a1a184b834e4`
- `dashboard-import-daylight-20260909.jpg`:
  `fc49557829f30b2f5631b5442b3a69d409277e44112177915289219fd02019d2`
- `dashboard-import-midnight-20260909.jpg`:
  `9c0fcff04a527fa9ce7c1840450a42c3e059461906940e8733009369e8b4bc3d`

This capture session checked the import mapping but did not publish its package
or run an analysis. It did not enumerate, open, read, or write serial devices.
These images demonstrate software behavior and appearance, not device
compatibility, physical voltage accuracy, or new hardware validation.

## Historical software screenshots (2026-09-03)

| File | Captured | Source | What it shows | What it does not show |
|---|---|---|---|---|
| `dashboard-dc-result.png` | 2026-09-03 | `SYNTHETIC` Simulator | Dashboard as captured on this date, completed 24-point DC workflow, save-location control, reviewed source, and run status | A physical AFE, controller output, instrument reading, or electrical performance |
| `dashboard-dc-evidence.png` | 2026-09-03 | `SYNTHETIC` Simulator | Finalized point table, software PASS, evidence source, `NO_NEW_HARDWARE_VALIDATION`, and full not-verified block | Hardware validation, safety certification, calibration, or long-duration reliability |

Both PNGs are 1196×819 pixels. Their SHA-256 identities are:

- `dashboard-dc-result.png`:
  `0bc310ae673226a47c47a71eefdd8af50a3a0bf73a81c79e04af0c20b67a9c05`
- `dashboard-dc-evidence.png`:
  `b7413756950af4f865566680d8bf7026d97045940334c3b8310f6bbe6c80dd2b`

Both historical screenshots were captured from the then-current application in an
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
