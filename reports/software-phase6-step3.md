# Software Phase 6 Step 3 Verification Report

**Date:** 2026-08-31<br>
**Status:** PASS — private-beta version and package metadata aligned<br>
**Evidence class:** HOST_TEST / SYNTHETIC / isolated package build<br>
**Physical serial or hardware operation:** none<br>
**Verified AFE bench-performance claims:** 0<br>
**Implementation commit:** `01ae57e`<br>
**Passing GitHub Actions run:** `33445311456`

## Outcome

The package now has one consistent private-beta version, `0.1.0b1` (displayed
in release prose as `v0.1.0-beta.1`).  Python import, installed distribution
metadata, CLI JSON, public compatibility manifests, deterministic demo/report
artifacts, README, and changelog all agree on that version.

This checkpoint prepares a beta candidate.  It does not create a Git tag,
GitHub Release, PyPI publication, public license, or v1.0 claim.

## Package metadata

| Field | Verified value |
|---|---|
| Distribution | `mixed-signal-afe-validation-platform` |
| Version | `0.1.0b1` |
| Product | Analog Validation Studio |
| Author | `Carlos-0798` |
| Author email | omitted |
| Requires Python | `>=3.10` |
| Development classifier | Beta |
| Declared Python classifiers | 3.10, 3.12, 3.14 |
| Repository/documentation/issues URLs | project GitHub URLs |
| License metadata | no license selected |
| Packaged license notice | `LICENSE` included; all rights reserved |

The metadata deliberately contains no personal email.  No SPDX identifier or
open-source license classifier was invented.  `CHANGELOG.md` states the same
license and hardware-evidence boundaries and is included in the sdist.

## Version-bearing golden updates

Changing the version correctly changes bytes in generated result/report/demo
files because those artifacts retain generator and software version lineage.
The affected hashes were regenerated and reviewed.  Unrelated replay fixtures,
analysis inputs, numerical criteria, outcomes, and evidence labels were not
rewritten.

The initial complete regression therefore reported three expected golden
failures.  After updating only the version-bearing expected hashes, all 21
demo/report/public-contract checks passed and the complete suite passed.

## Verification

| Gate | Result |
|---|---|
| Import / distribution / CLI version equality | PASS — `0.1.0b1` |
| Metadata and privacy assertions | PASS |
| Version/public/golden focused suite | PASS |
| Final full local pytest suite | PASS — 2,194 |
| Package statement coverage | PASS — 11,470/11,470; 100% |
| Ruff | PASS |
| mypy | PASS — 192 source/tool/test files |
| `pip check` | PASS |
| Isolated sdist and wheel build | PASS |
| Hosted Windows/Ubuntu Python 3.10/3.12/3.14 | PASS |
| Hosted coverage/static/build/base/serial clean install | PASS |

One local coverage invocation completed 2,193 tests with one display-only Tk
skip after the host Python installation intermittently could not read an
existing Tcl/Tk library file.  A separate final full local invocation passed
all 2,194 tests, and the hosted Windows 3.10/3.12/3.14 jobs all passed the same
complete suite.  The skip is retained here as environment evidence rather than
silently reported as a pass.

## Local verification artifacts

These are ignored local build outputs, not published releases:

| Artifact | Size | SHA-256 |
|---|---:|---|
| `mixed_signal_afe_validation_platform-0.1.0b1-py3-none-any.whl` | 246,866 bytes | `ed255f39545d0c72d3b42178a3d5d91fba2a60d12b4b33014ddbdf2228c7a8e4` |
| `mixed_signal_afe_validation_platform-0.1.0b1.tar.gz` | 452,789 bytes | `288addc1ebbb2107008d2ed6120f1e3761f214dd892cad736b59083df72d5eaf` |

Future candidate hashes may differ after additional Step 4–7 code and
documentation changes.  Only the final audited candidate manifest may be used
for tester delivery.

## Safety and evidence boundary

No port was enumerated or opened, no controller was reset/flashed/read/written,
and no AFE, ADC, DAC, comparator, instrument, breadboard, or supply was used.
Updated demo/report bytes remain `SYNTHETIC` software evidence.  The separate
MSP430 project remains an optional peer integration, not a component or parent
of this product.

## Next checkpoint

Step 4 adds one create-new release-candidate verifier that performs repeatable
build, clean-install, installed-demo, dependency-boundary, artifact-hash, and
privacy-minimal manifest checks.  It still will not publish a release or access
real hardware.
