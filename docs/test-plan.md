# Test plan and evidence labels

## Evidence labels

- `THEORY`: result derived from a documented equation and nominal inputs.
- `SPICE_IDEAL`: result produced by the included idealized LTspice netlists.
- `SYNTHETIC`: data generated in software to test analysis paths.
- `HOST_TEST`: executable Python test result.
- `BENCH_CONTROLLER`: physical controller bytes, not automatically an external-sensor or AFE measurement.
- `BENCH_DMM` / `BENCH_SCOPE`: future physical measurements with recorded wiring and instruments.

Only a specific `BENCH_*` record may support the physical behavior it directly observed. Controller UART evidence cannot support AFE voltage/gain/bandwidth claims. Phase 0 can produce the first four labels only.

## Phase 0 executable checks

- CRC known vector, empty payload, and round trip.
- Valid telemetry and command round trips.
- CRC mismatch, missing fields, non-ASCII, malformed values, and overlong input rejection.
- Least-squares gain, offset, and R-squared on exact and noisy synthetic points.
- High/low saturation exclusion and insufficient-linear-data rejection.
- Rising/falling Schmitt transition interpolation and hysteresis width.
- LTspice ideal buffer, gain, RC cutoff, and Schmitt topology tasks when the executable is available.

## Phase 1 entry gate

Do not power the analog assembly until the open toolchain, inventory, permission, and wiring items in `ASSUMPTIONS.md` are resolved. Phase 1 records must include actual part suffixes, supply current limit, pre-power continuity checks, measured 3.3 V and VBIAS, DMM model, gain-jumper state, raw DC sweep data, and any observed saturation or instability.

## Software Phase 4 serial host checks

- Use a deterministic in-memory backend before any OS/COM backend.
- Cover fragmented/coalesced records, normal timeout, open/read/close failure,
  disconnect, partial-frame reset, finite reconnect, and overlong recovery.
- Require exact raw bytes, UTC receive time, logical port, explicit profile,
  parse/error outcome, and optional typed sequence observation.
- Enforce per-record, event-count, total-byte, and metadata bounds; record FIFO
  eviction counters and do not persist/upload raw records automatically.
- Run the installed-wheel chain without pyserial to prove simulation/replay and
  core imports remain hardware optional.
- Drive every valid/invalid AFE golden record through the selected AFE serial
  profile; retain exact accepted bytes and stable rejected error families.
- Verify telemetry-only 16-bit continuity, explicit legacy-to-canonical
  Measurement mapping, strict capability transaction aggregation, and state
  rollback if a final raw outcome cannot be retained.
- Drive every repository-owned MSP430 valid/invalid fixture through the
  independent read-only profile; verify `TEL/ACK/STS/CFG/LOG`, 32-bit TEL wrap,
  unknown state rejection, raw sentinel/fault retention, and unavailable-safe
  Measurement mapping.
- Confirm the MSP430 profile has no command encoder, output capability, or
  `SAFE_SHUTDOWN`, and imports no peer-project runtime namespace.
- Construct `SerialAdapter` only from an explicitly matching closed session,
  profile identity/version, record limit, evidence source, and capability
  projector; reject mismatches before I/O.
- Run the same reusable eight-check read-only adapter contract against both AFE
  and MSP430 serial configurations, then drive both through the unchanged
  `ReadWorkflow` with an in-memory backend.
- Retain AFE native capabilities, explicitly alias
  `adcN/dacN/pwmN/dinN` to canonical workflow names, and reject any projector
  that changes identity, channel counts, numeric ranges, or adds commands.
- For the optional product-level AFE observation map, require an exact expected
  capability ID and complete unique native-ADC coverage; reject identity
  mismatch, missing/extra/repeated mappings, leading-zero channel aliases, and
  non-AFE use before measurement telemetry. Verify the no-alias projection is
  unchanged and a two-ADC input/output chain remains receive-only.
- Bound capability/read polling and queued Measurements; cover timeout, bad CRC,
  overlong input, buffer overflow, profile failure, capability drift, fatal
  session loss, and successful-reconnect capability invalidation.
- Prove read-only MSP430 DC and hysteresis runner preflight returns
  `UNSUPPORTED` with zero reads/writes using a backend that exposes no write
  method.
