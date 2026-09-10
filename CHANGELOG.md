# Changelog

This file records user-visible product changes.  The project follows semantic
versioning for stable releases and PEP 440 for Python package versions.

## [Unreleased]

- Added ordinary voltage-table import through the Dashboard **Import data** tab
  and `import-csv inspect/convert/verify`. Explicit V/mV columns and timezone or
  elapsed-time mappings produce immutable replay/project packages retaining the
  original source, mapping and hashes. Mapping templates are reusable; loading
  an imported setup requires fresh analysis Review. New mapping/manifest v1
  formats preserve the existing replay and project/run formats. This expands
  offline file compatibility and establishes no new device or bench validation.

- Entered local feature freeze after repository-external build, clean wheel
  install, byte-identical normal/Unicode demos, installed CSV Replay history,
  product-quality, privacy, and full regression gates. This checkpoint adds no
  runtime feature and makes no release or hardware-validation claim.
- Added a read-only Replay input archive table to Dashboard history. Selecting
  one v3 run shows each executed Replay preset's archived path, byte count, and
  full SHA-256; reused files retain separate preset references. v1/v2,
  Simulator-only, not-started, no-selection, and comparison states explain why
  details are unavailable. This adds no rerun action, schema, file access, or
  hardware claim.
- Added self-contained CSV Replay inputs to new project-run history. Manifest v3
  records a safe run-relative path, exact byte count, and SHA-256 for every
  Replay preset that actually starts; workers consume the staged copy, repeated
  references share one physical file, and input-copy failures publish nothing.
  Strict manifest v1/v2 documents remain readable and retain their original
  serialized fields. This preserves `CSV_REPLAY` evidence and is not hardware
  validation or manifest authentication.
- Added a structured frozen-review summary before a project batch can run. It
  shows the project and run identities, exact create-new destination, ordered
  presets, readable Source/Test names, and each preset's `SYNTHETIC` or
  `CSV_REPLAY` evidence boundary. The summary clears when Run consumes the
  review; execution, manifests, results, hashes, cancellation, CLI, and public
  API contracts are unchanged.
- Added first-use and empty-state guidance to Projects & history. The page now
  explains the next valid project action, previews the exact current Setup and
  its `SYNTHETIC`/`CSV_REPLAY` boundary, identifies unsaved projects and stale
  reviews, and distinguishes zero, one, or multiple history runs. Save, preset
  capture, Review, Run, Compare, and Clear now follow the existing workspace
  permissions instead of accepting clicks that can only fail.
- Added a decision guide above the Dashboard run-comparison table. It identifies
  baseline and candidate runs, batch states, same-project snapshot drift,
  matched/one-sided/not-started results, exact evidence-label matches or
  mismatches, and changed preset IDs. Numeric deltas remain copied arithmetic
  (`candidate - baseline`) and are explicitly not classified as improvement or
  regression; no result, manifest, comparison, or public API contract changed.
- Split the Dashboard result card into a decision summary and detailed result.
  The summary now distinguishes product completion from engineering PASS/FAIL,
  explains the exact evidence class, repeats the explicit claim boundary, names
  one unverified item, and gives the next safe action. Observation-only results
  say `NO ENGINEERING DECISION` instead of showing an ambiguous `none`.
- Replaced internal Source/Test enum text in the Dashboard with readable labels
  while preserving the original stable values in application state, projects,
  CLI output, and artifacts. Replay and Serial details now use mutually
  exclusive sections, and CSV Replay has a native local-file picker whose
  Cancel action preserves the existing path. The selected file is still read
  and validated only during Review.
- Added contextual beginner guidance to the Dashboard configuration and action
  areas. Simulator guidance is now visible instead of being hidden inside the
  Replay/Serial panel; all six test types explain their main fields in plain
  language, source text preserves `SYNTHETIC`/`CSV_REPLAY` and hardware
  boundaries, and each workflow step explains the next available action or why
  Run remains unavailable. This is presentation-only and changes no workflow,
  permission, result, manifest, or public API contract.
- Added a runtime-gated Dashboard accessibility bridge for Tk runtimes that
  provide the official `tk accessible` API. It assigns stable names, roles,
  help text, chart/table alternatives, and deduplicated step, issue, run, live,
  result, and artifact notifications. The current Windows candidate uses Tk
  8.6.15 and remains unsupported for screen readers after UI Automation exposed
  all 37 application descendants as unnamed panes; keyboard/high-contrast
  tests are no longer described as proof of assistive-technology support.
- Added a 1040×760 Dashboard layout with three-column configuration reflow and
  narrower result-table/save panels. Real Windows Tk tests now cover Setup,
  Results, and Projects at 100%, 125%, 150%, 175%, and 200% scaling.
- Added startup-time Windows high-contrast detection. When enabled, ttk styles,
  scroll canvases, live charts, focus, selection, disabled controls, and error
  borders use Windows system colors; all state and error meaning remains in
  text. Restart the Dashboard after changing the Windows contrast theme.
