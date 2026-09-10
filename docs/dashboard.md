# Local Dashboard

**Implemented:** Software Phase 5 Steps 5–7, 2026-08-31<br>
**State schemas:** `dashboard-state.v1`, `dashboard-wizard.v1`, and `dashboard-session.v1`<br>
**Default source:** Simulator<br>
**Hardware claim:** `NO_NEW_HARDWARE_VALIDATION`

## What is available now

`analog-validation dashboard` launches a local Tkinter/ttk application with a
fixed six-step validation workflow:

1. **Source** — select Simulator, CSV Replay, or Serial (read-only).
2. **Test** — select bounded read, bounded live monitoring, DC analysis,
   hysteresis analysis, linear calibration, or frequency-response analysis.
3. **Configure** — enter channels, units, counts, limits, and source-specific
   settings. Frequency response has a dedicated panel that keeps the Simulator
   model cutoff separate from the reviewed target cutoff. Live monitoring has
   explicit finite cycles, interval, time window, retained-point bound, and
   channel-selection controls.
4. **Review** — compile and validate the exact request before a worker starts.
5. **Run** — give the reviewed request to the existing single-owner worker and
   show bounded progress; Cancel uses cooperative cleanup.
6. **Result** — show outcome, evidence, limitations, points, create-new
   JSON/CSV export, and separate calibration-coefficient save/inspection when
   applicable.

During a reviewed live-monitor run, the Results tab adds a bounded chart,
acquired/retained/visible/evicted and quality counts, cooperative Pause/Resume,
and a presentation-only trailing-window selector. The job always terminates at
its reviewed cycle bound and has no engineering PASS/FAIL outcome.

The window separates the workflow into **Setup & run** and
**Results & evidence** tabs, plus **Projects & history** for reusable presets,
reviewed batches, and comparison. A vertical scrollbar appears only when the
active page is taller than the available viewport. Short pages stay pinned to
the top and ignore the Windows mouse wheel instead of moving into empty space;
long pages remain scrollable so run status, observations, limitations, and
artifact information are reachable. Each new step returns its active page to
the top instead of preserving a stale scroll position from the previous step.

**Import data** provides a separate entry for ordinary voltage CSV/TSV files.
Choose a file, explicitly map time/input/optional output and units, check the
mapping, and publish a new package. **Load imported setup** then opens the
existing Setup workflow with CSV Replay and requires a fresh Review. It never
starts a run. Mapping changes invalidate the checked preview; close warns about
a reviewed but unpublished import. Saving a mapping alone does not save its data.
The source snapshot, mapping, converted replay, project, and hashes are preserved
together. See [Voltage data import](voltage-data-import.md) for examples, limits,
and the distinction between a reusable mapping and analysis acceptance criteria.

Projects & history starts with a state-derived next action. It previews the
current Setup source and test before preset capture, states that capture stores
configuration without running, and preserves the exact `SYNTHETIC` or
`CSV_REPLAY` boundary. A Serial Setup says it cannot be stored and confirms that
the project page does not discover or open a port. Zero, one, and multiple-run
history states give different instructions instead of showing an empty table
with an impossible comparison request.

Selecting one history row now opens a read-only Replay input table beneath the
run list. For manifest v3 it shows every executed Replay preset, its run-relative
archived path, byte count, and full SHA-256. The guide distinguishes per-preset
references from physical files when one source was reused. Simulator-only and
not-started Replay cases explain why the table is empty; v1/v2 history explains
that it predates retained inputs. Selecting two rows keeps the existing
comparison workflow and clears the single-run input detail.

After **Review selected batch**, a structured frozen-review section shows the
exact project ID, run ID, create-new destination, and each selected preset in
execution order. Every row uses readable Source/Test names while preserving its
exact `SYNTHETIC` or `CSV_REPLAY` evidence label. Run consumes and clears this
review; the live progress and terminal history then become the authoritative
status. The preview does not read a Replay file or contact hardware.

## Reuse a setup and save a complete report

Select exactly one project preset and choose **Load selected into Setup**. The
Dashboard copies it into Configure, including all six supported test types and
the resolved Replay path. Loading does not read the CSV, start a job or modify
the saved preset. Existing setup edits and unsaved results are protected by a
confirmation. Run requires a fresh Review. To retain a variation, use the
existing **Add current Setup as preset** action with a new preset ID, then save
the project as a new file.