- Install the built wheel outside the repository without pyserial and run an
  installed-package SerialAdapter -> ReadWorkflow smoke while asserting
  `HOST_TEST`, raw lineage, deterministic close, and zero writes.
- Keep real port/HIL commands `NOT RUN` until the separate owner-approved gate;
  host lifecycle tests do not prove OS timing, UART electrical behavior, or a
  physical controller link.

## Software Phase 4 optional controller HIL checks

- Keep the base wheel usable without pyserial; install the driver only through
  the optional `serial` extra.
- Discover first, require an explicit application-UART port, and never use a
  COM number as a library default or capability inference.
- Use a backend with no public write method; send no command bytes, flash
  nothing, and do not change FRAM.
- Capture through the current `SerialAdapter` and `ReadWorkflow`, not an ad hoc
  parser; persist local create-new evidence with raw bytes/hashes, CRC,
  sequence/uptime, sentinels/faults, timeout, open/close, disconnect/reconnect,
  and zero-write counters.
- Keep Protocol v1 parsing strict. A documented legacy HB line may be classified
  only out of profile, with exact syntax and matching TEL sequence/uptime;
  malformed, unaligned, or other no-CRC lines remain anomalies.
- Label exact firmware `UNCONFIRMED_PASSIVE_ONLY` when passive telemetry has no
  version field. Do not infer external sensors, fan, wiring, 5 V, or AFE status
  from controller connectivity.

## Software Phase 4 compatibility closure checks

- Freeze exact `__all__` exports for transport, envelope, channel mapping,
  MSP430 protocol, profiles, serial adapters, and optional pyserial integration.
- Freeze new schema strings, serial-profile identities, public enum/flag
  members, primary constructor/function parameter shapes, and owned error
  inheritance relationships.
- Hash prior AFE/envelope/MSP430 fixtures plus one exact Phase 4 composite; do
  not hash the manifest itself.
- Rebuild AFE and MSP430 product chains from an independently defined
  structural backend using only public interfaces.
- Preserve 16/32-bit sequence wrap, canonical channels, raw lineage, typed CRC
  rejection, unavailable sentinel/fault mapping, `HOST_TEST` provenance,
  deterministic close, and absence of a write method.
- Rerun every Phase 1–3 golden contract before accepting the Phase 4 freeze.
- Require full pytest, 100% formal+optional package coverage, Ruff, mypy,
  dependency checks, isolated sdist/wheel build, archive-content inspection,
  and clean base/serial wheel installations.
- Keep the Step 7 physical UART capture separate; Step 8 discovery/build/install
  checks must not be reported as a repeated HIL or AFE/peripheral validation.

## Software Phase 5 product-layer checks

- **Step 1 complete:** keep `analog_validation_app` above the frozen core and
  optional OS backend; reject imports from the core back into the product layer
  and copied protocol/analysis implementations in the product package.
- **Step 1 complete:** run CLI help/version/profile commands from an installed
  base wheel without pyserial and without importing Tk or opening a display;
  verify unknown-command exit/output behavior and the module entry point.
- **Step 1 complete:** freeze bounded job/result/catalog/issue/CLI-output schema
  identities, require limitations, and reject output-capable product requests.
- **Step 2 complete:** freeze `product-job-event.v1`, bounded event text/queue,
  seven worker states, cancellation token, public worker errors, and finite
  join/close limits.
- **Step 2 complete:** verify one worker owns one job and normal, cancellation,
  factory/service/cleanup failure, context close, and completion-race paths
  clean up and never promote incomplete or cancelled evidence to PASS.
- **Step 2 complete:** bound the worker event queue/text and join wait; verify
  FIFO eviction counters, monotonic indexes, no orphan thread after cooperative
  services, and explicit timeout for a non-cooperative service. Job-specific
  duration/record bounds remain application-service responsibilities.
- **Step 3 complete:** freeze the installed `version`, `profiles`, `ports`,
  Simulator/Replay `read`/`monitor`/`dc`/`hysteresis`/`calibration`/`frequency`, coefficient
  inspection, and receive-only `observe`
  commands; verify stable human/JSON output and exits 0/1/2/3/4/5/70/130.