- Added field-level Dashboard validation guidance without changing
  `user-issue.v1`: form and workflow validation now carry an internal stable
  field key, move focus to the exact editable control, scroll it into view,
  apply a visible error border, and clear that state after correction. Unknown
  or non-field failures continue to use the existing issue card without
  guessing from English error text.
- Refreshed all three Dashboard pages with the shared Precision Lab Console
  theme: deep graphite surfaces, clearer card/input/table hierarchy, semantic
  primary/secondary/cancel controls, real-progress styling, and persistent
  local/read-only/evidence boundary labels. The native ttk implementation adds
  no fake data, network assets, idle animation, or changes to workflow logic.
- Prevented wide project-history columns from pushing Save, output-directory,
  safe-cancel, and clear actions outside the 1180-pixel minimum window. Added
  visible-boundary tests at 100%, 125%, 150%, 175%, and 200% Windows scaling,
  and changed the new-project defaults from AFE-specific wording to neutral
  Analog Validation Studio wording.
- Added Dashboard Projects & history: create/open/save-as projects, capture the
  current setup as a preset, review and execute a background offline batch,
  load verified history, and compare outcomes, evidence and metric deltas.
  Changed batch inputs invalidate review; closing waits for batch completion;
  unsaved project changes require discard confirmation.

- Added a complete host-side linear-calibration product workflow shared by the
  Simulator and strict CSV Replay sources: reviewed request compilation,
  bounded service execution, criteria, `TestRunResult`, and JSON/CSV results.
- Added deterministic `calibration-coefficients.v1` JSON persistence with
  create-new writes, strict bounded loading, full fit lineage, and explicit
  validation-only inspection that never silently applies or flashes values.
- Added CLI and Dashboard calibration flows, separate result/coefficient file
  controls, before/after error presentation, and deterministic human reports.
- Added a complete frequency-response product workflow for deterministic
  Simulator and strict CSV Replay sources: explicit Hz/input/output triples,
  acceptance criteria, `TestRunResult`, JSON/CSV export, CLI, Dashboard, and a
  deterministic logarithmic-frequency magnitude chart.
- Kept the Simulator's modeled cutoff independent from the reviewed acceptance
  target so tests can exercise both PASS and FAIL without changing criteria.
  Frequency results preserve all three record references per point and remain
  `SYNTHETIC` or `CSV_REPLAY`; no signal generator, oscilloscope, or AFE was used.
- Added a finite `live-monitor.v1` observation workflow for Simulator and strict
  CSV Replay. It reuses the reviewed compiler, streaming read path, bounded
  worker, CLI, and Dashboard while deliberately producing no engineering
  PASS/FAIL or analysis export.
- Added bounded live curves, cooperative pause/resume, presentation time-window
  selection, VALID/SUSPECT/INVALID totals, and separate accounting for ring-
  buffer eviction and worker-event drops.
- Added finite receive-only Serial live monitoring with primary-only safe
  defaults, a required exact primary channel, an explicit confirmation gate,
  conservative cadence-plus-polling runtime bounds, zero application write
  surface, and fail-closed timeout,
  disconnect, cancellation, and unsupported-capability behavior. Verification
  used in-memory backends only; real-port reliability gates remain outstanding.
- Added optional exact capability-ID pinning and the versioned
  `serial-channel-alias.v1` AFE ADC observation map. A mapped run requires full
  advertised-ADC coverage and stops before telemetry on identity, coverage, or
  collision failures; IDs are unauthenticated and mappings do not prove wiring.
- Added strict `validation-project.v1` and `validation-preset.v1` documents,
  a six-preset Simulator starter, and explicit bounded all-or-selected offline
  batch execution. Saved projects cannot persist Serial connection settings.
- Added create-new `validation-run-manifest.v2` history with an exact project
  snapshot, per-preset configuration identities, copied finalized outcomes and
  metrics, evidence labels, software version, SHA-256-verified artifacts,
  planned/not-started preset IDs, and explicit `COMPLETE`, `PARTIAL`,
  `CANCELLED`, or `ERROR` batch state. Strict v1 history remains readable and
  is never rewritten.
- Added thread-safe cooperative batch cancellation and real per-preset progress.
  The current worker finishes cleanup before later presets are stopped; CLI
  progress uses stderr, JSON remains isolated on stdout, and cancellation exits
  with code 130.
- Connected the same batch progress and cancellation contracts to the Dashboard.
  The Projects & history page shows the actual phase, current preset, planned and
  completed counts, offers one cooperative cancel action, waits for cleanup and
  manifest publication on close, and refreshes terminal v2 state in history.
  Legacy v1 history is labeled explicitly instead of inventing a batch status.