After a finalized DC, hysteresis, calibration or frequency-response analysis,
**Save report package…** creates a new folder containing HTML, SVG, Markdown,
text, the complete `result.json`, and a hash manifest. **Open saved report**
opens the local HTML in the user's browser after checking its publication hash.
Publishing an existing folder is refused without changing the result. The
report package saves the machine result too; calibration coefficients still
have their own separate save action. READ/LIVE observations do not claim to have
an analysis report or a persistent raw-data archive.

## Visual and interaction system

The **Appearance (this window)** selector in the header provides three palettes:

| Choice | Appearance | Intended use |
| --- | --- | --- |
| Workbench (default) | Neutral slate surfaces, soft blue accents | General laboratory and engineering work |
| Daylight | White cards, light gray background, dark blue text and actions | Bright rooms and users who prefer dark text |
| Midnight | Charcoal surfaces, subdued accents, readable pale text | Dim rooms and users who prefer lower background brightness |

The choice applies immediately to Setup, Results, Projects, tables, input fields,
dropdown lists, scroll backgrounds, and live-chart labels/traces. It lasts for the
current window; a new window starts with Workbench. Theme selection does not write
preferences into project files or manifests, change reviewed requests, discard
unsaved fields, clear results, change the selected tab, or restart acquisition.

All three themes share the same presentation rules:

- neutral surfaces separate the application background, cards and editable fields;
- a restrained blue accent identifies the current step, primary action, focus,
  and real progress;
- green identifies declared evidence or a safe boundary, amber marks warning
  information, and muted red identifies cancellation or failure actions;
- header labels state `LOCAL / OFFLINE`, `READ-ONLY DEFAULT`, and
  `EVIDENCE LABELED` in text, so meaning never depends on color alone;
- tables use a taller 30-pixel row, stronger headings, and a visible selected
  row; text entry and read-only selection controls share the same field surface;
- primary, secondary, disabled, and dangerous buttons have distinct native ttk
  active/pressed/focus states. All controls remain real widgets with their
  existing commands and keyboard focus behavior.

Body, supporting text and table text use at least 10-point Segoe UI. Palette
regression tests enforce a 4.5:1 contrast floor for their text/surface pairs,
including disabled text, selected rows, action states and chart legends. This
checks declared colors, not full accessibility certification or readability on
every display. Disabled states take priority over hover and readonly states.

The supported minimum window is 1040×760. Dense configuration groups reflow to
three columns and use vertical scrolling, while result tables and save controls
stay within the same horizontal viewport. This avoids hiding a required field
or action behind an undiscoverable horizontal scroll area. Real Windows Tk
checks cover Setup, Results, and Projects at scaling 1.0, 1.25, 1.5, 1.75, and
2.0.

At startup, the Dashboard reads the Windows high-contrast flag without changing
the operating-system setting. An enabled flag switches ttk surfaces, text,
focus, selection, disabled states, error borders, scroll canvases, and live
charts to Windows system colors. Text labels continue to carry source, state,
error, and evidence meaning. The appearance selector displays **System contrast**
and is disabled while this mode is active. If the user changes the Windows contrast theme
while the Dashboard is already open, the application must be restarted to
reload it.

The interface does not invent preview measurements, animate idle values, or
simulate progress. It renders only current application state. Continuous
background animation was intentionally omitted because it would compete with
live traces and warnings in a validation tool. The styling remains native ttk,
so it adds no browser runtime, network resource, image asset, or UI-thread timer.

Every step displays three beginner prompts: what is happening, why it matters,
and what the user must confirm. A separate action hint beside the navigation
buttons names the next usable action and explains why Run remains unavailable
before a valid compiled review exists. On Configure, a plain-language field
guide explains the selected source boundary and the meaning of the active test:
finite observations for Read, input/output fit for DC, rising/falling threshold
separation for Hysteresis, reference/observed values for Calibration,
amplitude-only triples for Frequency Response, and the bounded display buffer
for Live Monitor. Simulator guidance stays visible even though the
Replay/Serial connection panel is hidden. These texts are derived from the
existing draft and permission state and do not grant permission or recompute an
analysis.

Source and Test selectors use readable names such as **Simulator — synthetic
data**, **CSV Replay — local file**, **Read samples**, and **Frequency
response**. These are display aliases only: the application, saved projects,
CLI, and artifacts continue to use the stable `SIMULATOR`, `CSV_REPLAY`,
`READ`, and `FREQUENCY_RESPONSE_ANALYSIS` values. Unknown aliases are rejected
rather than guessed.

Simulator is selected by default, so opening the window does not enumerate a
port, open hardware, read a file, create an output, or start a network listener.

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

