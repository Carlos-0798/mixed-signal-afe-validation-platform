# Local Dashboard

**Implemented:** Software Phase 5 Steps 5–7, 2026-08-31<br>
**State schemas:** `dashboard-state.v1`, `dashboard-wizard.v1`, and `dashboard-session.v1`<br>
**Default source:** Simulator<br>
**Hardware claim:** `NO_NEW_HARDWARE_VALIDATION`

## What is available now

`analog-validation dashboard` launches a local Tkinter/ttk application with a
fixed six-step validation workflow:

1. **Source** — select Simulator, CSV Replay, or Serial (read-only).
2. **Test** — select bounded read, DC analysis, or hysteresis analysis.
3. **Configure** — enter channels, units, counts, limits, and source-specific
   settings.
4. **Review** — compile and validate the exact request before a worker starts.
5. **Run** — give the reviewed request to the existing single-owner worker and
   show bounded progress; Cancel uses cooperative cleanup.
6. **Result** — show outcome, evidence, limitations, points, and create-new
   JSON/CSV export when an analysis result exists.

The window separates the workflow into **Setup & run** and
**Results & evidence** tabs. Both pages have a visible vertical scrollbar and
support the Windows mouse wheel, so the run status, observation table,
limitations, and artifact information remain reachable on shorter displays.
Each new step returns its active page to the top instead of preserving a stale
scroll position from the previous step.

Every step displays three beginner prompts: what is happening, why it matters,
and what the user must confirm. Simulator is selected by default, so opening the
window does not enumerate a port, open hardware, read a file, create an output,
or start a network listener.

```powershell
analog-validation dashboard
```

## Why review happens before Run

The form is not an executable test by itself. `DashboardWizardDraft` first
converts user-entered strings into a bounded `ProductWorkflowConfiguration`.
The shared `prepare_product_job()` compiler then creates exactly one immutable
request, one reviewed service factory, and visible review lines. Only that exact
request can be handed to the worker.

```text
form draft
   -> strict typed conversion
   -> shared CLI/Dashboard workflow compiler
   -> reviewed request + visible safety/criteria summary
   -> single-owner worker
   -> existing core workflow / analysis / criteria / export
   -> finalized Dashboard result
```

This is the key engineering principle: the interface collects intent but does
not own CRC, profile parsing, line fitting, saturation exclusion, threshold
calculation, or PASS/FAIL. Those decisions remain in the tested core, so CLI and
Dashboard cannot silently calculate different answers.

## Source-specific safety behavior

### Simulator

- selected by default;
- deterministic and software-only;
- produces `SYNTHETIC` evidence;
- a PASS verifies the modeled software path, not a physical AFE.

### CSV Replay

- requires an explicit path and channel mapping;
- loads and validates the complete `csv-replay.v1` dataset during Review;
- keeps the immutable validated dataset closed and in memory until Run;
- reports `CSV_REPLAY`, even if historical rows name a bench source;
- never contacts hardware.

### Serial (read-only)

- requires an exact profile, logical port, read timeout, poll limit, sample
  bound, and explicit receive-only confirmation;
- Discover performs enumeration only, closes the backend, and does not open a
  listed port;
- Review does not open the selected port;
- Run defers construction/opening to the owning worker and closes it during
  cleanup;
- there is no command console, transmit field, write button, device command, or
  application-level backend `write()` surface.

Opening an OS serial port may still change driver control lines. Therefore a
real controller run remains a separately reviewed physical action even though
the application path is receive-only.

## Thread, cancellation, and navigation safety

- Tk widgets run only on the owner thread.
- The worker owns its service and adapter; widgets never call them directly.
- The owner thread polls immutable bounded events and renders copies.
- Cancel requests cooperative cancellation and preserves `CANCELLED`; it cannot
  create a PASS or export.
- Closing the window requests cancellation and performs a bounded join before
  returning a safe session result.
- Returning from Review invalidates the prepared request and clears its review
  authorization. **Modify setup** from Result also invalidates the prepared
  request but retains copied result evidence as a reference; Run remains
  disabled until the edited setup is validated again. **Start new test** clears
  the prior result and resets the form.
- Export uses create-new semantics and refuses to replace an existing file.
- The window is composed while hidden, finishes its first layout pass, and is
  then shown. Subsequent 50 ms worker polls redraw widgets only when an immutable
  Dashboard or wizard revision changes; unchanged polls do not clear and rebuild
  the observation table.

## Result and evidence display

The original six result regions remain available on the results tab:
source/profile,
configuration/safe review, progress, finalized point table, result/evidence,
and artifacts. Result actions make the end of a run explicit: **Modify setup**,
**Review same setup**, **Start new test**, or **Finish & close**. The Step 6
wizard exposes the acceptance criteria used for DC or hysteresis evaluation.
Evidence source, worker state, engineering outcome, limitations, exclusions,
and issues are written as text; meaning is not conveyed by color alone.

A bounded read can finish successfully without an analysis export. DC and
hysteresis results can expose the existing finalized `ResultExportBundle` and
write JSON or CSV. The Dashboard does not recompute that bundle.

## Verified software behavior

- CLI and Dashboard produced equivalent finalized results for the same 24-point
  Simulator DC configuration.
- Missing/invalid Replay input failed during Review, before worker start.
- A memory-backed MSP430 receive-only chain opened once during Run, closed once,
  and made zero write calls; no physical port was involved.
- A cooperative blocking service reached `CANCELLED`, ran cleanup, and exposed
  no export.
- Fake-toolkit tests exercised every Step 6 callback; a separate real Windows Tk
  smoke verified installed-package startup and safe auto-close.
- Step 7 made actionable controls explicit keyboard-focus targets. Real Windows
  Tk smoke at scaling 1.0, 1.5, and 2.0 verified focus traversal and successful
  layout creation.
- A real Windows interactive check covered Simulator READ, 12-point DC, and
  12-rising/22-falling hysteresis; valid and malformed CSV Replay; safe
  no-overwrite export; immediate rerun; result actions; scrolling; and clean
  window close. The executed observations remain `SYNTHETIC` or `CSV_REPLAY`
  software evidence only.
- The current follow-up gate passed 2,263 tests and covered 11,820/11,820
  executable package statements. Two isolated builds were byte-identical, and
  fresh base and `[serial]` installations passed using only an injected serial
  substitute.

## Current limitations

- Keyboard focus and common Tk scaling have automated baseline coverage; full
  screen-reader certification and long interactive sessions remain unverified.
- The hidden-first-paint and revision-gated redraw changes removed the observed
  incomplete first frame during the documented Windows check; behavior across
  every graphics driver, remote desktop mode, and display configuration remains
  unverified.
- The one-command demo is implemented, but it remains a deterministic software
  demonstration and does not validate physical hardware.
- Real COM worker lifecycle, disconnect/reconnect, and long-duration timing have
  not been tested in Step 6.
- The connected MSP430 was not enumerated, opened, read, reset, flashed, or
  written during this checkpoint.
- No physical AFE, ADC/DAC accuracy, threshold, gain, bandwidth, wiring, or
  instrument behavior was validated.

See the [CLI guide](product-cli.md), [human-report guide](human-reports.md),
[product-quality acceptance](product-quality-acceptance.md),
[Phase 5 plan](SOFTWARE_PHASE_5_PLAN.md), and
[Step 8 closure report](../reports/software-phase5-step8.md).
