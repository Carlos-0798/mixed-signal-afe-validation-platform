# Frozen Software Phase 2 Public API

**Compatibility manifest:** `phase2-public-api-golden.v1`

**Workflow behavior:** `phase2-workflow-golden.v1`

**Current manifest package version:** `0.1.0b1`
**Evidence:** HOST_TEST / SYNTHETIC / CSV_REPLAY

Software Phase 2 Step 8 freezes the software device and acquisition boundary before analysis runners are built on top of it. “Frozen” means accidental incompatible changes fail automated tests. It does not prohibit intentional evolution.

## What is frozen

`test-data/golden/phase2_public_api.json` records:

- exact public names exported by `analog_validation`, `.adapters`, `.replay`, and `.workflows`;
- capability, measurement, configuration, simulator, replay, adapter-config, TestRun, and workflow schema-version strings;
- lifecycle, simulator-fault, replay-channel, replay-timing, read-operation, and workflow-status enum values;
- required/default parameter shapes for the primary adapter and workflow entry points;
- stable adapter/replay error inheritance used by callers for recovery;
- SHA-256 hashes of the valid and invalid CSV Replay compatibility fixtures.

`test-data/golden/phase2_workflow_v1.json` records:

- one controller-neutral three-channel read request;
- exact default Simulator result meaning;
- exact CSV Replay result meaning, including `SATURATED` quality and forced `CSV_REPLAY` provenance;
- exact atomic `UNSUPPORTED` capability gaps for an empty replay adapter;
- host-only evidence metadata.

The reusable eight-check adapter contract separately freezes lifecycle, capability caching, typed read, provenance, error, shutdown, and reconnect behavior for reference, Simulator, and CSV Replay adapters.

The reviewed post-beta live-monitor addition extends this compatible boundary
with `run_streaming_read_workflow()`. It retains the same request/result,
capability preflight, evidence, incomplete-replay, and cleanup meanings while
adding optional per-cycle checkpoints, per-measurement observation, and an
injectable bounded interval wait. Existing `run_read_workflow()` behavior and
golden results are unchanged.

## Change policy

An intentional compatible addition may extend a future manifest after tests and documentation are updated. An intentional breaking change must:

1. introduce a new schema/profile/API version where serialized or behavioral meaning changes;
2. preserve the prior golden fixture when backward compatibility is promised;
3. add migration notes and new valid/invalid examples;
4. update public documentation and package smoke tests;
5. receive explicit review instead of regenerating golden files merely to make tests pass.

Internal implementation details that do not change public imports, typed models, adapter contract, workflow results, or frozen behavior may change without a new public version.

## Why hashes and exact outputs matter

A parser can continue to “pass tests” while a fixture is accidentally edited at the same time. Freezing the replay file hashes makes that edit visible. Likewise, checking only that a workflow returns three records would miss changed IDs, timestamps, provenance, units, quality flags, or missing-capability tokens. The exact golden result protects meaning, not just record count.

## Current boundary

This freeze covers only the Software Phase 2 host device/acquisition layer. It does not freeze future analysis-runner, report, CLI, Dashboard, serial-transport, firmware, or hardware APIs. The streaming callback and wait contract does not claim physical accuracy, electrical safety, hard-real-time timing, loss-free transport, or laboratory validation.

The current compatibility manifest records package `0.1.0b1`. Phase 3 and later
product workflows build analysis and evidence-aware TestRun results without
weakening these provenance and capability boundaries. Earlier reports retain
the historical `0.1.0.dev0` identity that was true when those checkpoints ran.