When form or workflow validation rejects a value, an internal stable field key
travels beside the normal exception until the Dashboard renders the issue. The
window scrolls the matching field into view, moves keyboard focus there, names
the field in text, and applies a rose error border. A successful correction or
navigation clears the border. Multi-field rules point to the second or bounding
value that must change; failures with no trustworthy field key stay in the issue
card without a guessed target. This hint is presentation state only:
`user-issue.v1`, CLI JSON, saved projects, run manifests, and historical
artifacts are unchanged.

## Source-specific safety behavior

### Simulator

- selected by default;
- deterministic and software-only;
- produces `SYNTHETIC` evidence;
- a PASS verifies the modeled software path, not a physical AFE.

### CSV Replay

- requires an explicit path and channel mapping;
- shows only Replay-specific source fields; Serial details remain hidden;
- provides **Choose CSV file...**, which opens the native local CSV picker only
  after a user click. Cancel preserves the existing path, and choosing a path
  does not read the file;
- loads and validates the complete `csv-replay.v1` dataset during Review;
- keeps the immutable validated dataset closed and in memory until Run;
- reports `CSV_REPLAY`, even if historical rows name a bench source;
- never contacts hardware.

### Serial (read-only)

- shows only Serial-specific source fields; Replay path and bounds remain
  hidden;
- requires an exact profile, logical port, read timeout, poll limit, sample
  bound, and explicit receive-only confirmation;
- supports bounded `READ` and finite `LIVE_MONITOR` jobs; Serial live monitoring
  defaults to the primary channel only and enables secondary/state channels only
  when the selected profile advertises the matching readable capabilities;
- selecting the exact MSP430 Equipment Health v1 profile pre-fills its bus-
  voltage channel in mV as a safe editable starting point; Review still shows
  the exact selected channel before any port can open;
- Discover performs enumeration only, closes the backend, and does not open a
  listed port;
- Review does not open the selected port;
- Review displays both the requested sampling cadence and the conservative
  worst-case serial receive-wait budget; configurations whose combined bound
  exceeds 55 seconds are rejected before Run;
- an optional **Expected capability device ID** requires exact equality before
  measurement reads; it is a protocol/profile label, not authentication or a
  verified physical serial number;
- AFE v1 may declare comma-separated `adcN=afe.chM.input|output` aliases. Review
  shows the complete mapping, and Run accepts it only when every advertised ADC
  is mapped exactly once without adding channels or commands;
- a successful result shows the accepted capability device/profile identity in
  the observation summary. The Dashboard explicitly labels this as protocol
  evidence, not proof of wiring or device authenticity;
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
- The Projects & history batch uses the same owner-thread rule. Its worker sends
  immutable `ValidationBatchProgress` snapshots through a queue; Tk only reads
  them during polling. The determinate progress bar and status text show the
  actual phase, current preset ID, one-based preset number, total, and completed
  terminal-record count.
- **Cancel batch safely** sets the shared cooperative token once. It does not
  kill the thread. The active worker performs cleanup, the batch stops before
  later presets, and the page remains busy until the current manifest is atomically
  published. Closing during a project batch requests the same cancellation and
  waits for that completion before destroying the window.
- The accepted batch Review is also exposed as an immutable presentation
  summary. The Dashboard renders project/run identity, exact destination,
  ordered preset rows, readable Source/Test names, and exact evidence labels;
  Run clears the summary as it consumes the underlying Review.
- A verified two-run comparison adds a read-only guide above the detailed
  table. It names the baseline and candidate, their batch states, whether the
  saved project snapshot changed, matched/one-sided/not-started coverage,
  exact evidence-label matches or mismatches, and changed presets. It does not
  recalculate engineering conclusions. A numeric delta is candidate minus
  baseline; its sign alone is not an improvement/regression decision.
- One selected history row renders only the manifest's existing v3 Replay input
  records. Loading or comparing a saved manifest rechecks path containment,
  byte count, and SHA-256 before display. The table neither opens the original
  CSV nor reruns a preset, and it states that `CSV_REPLAY` is not BENCH evidence.
- Save project, Add preset, Review, Run, Compare, and Clear use the same
  workspace facts as their backend checks. Run is available only while the
  visible preset order, run ID, and destination still match the reviewed batch;
  changing any input asks for Review again. A temporarily incomplete Setup
  disables preset capture without crashing the page and recovers on the next
  valid render.
- Returning from Review invalidates the prepared request and clears its review
  authorization. **Modify setup** from Result also invalidates the prepared
  request but retains copied result evidence as a reference; Run remains
  disabled until the edited setup is validated again. **Start new test** clears
  the prior result and resets the form.
