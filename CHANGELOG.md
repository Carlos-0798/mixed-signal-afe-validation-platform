# Changelog

This file records user-visible product changes.  The project follows semantic
versioning for stable releases and PEP 440 for Python package versions.

## [Unreleased]

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
