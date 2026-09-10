# TD-040A core batch and CLI acceptance

**Date:** 2026-09-07<br>
**Evidence:** `HOST_TEST`, with product outputs labeled `SYNTHETIC`<br>
**Hardware access:** none<br>
**Serial discovery/open:** none<br>
**Hardware validation claim:** none

## Scope

TD-040A adds a shared core contract for sequential batch progress and
cooperative cancellation, publishes `validation-run-manifest.v2`, and connects
the behavior to the CLI. It does not connect the Dashboard, persist raw
READ/LIVE observations, add trace overlays, sign manifests, access hardware, or
change another repository.

## Frozen execution semantics

- `COMPLETE`: all project presets were planned and every worker plus cleanup
  reached a terminal state.
- `PARTIAL`: an intentional strict subset was planned and every selected worker
  plus cleanup reached a terminal state.
- `CANCELLED`: cancellation was accepted; the current worker completed cleanup,
  later presets did not start, and completed terminal records were retained.
- `ERROR`: execution or cleanup failed; the failed terminal record was retained
  and later presets did not start.

The progress contract reports current preset ID, one-based preset number, total
planned presets, completed terminal-record count, and the phase `PREPARING`,
`RUNNING`, `CANCELLING`, `FINALIZING`, or `FINISHED`. A completed count changes
only after worker cleanup and terminal publication.

## Manifest compatibility and integrity

New runs write `validation-run-manifest.v2` with ordered planned and not-started
preset IDs plus explicit counts. The strict v1 parser and exact v1 serialization
shape remain available. Loading v1 does not rewrite the source artifact.

Create-new destinations, staging plus atomic rename, no-overwrite behavior,
project snapshot/configuration/artifact SHA-256 validation, bounded inputs, and
offline Simulator/CSV-only project restrictions remain enforced. SHA-256 is an
integrity check, not author authentication.

## Test-first record

The first new-test run failed during collection because the new public v2
symbols did not exist. After the minimal implementation, 122 tests passed and
three failed: two old assertions depended on prior error text/summary shape, and
one lineage mutation was rejected earlier by the new planned-order invariant.
The fixes retained recognizable legacy error meaning, updated exact v2 counts,
and exercised both planned-list and snapshot lineage checks.

The first public-golden run then failed in five expected sections: module
exports, schema versions, dataclass fields, signatures, and serialized fields.
The reviewed generator updated those sections after adding the legacy v1
constant, batch enums, progress type, cancellation token, and callback shapes.

The first full coverage run passed all 2,598 tests but reached 99.76% because
new defensive branches were not yet exercised. Added malformed progress,
manifest-state, compatibility, callback, lineage, CLI presentation, and exit
precedence tests brought the final gate to 100% without deleting guards.

## Final verification

| Gate | Result |
|---|---|
| Focused cancel/cleanup/v1-v2 composite | PASS — 11 passed |
| Full pytest with package statement coverage | PASS — 2,620 passed; 15,555/15,555; 100.00% |
| Phase 5 public API golden | PASS — 15 passed |
| Ruff | PASS |
| mypy | PASS — 225 source files |
| `pip check` | PASS |
| `git diff --check` | PASS |

The real CLI Simulator acceptance created a fresh six-preset project and run.
It returned `COMPLETE`, planned/completed 6/6, zero not-started presets, one
parseable JSON document on stdout, and progress only on stderr. History loaded
the saved manifest. A second run aimed at the same directory returned exit 5;
the original manifest SHA-256 remained unchanged.

Controlled CLI/core tests covered cancellation before the first preset,
between presets, during the active worker, and at the worker-finish boundary.
They also covered cleanup failure, retained records, explicit not-started IDs,
exit 130 for cancellation, exit 5 for cleanup error, and strict v1 round trip.

## Remaining work

TD-040B should connect the existing progress and cancellation contracts to the
Dashboard, including button state, close behavior, history refresh, and real Tk
automation. Raw READ/LIVE persistence, trace overlays, signatures, scheduling,
and hardware work remain separate later increments.