- **Step 3 complete:** exercise Simulator, CSV Replay, and receive-only
  SerialAdapter product chains
  through the same application service. Serial tests use an in-memory backend
  unless a separate physical-HIL authorization is recorded.
- **Step 3 complete:** require explicit port, profile, duration/record bounds,
  and read-only review
  for `observe`; do not expose a write method, raw command box, automatic port
  choice, or capability inference from a USB name.
- **Step 3 complete:** verify cooperative cancellation and cleanup in a real
  child Python process by injecting `KeyboardInterrupt` at the interpreter
  boundary. Interactive Windows console `Ctrl+C`/`Ctrl+Break` and real-COM
  worker cancellation remain explicit later smoke gates.
- **Step 4 complete:** build bounded immutable report/chart views only from
  finalized result bundles; DC uses frozen predicted values, hysteresis uses
  exported adjacent transitions/final threshold metrics, calibration uses
  exported before/after signed errors, and frequency response uses exported
  amplitude gain/cutoff values on a logarithmic frequency axis, with no refit,
  cutoff re-interpolation, outcome change, or provenance promotion.
- **Step 4 complete:** freeze text/Markdown/self-contained HTML/SVG plus manifest
  output with no script or remote resource; display evidence, limitations,
  not-verified items, versions, input identity, lineage, and hashes using text as
  well as visual status.
- **Step 4 complete:** verify strict JSON/CSV loading, 10,000-point bound,
  hostile text and substituted-SVG rejection, create-new atomic directory
  publication, staging cleanup, path races, five artifact hashes, installed base
  wheel execution, and preserved PASS/FAIL/INCOMPLETE/UNSUPPORTED/ABORTED exits.
- **Step 5 complete:** test immutable bounded Dashboard state/actions and the
  presenter headlessly; reject cross-thread presenter use and preserve catalog,
  worker event, issue, finalized result, report point, and path-free artifact
  identity without recomputing engineering conclusions.
- **Step 5 complete:** keep Tk imports inside the explicit app/widget boundary;
  route updates through owner-thread polling, verify rendering-only widgets,
  cooperative cancel, finite close/join, and actual worker cleanup.
- **Step 5 complete:** launch and safely auto-close a real Windows Tk window,
  verify Simulator/AFE defaults and textual status, and confirm no pyserial
  import, port access, file creation, network listener, or hardware claim.
- **Step 6 complete:** test the fixed source/test/configure/review/run/result
  state machine, what/why/confirm guidance, strict typed form conversion, stale
  review invalidation, visible criteria, and every widget callback headlessly.
- **Step 6 complete:** prove CLI/Dashboard finalized-result equivalence for the
  same synthetic DC request, validate Replay before worker start, and use a
  write-trap memory backend to prove reviewed MSP430-shaped receive-only Run
  opens/closes exactly once with zero write calls.
- **Step 6 complete:** verify cooperative Dashboard cancellation reaches
  `CANCELLED`, runs cleanup, creates no export, and that JSON/CSV export remains
  create-new. Repeat installed-package base import, synthetic CLI, and real Tk
  startup/close without physical-port access.
- Keep create-new output, hostile path/text/Unicode, sensitive raw-data
  exclusion, and no-network checks when the report is later embedded in the
  demo. Phase 5 reports and Dashboard deliberately provide no overwrite mode.
- Run the deterministic installed-package demo in a new directory and compare
  exact machine/result/report/plot manifest hashes.
- Before Phase 5 closure, require full pytest and coverage, Ruff, mypy,
  dependency checks, sdist/wheel inspection, base/serial external installs,
  CLI/demo smoke, and repeat the real Windows Dashboard launch/close smoke or
  record an honest `NOT RUN` result when the environment cannot display it.
- Keep the earlier controller UART HIL in its own report. Product UI tests and
  screenshots are not AFE, peripheral, electrical-safety, timing, or long-run
  hardware evidence.

## Post-beta calibration and frequency-response checks

- Require calibration and frequency-response requests to use the same reviewed
  compiler, service, bounded worker, result export, CLI, Dashboard, and report
  boundaries as the accepted read/DC/hysteresis workflows.