- Export has no implicit default destination: a finalized analysis remains in
  memory until the user types a new path or chooses one through the native
  **Choose save location...** dialog. The picker suggests a format-matching
  filename, and manually entered paths must use the selected `.json` or `.csv`
  suffix. Each newly finalized analysis starts with an empty destination.
  Export uses create-new semantics and refuses to replace an existing file.
- If the only copy of a finalized analysis has not been exported, **Modify
  setup**, **Review same setup**, **Start new test**, **Finish & close**, and the
  window close control ask before discarding it. The safe default returns to
  the Result page so the user can save first.
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
wizard exposes the acceptance criteria used for DC, hysteresis, calibration,
or frequency-response evaluation.
Evidence source, worker state, engineering outcome, limitations, exclusions,
and issues are written as text; meaning is not conveyed by color alone.

The result card presents a five-line decision summary before detailed text:

1. **Run result** explains whether the product completed, remained incomplete,
   was unsupported, was cancelled, or ended in error.
2. **Engineering decision** separately reports PASS/FAIL or explicitly states
   `NO ENGINEERING DECISION`.
3. **Evidence** preserves the exact THEORY, SYNTHETIC, CSV_REPLAY, SPICE,
   HOST_TEST, or specific BENCH class and explains its practical scope.
4. **Claim boundary** repeats `NO_NEW_HARDWARE_VALIDATION` and the first
   unverified item carried by the result.
5. **Next action** points to saving/reviewing a completed result or following
   structured recovery without turning an incomplete run into PASS.

The detailed portion retains the original result summary, every limitation,
every not-verified item, and structured issue recovery. This is presentation
of copied state only; the Dashboard does not derive or revise the engineering
outcome.

A bounded read can finish successfully without an analysis export. DC,
hysteresis, calibration, and frequency-response results can expose the existing
finalized `ResultExportBundle` and write JSON or CSV. Calibration additionally exposes a
strict `calibration-coefficients.v1` file. Result and coefficient destinations
are independent and create-new. Loading coefficients validates and displays
them for inspection only; it does not apply them, rerun analysis, or write
firmware. The Dashboard does not recompute either artifact.

A live-monitor result also finishes without an analysis export. Its final
visible table and `live-monitor.v1` snapshot are observation evidence, not a
criteria evaluation. Oldest-point eviction is reported separately from worker
event drops and invalid/suspect measurement counts.

The reusable interaction rules, acceptance cases, and design rationale are
recorded in the [software interaction design guide](SOFTWARE_INTERACTION_DESIGN_GUIDE.md)
and [Dashboard interaction design audit](UX_DESIGN_AUDIT.md).

## Verified software behavior

- CLI and Dashboard produced equivalent finalized results for the same 24-point
  Simulator DC configuration.
- The calibration workflow reached the same product compiler, worker, core
  fit/evaluator, result export, coefficient writer, and report path for
  Simulator and CSV Replay while retaining `SYNTHETIC`/`CSV_REPLAY` evidence.
- The frequency-response workflow reached the same compiler and worker for
  Simulator and CSV Replay, retained three references per point, evaluated an
  independently reviewed cutoff target, and displayed a logarithmic-frequency
  dB chart without opening a serial source or controlling an instrument.
- The live-monitor workflow reached the same compiler, worker,
  Simulator/Replay/receive-only Serial adapters, terminal result, and Dashboard
  state; finite duration, ring-buffer eviction, pause/resume, time-window
  changes, status counts, and CLI JSON/human views were host-tested. The Serial
  path used only an in-memory backend and made zero application write calls.
- In-memory Serial tests also cover bad-CRC recovery within the reviewed poll
  budget, timeout/disconnect failure, cooperative cancellation, deterministic
  cleanup, and explicit `UNSUPPORTED` results when an optional AFE channel is
  not advertised.
- Missing/invalid Replay input failed during Review, before worker start.
- Field-level Review failures identify the exact control without parsing the
  English error message. Real Windows Tk tests at scaling 1.0, 1.25, 1.5, 1.75,
  and 2.0 verified focus transfer, error styling, automatic vertical reveal,
  and clearing after navigation.
- The 1040×760 minimum layout kept critical Setup, Results, and Projects
  controls horizontally visible at the same five scaling levels. The same
  fresh-process checks exercised standard and forced Windows high-contrast
  rendering, including field focus/reveal and result actions.
- A memory-backed MSP430 receive-only chain opened once during Run, closed once,
  and made zero write calls; no physical port was involved.
