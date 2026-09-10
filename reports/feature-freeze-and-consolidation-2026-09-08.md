# Feature Freeze and Consolidation Acceptance

**Date:** 2026-09-08<br>
**Evidence:** `HOST_TEST`, deterministic `SYNTHETIC`, and bounded `CSV_REPLAY`<br>
**Hardware validation:** `NO_NEW_HARDWARE_VALIDATION`

## Outcome

Analog Validation Studio `0.1.0b1` has entered local feature freeze. The current
uncommitted product was copied as 466 tracked/untracked non-ignored source files
to a new directory outside the worktree, built, installed, and exercised without
using a repository import path. No runtime blocker was found. The feature-freeze
policy is documented in `docs/FEATURE_FREEZE.md`; this is not a release decision.

## Source and safety boundary

- Branch: `codex/calibration-workflow`.
- HEAD: `bf8c4c6f59ba9063524aea7db01df87d35170483`.
- Build source: a repository-external snapshot of the complete current
  non-ignored file set, including the uncommitted product modules.
- Runtime sources: deterministic Simulator and one temporary strict CSV Replay.
- No serial-port discovery/open, device command, MSP430/AFE access, or laboratory
  instrument access occurred.
- No commit, push, PR, merge, tag, Release, package publication, visibility,
  license, or history action occurred.

## Build and clean-install evidence

The first `python -m build --no-isolation` attempt stopped before source build
because the project development environment intentionally did not contain
`setuptools.build_meta`. The retry used build's standard isolated environment,
which provisioned its declared `setuptools>=77` backend and completed both
artifacts. No dependency was added to the project environment.

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| `mixed_signal_afe_validation_platform-0.1.0b1-py3-none-any.whl` | 338,338 | `50673dba29e3b0b0dc4a0f4ee458793b7c951e6c67942fbe42367656babee26e` |
| `mixed_signal_afe_validation_platform-0.1.0b1.tar.gz` | 946,794 | `9bcdd46f07ebed748d6b620a13e8b1bbf2dbeed8d611b106bc1d942fe04dba8b` |

The wheel contains 102 entries, including the project/history service and
Dashboard project workspace. It was installed into a fresh environment with
`--no-index --no-deps`. An isolated import resolved to that environment's
`site-packages`, and installed `analog-validation version --json` returned
`product-cli-output.v2` with software version `0.1.0b1`.

## Installed workflow acceptance

Two installed `demo --json` runs used separate new destinations, one with a
normal name and one with a Unicode name. Both exited 0, each produced 12 files,
and every relative path and file SHA-256 matched. JSON remained parseable and
stderr was empty.

An installed one-preset Replay project then exercised the product path:

- run exit 0 with progress on stderr and no progress text on JSON stdout;
- `validation-run-manifest.v3`, batch `COMPLETE`, evidence `CSV_REPLAY`;
- one input artifact archived as `inputs/01-replay-read.csv`;
- archived bytes matched the original input SHA-256
  `6b9e43a84c0d74c8c19050f94b1bc8ea6c819bf930d08a0d3aa7e46cfb1bf842`;
- after the project-side source CSV was changed, manifest loading and installed
  `project history --json` still passed from the archived bytes.

This proves package/install and bounded software behavior only. It does not
prove sensor, ADC/DAC, AFE, bandwidth, noise, timing, wiring, or controller
behavior.

## Quality and privacy checks

The first post-documentation full regression had one failure: an architecture
test requires the README to retain the exact phrase `7/8 checkpoints`, while the
initial freeze wording said only that Phase 6 remained 7/8. The wording was
corrected without changing the frozen 7/8 status or any runtime behavior. The
focused contract test and then the complete gate were rerun.

| Gate | Result |
|---|---|
| Final full pytest and package statement coverage | PASS — 2,709 tests; 16,356/16,356, 100.00% |
| Ruff | PASS — all repository paths |
| mypy | PASS — 227 source files |
| pip dependency consistency | PASS — no broken requirements |
| Product-quality acceptance | PASS — 15/15 checks |
| 10,000-record Replay parse | PASS — 0.561206 s, 13.102 MiB traced peak |
| 10,000-point live publication | PASS — 0.197072 s, 1.332 MiB traced peak, bounded at 2,048 retained |
| Deterministic demo publication | PASS — 0.029117 s, 12 artifacts, `SYNTHETIC` |
| Current-path privacy scan | PASS after replacing one historical local temp path with `%TEMP%` notation |

Wall-clock values describe this Windows host and are not real-time guarantees.
The product-quality run was in-process `HOST_TEST`/`SYNTHETIC`; it opened no
serial port and measured no hardware.

## Deferred work and next decision

Archived-input rerun, READ/LIVE observation artifacts, curve overlays, manifest
authentication, multi-user/cloud functions, UI runtime migration, physical
serial soak, and AFE bench validation remain deferred. They do not block the
current software demonstration and should resume only from observed need or an
explicit new phase.

## Working-tree preservation audit

The freeze began from a 466-file SHA-256 map of every tracked or untracked
non-ignored file. The final map contains 468 files. No baseline file was removed.
Only seven existing documentation/report files changed, and the two additions
are this report and `docs/FEATURE_FREEZE.md`; no runtime or test file changed
during the freeze stage.

Final Git status is 50 modified and 39 untracked files, 89 total, with 0 staged,
0 deleted, and 0 renamed. These totals include all previously completed
uncommitted product work. Branch and HEAD remain unchanged.

The next safe action is owner review of the frozen uncommitted diff and a commit
grouping proposal. Software Phase 6 Step 8 and every public action still require
separate explicit owner authorization.