- For frequency response, keep the deterministic Simulator model cutoff
  separate from the acceptance target cutoff. Verify an exact default PASS and
  a deliberate model/target mismatch that returns engineering exit `1`/`FAIL`.
- Preserve three references per frequency point: explicit Hz, input amplitude,
  and output amplitude. Reject unequal batches, nonpositive frequency/amplitude,
  mixed source, invalid lineage, ambiguous crossings, and tampered results.
- Exercise strict CSV Replay grouping, stable JSON/CSV round trips, dedicated
  Dashboard controls, and presentation-only logarithmic-frequency SVG output.
- Require full package statement coverage, Ruff, mypy, dependency consistency,
  repeated isolated build, fresh base and `[serial]` installs, and an installed
  frequency CLI/report smoke before committing the combined increment.
- The formal release-candidate/audit tools remain commit-bound and must be run
  only after an owner-approved clean commit. Hosted CI remains `NOT RUN` until
  an owner-approved push. Neither gate may enumerate/open a physical port.

## Post-beta bounded live-monitor checks

- Compile `LIVE_MONITOR` through the same six-step reviewed product boundary as
  the other workflows; reject Serial and any output-capable request before a
  service or adapter is created.
- Limit every job to at most 55 seconds and 10,000 acquired measurements. Keep
  the retained ring buffer independently bounded from 1 to 10,000 points and
  keep the visible time window bounded from 0.1 to 3,600 seconds.
- Exercise Simulator and strict CSV Replay through the shared streaming-read
  workflow. Verify multi-channel batches, normal completion, early end of data,
  cancellation, cleanup, invalid configuration, and unequal service batches.
- Freeze the `live-monitor.v1` snapshot/trace public contract, all relevant
  CLI paths, product services, Dashboard dataclasses, and stable maximums in the
  Phase 2/3/5 golden manifests.
- Verify ring-buffer eviction, VALID/SUSPECT/INVALID counts, last timestamp,
  cooperative pause/resume, time-window filtering, and worker-event dropped
  counts as separate facts; no one counter may be presented as another.
- Verify CLI human and JSON views and Dashboard chart/table/status presentation
  without producing an analysis bundle, engineering PASS/FAIL, or automatic
  file output.
- Exercise every live Dashboard callback headlessly and run a real Tk
  keyboard/scaling/startup smoke on a complete Tcl/Tk runtime. If the current
  interpreter cannot load Tk, record that smoke as `NOT RUN` instead of treating
  a mocked widget test as visible-GUI evidence.
- Treat screen-reader readiness as a separate gate: record the Tcl/Tk patch
  level, require an actual accessibility metadata API, inspect programmatic
  names/roles/values and focus through Windows UI Automation, verify dynamic
  events with Narrator, and complete a real-user task chain. Keyboard focus,
  visible text, high contrast, or mocked metadata calls alone cannot pass it.
- Require complete pytest statement coverage, Ruff, mypy, dependency checks,
  isolated build, fresh base/serial installs, and an installed Simulator/Replay
  monitor smoke before an owner-approved commit.
- Keep real-device serial reliability claims deferred until device identity,
  receive-only permissions, disconnect/reconnect, sample-rate limits, memory
  behavior, 30-minute/2-hour soak tests, and evidence classification have
  separate acceptance records. The optional expected ID is not authentication,
  and no host test may be promoted to physical timing, wiring, or AFE validation
  evidence.

## Post-beta local test-project and history checks

- Freeze strict `validation-project.v1`, `validation-preset.v1`,
  `validation-run-record.v1`, `validation-run-manifest.v1` compatibility,
  `validation-run-manifest.v2`, `validation-run-manifest.v3`,
  `validation-run-input-artifact.v1`, and
  `validation-run-comparison.v1` schemas plus their public API/CLI shapes.
- Require projects to contain 1–32 unique offline presets. Reject Serial source
  or connection settings, unsafe identifiers, unknown fields, duplicate JSON
  keys, non-finite numbers, NUL, invalid UTF-8, excessive size/counts, and replay
  paths that escape the project directory.
- Verify that inspect parses only project metadata and opens no replay, adapter,
  port, or output path. Treat run as the only resource-opening boundary.
