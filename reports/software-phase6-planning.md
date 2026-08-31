# Software Phase 6 Planning Checkpoint

**Date:** 2026-08-31<br>
**Milestone:** release engineering and external-test delivery plan<br>
**Evidence class:** HOST_TEST planning record<br>
**Hardware used:** none<br>
**Implementation status:** Step 1 complete; 1 of 8 checkpoints

## Outcome

The Software Phase 6 implementation plan and Step 1 release contract are complete. They convert the broad
“packaging, CI, documentation, and v1.0” milestone into eight reviewable steps
with one earlier delivery point: private beta candidate `0.1.0b1` after Steps
1–7. Step 8 retains every merge, tag, GitHub Release, visibility, license, and
v1.0 decision for explicit owner review.

No runtime code, version, repository visibility, license, tag, Release, or
hardware state changed in this planning checkpoint.

## Confirmed entry baseline

- Software Phases 1–5 are complete at 8/8 each.
- The current package version is `0.1.0.dev0`.
- The final Phase 5 gate is 2,189 tests, zero skips, and 11,470/11,470 package
  statements.
- Ruff, 191-file mypy, dependency checks, isolated build, external base/serial
  installs, byte-identical demos, and real local Windows Tk smoke passed.
- The GitHub repository is Private and its default branch is `main`.
- No hosted workflow exists at Phase 6 entry.
- `LICENSE` states that no license has been selected and all rights are
  reserved.
- The Phase 5 Draft PR remains separate from this new
  `phase6/release-engineering` branch.
- Verified AFE hardware-performance claims remain zero.

## Frozen planning decisions

- use PEP 440 `0.1.0b1` for the first installable beta candidate and display it
  as `v0.1.0-beta.1` in release-facing prose;
- test representative minimum/primary/latest Python versions before broadening
  claims;
- keep hosted CI read-only and pin actions to reviewed full commit SHAs;
- make base and `[serial]` clean installs separate gates;
- never enumerate or open a real port in default CI/release verification;
- add a machine-readable, privacy-minimal release manifest;
- prove extension independence with a public-API-only external adapter;
- keep the repository Private and `All rights reserved` through beta
  preparation unless the owner decides otherwise;
- treat CI, package installation, simulator/demo, local Tk, physical UART, and
  future AFE bench evidence as distinct evidence classes;
- stop before merge/tag/Release/v1.0 and provide an exact owner preview.

## Reviewed action versions

The planning audit checked the official GitHub release records on 2026-08-31.
Implementation will pin these reviewed commits rather than floating tags:

| Action release | Commit |
|---|---|
| `actions/checkout@v7.0.1` | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| `actions/setup-python@v7.0.0` | `5fda3b95a4ea91299a34e894583c3862153e4b97` |
| `actions/upload-artifact@v7.0.1` | `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` |

The workflow will use only actions needed for checkout, Python setup, and
bounded artifact upload. It will not contain a publication token or release
job.

## Safety and evidence boundary

Planning used repository files, Git metadata, and official GitHub action/repo
metadata only. It did not enumerate or open a COM port; operate the connected
MSP430; access an AFE, instrument, supply, breadboard, or laboratory resource;
or create synthetic results that could be confused with physical measurements.

## Next checkpoint

Software Phase 6 Step 2 will add the minimal-permission hosted CI workflow and
executable repository checks. The first push will be reviewed as CI evidence;
it will not publish a package or Release.