- Added explicit history verification and `validation-run-comparison.v1`.
  Comparison reports configuration/status/outcome/evidence/count/metric changes
  without rescanning directories or recalculating PASS/FAIL.
- Added installed `project create`, `project inspect`, `project run`, `project
  history`, and `project compare` CLI paths plus public project APIs and golden
  compatibility coverage.
- Extended the public Phase 3/5 compatibility contracts and regression suite;
  the current local calibration + frequency-response + receive-only live-monitor
  + project/history/display-layer increment passes 2,627 tests and 15,639/15,639 package
  statements. Full Ruff, mypy across 225 files, dependency, 15/15
  product-quality, wheel/sdist build, and repository-external installed project
  CLI smoke pass. This is host software evidence only and makes no AFE bench
  claim.
- Hardened the frequency Simulator against overflow across extreme but finite
  frequency ranges, normalized terminal live-monitor state after a pause/finish
  race, and aligned the reviewed frequency-data completeness text with the
  conservative v1 cutoff-publication rule.
- Made release-candidate clean-install subprocesses explicitly scrub inherited
  `PYTHONPATH`, preventing an outer development checkout from making pip mistake
  the candidate package for an already-installed distribution.
- Reorganized the repository front page around product value, a reproducible
  software demo, architecture, compatibility, evidence limits, and a concise
  recruiter-facing verification snapshot.
- Added two classified Windows Dashboard screenshots captured from a
  Simulator-only DC run; both remain `SYNTHETIC` and explicitly make no new
  hardware-validation claim.
- Added a security policy, contribution guide, pull-request checklist,
  CODEOWNERS, weekly Dependabot configuration, and an owner-gated publication
  and LinkedIn checklist.
- Added exact GitHub/LinkedIn portfolio-copy previews and a dated local
  publication-preparation record; neither document performs a remote change.
- Synchronized current-state plan, traceability, beginner, environment,
  Dashboard, media, hardware, and firmware documentation while retaining
  historical checkpoint results.
- Redesigned the local Dashboard with modern ttk styling, Setup/Results tabs,
  visible vertical scrolling, mouse-wheel routing, and a hidden-first-paint
  sequence that reduces incomplete initial rendering on the tested Windows host.
- Added explicit **Modify setup**, **Review same setup**, **Start new test**, and
  **Finish & close** result actions while preserving reviewed-run boundaries.
- Added presentation-only READ observations so successful acquisition remains
  visible without being mislabeled as an engineering PASS/FAIL analysis.
- Fixed hidden configuration errors, stale duplicate-export success text,
  immediate-rerun terminal-event leakage, and stale review authorization after
  returning to editable configuration.
- Added Windows interaction evidence and regression coverage for valid and
  invalid Simulator/CSV paths, result navigation, scrolling, redraw gating,
  first paint, and legacy Tk fallback behavior.
- Added a reusable software-interaction design guide covering workflow state,
  adaptive scrolling, native save behavior, error recovery, evidence labels,
  automated checks, and manual acceptance criteria.
- Private beta feedback and release-candidate decisions remain pending.
- The owner selected the MIT License and it is present in source/package
  metadata. No Git tag, GitHub Release, or PyPI publication has been created.

## [0.1.0b1] - 2026-08-31

First controlled private-beta candidate for Analog Validation Studio.

### Added

- Controller-neutral measurement, capability, test-run, protocol, adapter,
  analysis, runner, export, and product-workflow APIs.
- Deterministic Simulator and strict CSV Replay data sources.
- Receive-only AFE v1 and independent MSP430 Equipment Health v1 serial
  profiles with optional pyserial packaging.
- Installed CLI, local Tk Dashboard, evidence-visible reports, and a
  reproducible offline demonstration.
- Hosted Windows/Ubuntu CI for Python 3.10, 3.12, and 3.14, with 100% package
  statement coverage, Ruff, mypy, dependency, build, and clean-install gates.
- A deterministic, create-new release-candidate verifier with repeated builds,
  fresh base/serial installs, installed synthetic-demo reproduction, SHA-256
  identities, and a privacy-minimal host-evidence manifest.
- Beginner installation, private-beta testing, troubleshooting, known-limit,
  checklist, and sanitized structured-feedback workflows verified against the
  hosted wheel in a clean short-path environment.
- A third-party-style read-only adapter example that imports only the installed
  top-level public API and passes the shared workflow from a repository-external
  isolated Python process with explicit SYNTHETIC provenance and zero writes.

### Safety and evidence limits

- Simulator/demo results are synthetic software evidence.
- Serial support is receive-only at the product boundary.
- No configurable AFE has been built or bench-validated; verified AFE hardware
  performance claims remain zero.
- The separate MSP430 Equipment Health Controller remains an independent peer
  product connected only through a public compatibility profile.

### License status

At this historical beta checkpoint, no license had been selected. The later
Unreleased line records the owner-selected MIT License without implying that a
tag or public Release exists.