- Run all six starter presets and explicit ordered subsets through the existing
  reviewed compiler/service/worker. Assert deterministic source/outcome meaning,
  including no engineering conclusion for READ/LIVE_MONITOR.
- Publish only to a new directory through staging. On any preparation,
  execution, artifact, manifest, rename, or existing-target failure, leave no
  partially published run.
- Preserve the exact project snapshot, software version, per-preset canonical
  configuration SHA-256, terminal states, copied finalized outcomes/evidence,
  bounded metrics/limitations, and result/coefficient artifact hashes.
- For every executed CSV Replay preset, copy the bounded source into staging
  before preparation, run from that copy, and preserve run-relative path, byte
  count, and SHA-256. Deduplicate one resolved source without losing per-preset
  references; never open or archive a not-started preset.
- Reject missing, changed-size, changed-content, unsafe, unreadable, or oversized
  input artifacts. Any input-copy failure must leave no published directory or
  staging residue, and original v1/v2 documents must retain their exact shapes.
- Load history only from explicit manifest paths. Reject duplicates, mixed
  project IDs, inconsistent summaries, missing/oversized artifacts, and digest
  mismatches; do not recursively scan user directories.
- Compare only two verified manifests from the same project. Detect project or
  preset configuration changes even when metrics match, report missing presets,
  and never refit/re-evaluate or change a stored PASS/FAIL.
- Exercise human and JSON CLI output, stable exit precedence, malformed inputs,
  output collisions, and fresh installed-wheel create/inspect/run/history/
  compare paths without installing or loading the Serial backend.
- Exercise normal completion, pre-first cancellation, between-preset
  cancellation, active-worker cancellation, cleanup failure, retained terminal
  records, explicit not-started IDs, progress ordering, exit `130`, and strict
  JSON-stdout/progress-stderr separation.
- Exercise Dashboard queue handoff, determinate progress, idempotent cancel
  state, terminal v2/v3 history refresh, explicit v1 labeling, and window-close
  cancellation. Run actual Tk keyboard/scaling flows in fresh processes so one
  Tcl interpreter cannot contaminate another case.
- Exercise the read-only Dashboard input-archive view for no selection, one and
  multiple selections, v1/v2 history, Simulator-only v3, and populated Replay
  v3. Assert exact path/bytes/SHA-256 display, table clearing during comparison,
  unchanged evidence text, and 1040×760 horizontal control bounds at all five
  supported Windows scaling values.
- Keep SHA-256 described as integrity, not authentication. Keep Dashboard
  signed manifests, raw READ/LIVE output-observation artifacts, concurrent scheduling,
  cloud sync, and real-device batches explicitly deferred.

## Post-beta Dashboard narrow/high-contrast checks

- Treat 1040×760 as the supported minimum window. Verify the actual root size,
  critical-control horizontal bounds, and usable input/button widths rather than
  accepting an OS-enlarged window as a pass.
- Reflow dense configuration groups to three columns and constrain fixed result
  table/text widths. Keep vertical scrolling and avoid a horizontal scrollbar
  that could hide required actions from a first-time user.
- Run Setup and Results in fresh Windows Tk processes at scaling 1.0, 1.25, 1.5,
  1.75, and 2.0 in both standard and forced high-contrast modes. Keep field
  focus/highlight/reveal/clear checks in the same chain.
- Run the Projects batch/history/keyboard workflow at 1040×760 across the same
  five scaling values, using only Simulator and new temporary output paths.
- Read the Windows high-contrast flag without changing it. In enabled mode use
  Windows system window/text/highlight/disabled colors for ttk widgets and
  native canvases while retaining explicit text for state, evidence, errors,
  cancellation, and limitations.
- Record that startup-time detection requires an application restart after an
  OS theme change. Keep screen-reader announcements, Remote Desktop, long
  keyboard sessions, localization, and widths below 1040 in separate manual
  acceptance work.

## Deferred bench acceptance

- At least ten DC points per gain setting, with raw data retained.
- Real saturation limits determined before fitting.
- Oscilloscope stability evidence where permitted.
- Theoretical, SPICE, and bench values shown in separate columns.
- No target accuracy stated as achieved until uncertainty and repeatability are evaluated.
