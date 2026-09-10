# Frequency-Response Product Workflow Verification

**Date:** 2026-09-05  
**Milestone:** Post-beta amplitude-response product closure  
**Evidence class:** HOST_TEST / SYNTHETIC / CSV_REPLAY  
**Hardware used:** none  
**Repository state:** local `codex/calibration-workflow` worktree; not committed,
not pushed, not merged, not released

## Outcome

The existing offline amplitude-response math is now connected to one complete
product workflow. Simulator and CSV Replay supply explicit frequency, input
amplitude, and output amplitude records; the shared compiler and bounded worker
run a dedicated frequency-response service; versioned criteria produce a
provenance-consistent `TestRunResult`; and the same finalized evaluation feeds
machine exports, the CLI, Dashboard, and human reports.

This closes the host-software amplitude-response workflow. It does not produce
or sample a physical waveform, estimate phase, run an FFT, control an
instrument, measure an AFE, or prove physical bandwidth.

## Delivered capability

- `frequency-response-criteria.v1` and
  `frequency-response-evaluation.v1` evaluate estimated cutoff relative to an
  independently reviewed target and enforce a minimum included-point count.
- The deterministic Simulator model cutoff is separate from the target cutoff;
  changing one cannot silently rewrite the other.
- Product `FREQUENCY_RESPONSE_ANALYSIS` compiles three bounded analog reads and
  supports deterministic Simulator and strict CSV Replay sources.
- The Simulator uses a bounded logarithmic frequency grid and a deterministic
  single-pole amplitude model. Each point has three distinct record references.
- `result-export.v1` preserves criteria, amplitude ratio, gain dB, target/drop/
  cutoff metrics, quality decisions, limitations, and all frequency/input/output
  record and raw-record lineage.
- CLI paths include `simulate frequency` and `replay frequency`. The Dashboard
  exposes dedicated frequency range, model cutoff, target cutoff, target drop,
  tolerance, and minimum-point controls.
- Human reports copy finalized gain/cutoff values into a deterministic SVG whose
  x-axis is logarithmic. Presentation does not recalculate the cutoff or outcome.
- Phase 3 and Phase 5 public compatibility goldens freeze the additive schemas,
  imports, call shapes, CLI paths, and serialized result identity.

## Functional acceptance

| Scenario | Actual result |
|---|---|
| Default deterministic model and target at 1000 Hz | `PASS`; estimated cutoff 1000 Hz |
| Model at 2000 Hz, target at 1000 Hz, tolerance 5% | Engineering `FAIL` / CLI exit 1; estimated cutoff 1948.0148061417415 Hz |
| Evidence source | `SYNTHETIC` for Simulator; `CSV_REPLAY` for replay |
| Point lineage | Three distinct frequency/input/output references retained per point |
| Physical I/O | Not used; no serial discovery/open/write and no instrument control |

The deliberate mismatch is a successful product test of acceptance behavior,
not a software crash. The estimated 1948.0148061417415 Hz value reflects
interpolation across the bounded logarithmic sample grid; it is not a measured
component cutoff.

## Executed verification

| Gate | Actual result |
|---|---|
| Focused frequency/criteria/service/Dashboard regression | PASS — 114 tests |
| Public compatibility/model regression | PASS — 102 tests |
| Full pytest and package statement coverage | PASS — 2,375 tests; 13,133/13,133 statements; 100% |
| Full Ruff and mypy | PASS — Ruff on `src`/`tools`/`tests`/public adapter; mypy on 214 files |
| Development dependency consistency | PASS — no broken requirements |
| Product-quality acceptance | PASS — 10/10 checks; 10,000-record Replay 0.504480 s and 13.102 MiB peak on this host |
| Repeated isolated build and fresh installs | PASS — two byte-identical wheel/normalized-sdist builds; base and `[serial]` installs; injected serial substitute only |
| Installed frequency CLI/report chain | PASS — exact default PASS, intentional engineering FAIL/exit 1, and five report artifacts |
| Clean-install environment isolation | PASS — inherited `PYTHONPATH` is scrubbed and unit-tested so pip must install the candidate wheel |
| Hosted CI | NOT RUN — local increment is not pushed |
| Formal commit-bound release candidate/audit | NOT RUN — a clean committed source identity is required |
| Physical AFE or instrument test | NOT RUN |

## Safety and compatibility conclusions

- The workflow remains controller-neutral. No MSP430 implementation is imported
  into frequency-response math or the product service.
- A future MSP430, standalone acquisition board, or SCPI instrument can
  integrate through versioned public adapters and explicit artifacts without
  making this project subordinate to another project.
- CSV Replay creates a new `CSV_REPLAY` observation context and does not
  authenticate historical physical measurements.
- The current workflow is read-only at the product boundary. A physical sweep
  that drives a waveform source requires a separate capability/safe-range/
  shutdown design and explicit authorization.

## Remaining limitations and next feature

- No phase response, complex transfer function, uncertainty propagation,
  multi-channel synchronization, live waveform view, FFT, signal-generator
  adapter, oscilloscope adapter, or SCPI/PyVISA instrument control exists.
- No physical AFE, reference source, DMM, oscilloscope, function generator, or
  school laboratory resource was used.
- The bounded offline live-monitor/curve increment was subsequently implemented
  in this same uncommitted branch and has its own verification report. Physical
  frequency sweeps remain a later separately authorized evidence path.
