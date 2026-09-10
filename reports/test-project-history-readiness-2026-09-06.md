# Test Project and Run-History Readiness — 2026-09-06

## Decision

The local project/preset/batch/history/comparison increment is functionally
complete for public API and CLI use and has passed its current-source local
test, static, dependency, build, and clean-install gates. This report does not
approve a commit, push, merge, tag, Release, hardware operation, or public
claim.

## Delivered product chain

- Strict versioned local project and preset documents.
- Six-preset Simulator starter project covering read, DC, hysteresis,
  calibration, amplitude-frequency response, and finite live monitoring.
- Explicit all-or-selected sequential offline batch execution.
- Create-new run directories with exact project snapshots, per-preset
  configuration identities, finalized result/coefficient artifacts, and a
  versioned run manifest.
- Explicit verified-history loading with no recursive directory discovery.
- Pure two-run comparison of copied outcomes and numeric metrics; no PASS/FAIL
  recalculation.
- Installed `analog-validation project create|inspect|run|history|compare`
  commands with human and JSON views.
- Public API and compatibility-golden coverage.

## Verification completed before final gate

- Project/API/CLI focused tests: 67 passed.
- Phase 5 public compatibility golden: 15 passed.
- Full regression and coverage: 2,575 passed; 14,913/14,913 package statements
  covered (100%).
- Editable-install CLI smoke: create, inspect, six-preset run, selected
  two-preset run, two-manifest history, and comparison all returned success.
- The complete run produced seven files; the selected DC/frequency run produced
  four. Both declared no Serial/device access and no hardware validation.

- Full Ruff: PASS.
- mypy: PASS across 221 source files.
- Dependency consistency: `pip check` PASS.
- Product-quality acceptance: 15/15 PASS. On this Windows/Python 3.12 host,
  10,000-record Replay completed in 0.683011 seconds with 13.102 MiB peak traced
  memory; the 10,000-point live stress completed in 0.284917 seconds with 1.355
  MiB peak traced memory. These are host usability observations, not real-time
  guarantees.
- Isolated wheel/sdist build from the current source tree: PASS.
- Fresh repository-external base-wheel installation: PASS; public project API,
  installed `pip check`, create, inspect, all-six run, selected-two run, history,
  and compare all succeeded.
- Formal commit-bound release candidate/audit and hosted CI: NOT RUN because
  this tree is intentionally uncommitted and no push was authorized.

## Defensive behavior exercised

Tests reject duplicate JSON keys, unsupported versions, NaN/Infinity, NUL,
invalid UTF-8, unsafe IDs, oversize documents/lists, duplicate presets/history
paths, unknown preset selections, mixed projects, persisted Serial settings,
replay path escape, existing destinations, staging failures, inconsistent
summaries, missing artifacts, SHA-256 mismatches, project-ID/snapshot mismatch,
unknown manifest presets, and configuration-hash/snapshot mismatch. Failure
paths do not leave a published run directory.

## Evidence boundary

All new execution evidence is `SYNTHETIC`, `CSV_REPLAY`, or `HOST_TEST`. The
project format refuses Serial settings, the tested starter uses Simulator only,
and no port discovery or physical device access occurred. No AFE gain, cutoff,
calibration accuracy, hysteresis, wiring, safety, or reliability claim is added.

SHA-256 detects artifact changes relative to the manifest but is not a digital
signature. Read/live run history currently records summaries rather than raw
observation streams. Dashboard project/history editing and visualization remain
future work.
