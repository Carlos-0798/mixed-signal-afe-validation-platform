# Bounded Live-Monitor Product Workflow Verification

> Historical feature-stage snapshot: the later combined precommit review in
> `calibration-frequency-live-precommit-review-2026-09-06.md` supersedes the
> aggregate test counts, timings, and working-tree build hashes below. They are
> retained here as the evidence recorded when this individual feature closed.

**Date:** 2026-09-05  
**Milestone:** Post-beta bounded offline live-monitor closure  
**Evidence class:** HOST_TEST / SYNTHETIC / CSV_REPLAY  
**Hardware used:** none  
**Repository state:** local `codex/calibration-workflow` worktree; not committed,
not pushed, not merged, not released

## Outcome

Analog Validation Studio now has one finite live-observation workflow that is
usable without hardware. Simulator and strict CSV Replay measurements move
through a compatible public streaming-read API, the reviewed product compiler,
the bounded single-owner worker, a versioned in-memory monitor session, CLI
human/JSON views, and the Dashboard Results page.

This closes the offline software workflow for bounded live curves. It does not
open a serial port, operate an MSP430, sample a physical waveform, prove timing,
or validate an analog front end. A live-monitor completion deliberately has no
engineering PASS/FAIL and produces no analysis export.

## Delivered capability

- `run_streaming_read_workflow` reads equal-length channels in sample-major
  cycles while preserving the existing capability, lifecycle, evidence, early
  EOF, and deterministic cleanup semantics.
- `live-monitor.v1` freezes immutable trace points and snapshots containing
  total/retained/evicted counts, pause state/count, presentation time window,
  and VALID/SUSPECT/INVALID totals.
- `LiveMonitorSession` owns a thread-safe ring buffer, cooperative pause/resume
  checkpoints, bounded interval waits, and an adjustable trailing display
  window. Acquisition and presentation limits remain separate.
- Product requests allow at most 55 seconds of requested interactive duration,
  10,000 total measurements, and 10,000 retained points; the default retained
  limit is 2,048. A job always terminates.
- Product `LIVE_MONITOR` is available only for Simulator and strict CSV Replay.
  Serial is rejected by the catalog/compiler before an adapter can be opened.
- CLI paths include `simulate monitor` and `replay monitor`, with explicit cycle,
  cadence, channel, time-window, and ring-buffer limits.
- The Dashboard provides a bounded multi-channel curve, observation table,
  status/quality/eviction/event-drop text, cooperative pause/resume, and a
  presentation-only time-window selector.
- Phase 2 and Phase 5 compatibility manifests freeze the additive streaming
  function, live schemas/dataclasses/signatures/constants, and both CLI paths.

## Safety and resource invariants

| Invariant | Enforced behavior |
|---|---|
| Finite work | Requested duration <= 55 seconds and total measurements <= 10,000 |
| Memory-bound display | Oldest retained trace point is evicted when the selected ring limit is exceeded |
| Honest counters | Ring eviction, worker-event drops, and invalid/suspect measurements are reported separately |
| Pause semantics | Pause is cooperative at bounded checkpoints; resume wakes the worker; cleanup resumes before close |
| Outcome semantics | Product status can complete, but engineering outcome remains `none` |
| Output authority | No device command, output channel drive, analysis export, or automatic file write is added |
| Source boundary | Only `SYNTHETIC` and `CSV_REPLAY`; no source is promoted to bench evidence |

Multi-channel values are read sequentially within one logical cycle. They are
not simultaneous samples and cannot support a phase, skew, or synchronization
claim.

## Functional acceptance

| Scenario | Actual result |
|---|---|
| Installed Simulator, 5 cycles x 3 channels, ring limit 3 | `COMPLETED`; 15 total, 3 retained, 12 evicted; engineering outcome `none` |
| Installed CSV Replay, 1 cycle x 3 channels, ring limit 3 | `COMPLETED`; 3 total, 3 retained, 0 evicted; `CSV_REPLAY`; outcome `none` |
| 10,000-point in-process live stress, retained limit 2,048 | 0.183188 s; 1.331 MiB peak traced memory; 2,048 retained; 7,952 evicted |
| Time-window check in the same stress | 1,001 newest points visible in the selected 1-second window |
| Real Windows Tk accessibility smoke | 3/3 passed at scaling 1.0, 1.5, and 2.0 with focus traversal |
| Physical I/O | Not used; serial discovery/open/write and instrument control were not performed |

The timings describe this CPython 3.12.10/Windows 11 AMD64 host run. They are
regression guards, not throughput marketing figures, deadline guarantees, or
physical sample-rate measurements.

## Executed verification

| Gate | Actual result |
|---|---|
| Full pytest and package statement coverage | PASS — 2,458 tests; 13,825/13,825 statements; 100% |
| Full Ruff and mypy | PASS — Ruff on the complete repository; mypy on 217 source files |
| Development dependency consistency | PASS — no broken requirements |
| Product-quality acceptance | PASS — 15/15 checks, including 10,000-point live stress |
| Repeated isolated build | PASS — wheel and normalized sdist byte-identical across two builds |
| Fresh base install | PASS — no runtime dependencies; headless import, version, demo, and public adapter |
| Fresh `[serial]` install | PASS — injected host substitute only; physical discovery/open/write all false |
| Installed live CLI | PASS — Simulator and CSV Replay monitor JSON checked from the built wheel |
| Built wheel identity | 285,222 bytes; `da8a532750b6f64f7bd159b6be010c8616021115c73c85fb36557a3b3cb3930a` |
| Built normalized sdist identity | 779,667 bytes; `a9bbb18ae56b13e1ff8badc3865d72afc9e491f615547762d2db0ecfa18160de` |
| Hosted CI | NOT RUN — local increment is not pushed |
| Formal commit-bound release candidate/audit | NOT RUN — a clean committed source identity is required |
| Physical AFE, controller, or instrument test | NOT RUN |

The temporary build/install environments were deleted after verification. The
hashes identify this uncommitted worktree build only and are not release IDs.

## Remaining limitations and next gate

- There is no infinite session, persistent history, background service, alarm,
  trigger, cursor, zoom, or live-result export.
- The final `ReadWorkflowResult` is finite and bounded to 10,000 measurements;
  the ring buffer bounds the displayed subset rather than authenticating a
  physical acquisition rate.
- Cooperative pause can react only at checkpoints; no OS scheduling latency or
  sub-cycle timing guarantee is claimed.
- Serial live monitoring, automatic reconnection, device identity handshake,
  data-gap policy, and 30-minute/2-hour soak evidence remain deferred.
- Before enabling a real source, the project needs a separately reviewed
  receive-only session contract, explicit device/profile identity, sample-rate
  and memory budgets, disconnect/reconnect tests, cleanup evidence, and owner
  authorization for the exact port and physical wiring.

The next code-governance step is an owner-approved combined commit review,
followed by the clean-commit release-candidate/audit gate. The next engineering
feature is the real-device closure design; physical execution remains a separate
approval and evidence event.
