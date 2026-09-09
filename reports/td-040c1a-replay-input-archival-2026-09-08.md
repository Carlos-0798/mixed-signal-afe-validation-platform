# TD-040C1A Replay Input Archival Acceptance

**Date:** 2026-09-08<br>
**Evidence:** `HOST_TEST` / `CSV_REPLAY`<br>
**Hardware validation:** `NO_NEW_HARDWARE_VALIDATION`

## Decision

TD-040C1A is locally complete. A new offline project run now preserves the exact
CSV Replay bytes used by each executed preset, so verified history no longer
depends on the original project-side file remaining unchanged or present.

This checkpoint did not enumerate or open a serial port, access an MSP430, AFE,
or instrument, add Dashboard controls, persist READ/LIVE output observations,
add curve overlays, sign a manifest, or publish software.

## Frozen contract

- New runs publish `validation-run-manifest.v3`; strict v1 and v2 documents keep
  their original accepted fields and serialization shapes.
- `validation-run-input-artifact.v1` records preset ID, `CSV_REPLAY`, one safe
  `inputs/NN-preset.csv` path, exact byte count, and SHA-256.
- The source is copied into create-new staging before prepare, and the worker
  consumes that staged copy. The hash therefore describes the bytes actually
  offered to the Replay parser and adapter.
- Multiple executed presets resolving to one source retain separate manifest
  records but share one physical archived file.
- A preset cancelled before start is not opened or archived. Completed records
  and their inputs remain; later preset IDs stay explicitly not started.
- Missing, non-file, unreadable, oversized, or unwritable input fails closed.
  Staging is removed and no output directory is published.
- History verifies that every input stays inside its run directory and still
  matches its recorded size and SHA-256. SHA-256 is integrity, not identity or
  authorship authentication.

## Red tests and fixes

The intended first red test failed at import because the new v2 compatibility
constant did not yet exist. After the minimum implementation, fixture assertions
exposed six expected shape updates: v3 summary count, v1 field stripping, and
the staging-path expectation. The focused set then passed 81 tests.

The CLI-focused run next exposed one old expected summary without the v3 input
count, and Ruff exposed import/order simplifications. Those were corrected
without changing runtime semantics. A later negative test initially called a
test helper with an unsupported keyword; it was repaired to construct the
invalid immutable value with `dataclasses.replace`.

The first full repository gate was deliberately retained as a failed result:
1 failed and 2,707 passed, with 16,321/16,325 statements covered (99.98%). One
Dashboard comparison test had changed a Simulator record to `CSV_REPLAY` without
adding the now-required v3 input record. The product contract correctly rejected
that internally inconsistent fixture. Adding a valid input-artifact record and
the two new defensive CLI presentation cases resolved the failure.

## Final verification

| Gate | Result |
|---|---|
| Focused project/CLI/public-golden tests | PASS — 120 tests |
| Focused project module statement coverage | PASS — 1,042/1,042, 100.00% |
| Full pytest and package statement coverage | PASS — 2,708 tests; 16,325/16,325, 100.00% |
| Ruff | PASS — all repository paths |
| mypy | PASS — 218 source files |
| pip dependency consistency | PASS — no broken requirements |
| `git diff --check` | PASS — exit 0; Git emitted only its existing line-ending normalization warning for the generated API golden |
| Independent installed CLI chain | PASS — parseable JSON stdout, progress on stderr, manifest v3, per-preset references with one deduplicated file, human output, and history verification after source mutation |

The independent CLI artifacts were created in a new
`%TEMP%\avs-td040c1a-acceptance-*` directory.
They use a temporary copy of the strict Replay golden; the evidence remains
`CSV_REPLAY/HOST_TEST` and does not establish BENCH behavior.

## Remaining work

- READ/LIVE output-observation persistence remains separate TD-040C1 work.
- A one-click rerun from the archived input is not implemented; the bytes and
  integrity metadata are available for an explicit future workflow.
- Dashboard does not expose input-artifact details. Existing v3 histories still
  load through the shared manifest API and retain normal batch-state display.
- Curve overlays and manifest signing/authentication remain TD-040C2 and
  TD-040C3 respectively.

The next product increment should be selected from observed workflow friction.
TD-040C1B should begin only if users need READ/LIVE output replay or a direct
rerun action enough to justify another data and UI contract.
