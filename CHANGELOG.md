# Changelog

This file records user-visible product changes.  The project follows semantic
versioning for stable releases and PEP 440 for Python package versions.

## [Unreleased]

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
