# Changelog

This file records user-visible product changes.  The project follows semantic
versioning for stable releases and PEP 440 for Python package versions.

## [Unreleased]

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
  buffer eviction and worker-event drops. Serial live monitoring remains
  disabled pending an explicit real-device reliability gate.
- Extended the public Phase 3/5 compatibility contracts and regression suite;
  the local unmerged calibration + frequency-response + live-monitor increment
  passes 2,459 tests and 13,834/13,834 package statements. Full Ruff, mypy,
  dependency, 15/15 product-quality, repeated-build, fresh base/serial install,
  and installed Simulator/Replay monitor gates pass. This is host software
  evidence only and makes no AFE bench claim.
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
- No public license, Git tag, GitHub Release, or PyPI publication has been
  selected or created.

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

No license has been selected.  All rights remain reserved until the project
owner makes and documents a separate licensing decision.