- A cooperative blocking service reached `CANCELLED`, ran cleanup, and exposed
  no export.
- Dashboard project batches marshal progress without cross-thread Tk calls,
  disable cancellation after the first accepted request, retain cancelled
  history, show `COMPLETE`/`PARTIAL`/`CANCELLED`/`ERROR`, and label v1 history
  `LEGACY_V1` because v1 did not encode a batch status.
- The batch Review chain asserts the frozen project/run/destination, project
  order, readable Source/Test labels and `SYNTHETIC` evidence at all five Tk
  scaling values, then asserts that Run clears the consumed Review. A bounded
  unit fixture also verifies the `CSV_REPLAY` label without opening hardware.
- Fresh-process Windows Tk tests at scaling 1.0, 1.5, and 2.0 exercised project
  cancellation, terminal history refresh, comparison, keyboard range selection,
  and cleanup-before-close. These are `HOST_TEST`/`SYNTHETIC` results.
- The project comparison chain now also asserts visible project/run identity,
  one-sided result coverage, exact `SYNTHETIC` labeling, and the displayed
  candidate-minus-baseline convention at five scaling levels.
- TD-040C1B fake-toolkit tests cover no selection, multi-selection, v1/v2,
  Simulator-only v3, and populated Replay v3 states. Fresh-process Windows Tk
  tests keep all critical Projects controls within the 1040×760 horizontal
  boundary at 100%, 125%, 150%, 175%, and 200% scaling.
- Fake-toolkit tests exercised every Step 6 callback; a separate real Windows Tk
  smoke verified installed-package startup and safe auto-close.
- Step 7 made actionable controls explicit keyboard-focus targets. Real Windows
  Tk smoke at scaling 1.0, 1.5, and 2.0 verified focus traversal and successful
  layout creation.
- The display refresh kept the same callbacks and immutable state flow while
  adding a shared dark palette, semantic button/progress/table styles, and
  persistent text labels for local, read-only, and evidence boundaries. Fresh
  Windows Tk processes verified the theme, widget tree, and critical horizontal
  control bounds at scaling 1.0, 1.25, 1.5, 1.75, and 2.0. Project tables use a
  bounded initial column width so Save, destination, safe-cancel, and clear
  actions stay visible; these checks are `HOST_TEST` only.
- A real Windows interactive check covered Simulator READ, 12-point DC, and
  12-rising/22-falling hysteresis; valid and malformed CSV Replay; safe
  no-overwrite export; immediate rerun; result actions; scrolling; and clean
  window close. The executed observations remain `SYNTHETIC` or `CSV_REPLAY`
  software evidence only.
- The receive-only live-monitor/device-contract checkpoint passed 2,508 tests and covered
  14,006/14,006 executable package statements. Full Ruff, mypy across 218 source
  files, dependency, 15/15 product-quality, wheel/sdist build, and isolated
  installed-CLI device-contract smoke also passed; commit-bound candidate/audit
  and hosted CI have not run for this uncommitted extension.

## Current limitations

- Keyboard focus and common Tk scaling have automated baseline coverage; full
  screen-reader certification and long interactive sessions remain unverified.
- The hidden-first-paint and revision-gated redraw changes removed the observed
  incomplete first frame during the documented Windows check; behavior across
  every graphics driver, remote desktop mode, and display configuration remains
  unverified.
- The one-command demo is implemented, but it remains a deterministic software
  demonstration and does not validate physical hardware.
- Real COM worker lifecycle, reconnect, device data rate, and long-duration
  timing have not been tested. Automatic reconnect remains disabled; a
  disconnect fails closed.
- AFE ADC aliases are reviewed host metadata. Even a matching reported ID and a
  complete mapping cannot verify which physical signal is wired to a pin. The
  current MSP430 profile uses a static host capability snapshot rather than a
  firmware-unique identity response.
- The connected MSP430 was not enumerated, opened, read, reset, flashed, or
  written during this checkpoint.
- No physical AFE, ADC/DAC accuracy, threshold, gain, bandwidth, wiring, or
  instrument behavior was validated.

See the [CLI guide](product-cli.md), [human-report guide](human-reports.md),
[product-quality acceptance](product-quality-acceptance.md),
[Phase 5 plan](SOFTWARE_PHASE_5_PLAN.md), and
[Step 8 closure report](../reports/software-phase5-step8.md).

Current portfolio screenshots are cataloged in the
[media evidence register](../media/README.md). They use only the deterministic
Simulator and do not add a hardware claim.
