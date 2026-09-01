# Software Phase 6 Step 4 Verification Report

**Date:** 2026-08-31<br>
**Status:** PASS — deterministic candidate verifier accepted<br>
**Evidence class:** HOST_TEST / SYNTHETIC / isolated package installation<br>
**Physical serial or hardware operation:** none<br>
**Verified AFE bench-performance claims:** 0<br>
**Accepted implementation commit:** `0c04aee9b2de22128d0d9592dc9451f0b2632544`<br>
**Passing GitHub Actions run:** `33447031789`

## Outcome

The repository now has one create-new release-candidate verifier that starts
only from a clean Git commit and emits `release-candidate-manifest.v1` only
after every host gate passes. It runs the complete test/coverage/static suite,
builds twice, compares exact artifact bytes, installs the wheel into fresh base
and `[serial]` environments, reproduces the installed synthetic demo in normal
and Unicode paths, validates package/dependency boundaries, and checks manifest
privacy before an atomic directory rename.

The same commit produced byte-identical wheel, normalized sdist, and manifest
files on the local Windows/Python 3.12 host and the hosted Windows/Python 3.12
runner. The uploaded GitHub artifact has a seven-day retention bound. It is not
a Git tag, GitHub Release, PyPI upload, public license, or tester delivery.

## Why sdist normalization is legitimate

The initial two-build experiment found that the wheel was byte-identical but
the raw `.tar.gz` sdist was not. All 231 extracted file contents were identical;
only archive/gzip timestamps and container metadata differed. The verifier now
rewrites generated sdist metadata using the source commit timestamp, fixed
owner/mode values, sorted safe member names, and a filename-free gzip header.

This does not hide source drift. Both independently built archives are
normalized separately, and any different filename or file payload still
changes the final size/hash and fails the gate. Unsafe absolute/backslash/`..`
members, links, excessive members, and excessive expanded size are rejected.

## Accepted gates

| Gate | Result |
|---|---|
| Clean source identity | PASS — full commit recorded; dirty/untracked source rejected |
| Complete local suite | PASS — 2,211 tests |
| Package statement coverage | PASS — 11,470/11,470; 100% |
| Ruff | PASS |
| mypy | PASS — 195 source/tool/test files |
| Development `pip check` | PASS |
| Independent isolated builds | PASS — wheel and normalized sdist byte-identical |
| Archive integrity | PASS |
| Fresh base install | PASS — `--no-deps`, no pyserial, no Tk import |
| Installed CLI/version | PASS — `0.1.0b1` |
| Installed normal/Unicode demos | PASS — all 12 files byte-identical |
| Fresh `[serial]` install | PASS — pyserial extra resolved |
| Serial smoke | PASS — injected `SYNTHETIC_PORT` only; no OS discovery/open/write |
| Manifest privacy | PASS — no absolute path, username, credential field, physical port, or raw frame |
| Hosted matrix | PASS — Windows/Ubuntu × Python 3.10/3.12/3.14 plus quality/candidate jobs |

## Local and hosted candidate identities

The following ignored local files and the downloaded hosted files matched in
name, size, and SHA-256. These are Step 4 checkpoint artifacts, not a final
Step 7 audited tester bundle.

| Artifact | Size | SHA-256 |
|---|---:|---|
| `mixed_signal_afe_validation_platform-0.1.0b1-py3-none-any.whl` | 246,844 bytes | `a79a521b4a6c2be78fff61d07f7ede42f7202c2bb75c61a6332e704eb88e11b8` |
| `mixed_signal_afe_validation_platform-0.1.0b1.tar.gz` | 449,358 bytes | `a5a10b38c6a6cdb821052ec993a00edf2f0e7648cfd8fa06e046f8c5107e99e8` |
| `release-manifest.json` | 4,938 bytes | `8a79824e64052d199b56f59bf0194e2579657a7ec4db8f06a058eac72e8ee64c` |

The manifest also freezes these installed-demo identities:

- canonical result SHA-256:
  `0760fc55f71b04c8fc97b4730f35d82039566f5ca7db337214e91411ed51f9c9`;
- complete 12-file tree SHA-256:
  `349b8b74fb1305de2195f15aa92bed594abba54fdef136e446e47a784a25cefd`;
- demo manifest SHA-256:
  `3cc905c2df3ac9b1c2d12b0d2c68a644244ceb69db7c968c843d7f4180ec41b5`.

## Manifest evidence boundary

The candidate manifest records source commit/timestamp, package version,
Python/platform, gate statuses, artifact hashes, base/serial dependency
boundaries, and installed-demo hashes. Its hardware section explicitly records:

- evidence sources: `HOST_TEST`, `SYNTHETIC`;
- hardware claim: `NO_NEW_HARDWARE_VALIDATION`;
- AFE bench requirements verified: `0`;
- physical ports enumerated/opened: `0/0`;
- application bytes written: `0`;
- physical hardware operations: `NOT_RUN`.

The manifest deliberately excludes the output directory, local username,
email, credentials, USB identity, physical port name, and raw serial content.

## Diagnostic history retained

| Attempt | Result | Engineering finding |
|---|---|---|
| Raw two-build experiment | FAIL for raw sdist only | Extracted content was identical; current-time gzip/tar metadata was nondeterministic |
| First full verifier attempt | ABORTED; no candidate | Newly installed Windows console launcher did not start once; an immediate isolated rerun passed |
| Second full verifier attempt | ABORTED; no candidate | All gates passed, then a duplicated staging name exceeded the legacy Windows path limit before publication |
| Final local attempt | PASS | Console launch has bounded retry only for transient OS launch errors; staging uses a short same-parent name and preflights path length |
| Hosted run `33447031789` | PASS | All compatibility/quality jobs and the same deterministic candidate verifier passed |

The two aborted attempts created no output candidate and no PASS manifest.
Nonzero CLI exits, test failures, build differences, privacy failures, and
repeated launch failures remain hard failures; they are not retried into PASS.

## Safety and publication boundary

No port was enumerated or opened, and the connected MSP430 was not read, reset,
flashed, or written. No AFE, ADC, DAC, comparator, breadboard, supply, DMM,
oscilloscope, or signal generator was used. No merge, tag, Release, visibility
change, license selection, PyPI upload, or LinkedIn action was performed.

## Next checkpoint

Step 5 creates the beginner installation guide, private-beta testing guide,
troubleshooting guide, known-limitations/checklist material, and privacy-safe
bug/test-feedback templates. Real serial use remains optional and off by
default; the future AFE hardware phase remains a separately gated second part
of this product, while the MSP430 controller remains an independent peer.
