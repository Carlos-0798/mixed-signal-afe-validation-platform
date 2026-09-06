# Calibration, Frequency Response, and Live Monitor Precommit Review

Date: 2026-09-06  
Branch: `codex/calibration-workflow`  
Committed base inspected: `158e752`  
Review state: local uncommitted source tree; not a release candidate

## Outcome

The combined calibration, amplitude-frequency response, and bounded live-monitor
increment passed its local precommit review after two defensive code corrections
and one user-facing contract clarification. The three workflows remain separate
product features built on the same public adapter, workflow, worker, evidence,
result, CLI, Dashboard, and reporting layers. No source-level dependency on the
independent MSP430 project was introduced.

This review does not authorize or claim a commit, push, hosted CI run, tag,
Release, package publication, serial session, instrument session, or physical
AFE validation.

## Defensive findings closed

1. **Pause/finish race presentation** — a final live-monitor snapshot could
   retain a stale paused flag when acquisition had already become inactive. The
   presenter now gives the terminal state precedence, labels the view
   `finished`, and disables both Pause and Resume. A regression test covers the
   inactive-plus-paused snapshot explicitly.
2. **Finite extreme-frequency overflow** — the deterministic single-pole model
   previously squared finite frequency values directly. Inputs near `1e200 Hz`
   could therefore raise `OverflowError` even though the request passed the
   finite-number contract. The equivalent attenuation calculation now operates
   in the logarithmic domain. A regression test spans `1e-200 Hz` to `1e200 Hz`
   and verifies finite positive output without changing ordinary-range results.
3. **Frequency-data completeness wording** — v1 intentionally refuses to
   publish a cutoff when any requested point is excluded. The review screen and
   engineering documentation now state that at least 10 points are required and
   every requested point must be usable and strictly increasing. The analysis
   continues to retain decisions and `usable-points:n/total` evidence instead of
   inventing a cutoff.

## Architecture and safety review

- Calibration fits observed/reference pairs from one declared product evidence
  source, evaluates before/after error, exports a finalized `TestRun`, and saves
  a create-new versioned coefficient file. Loading a coefficient file validates
  and displays it; it does not silently apply values or write firmware.
- Frequency response acquires explicit frequency/input/output triples, preserves
  all three record references, computes amplitude ratio and gain in dB, and
  publishes a cutoff only under the reviewed completeness and unique-crossing
  rules. Simulator model cutoff and acceptance target remain independent.
- Live monitoring is finite and presentation-only. The ring buffer, time window,
  quality totals, pause/resume checkpoints, and eviction counts are bounded. It
  produces no engineering PASS/FAIL and no analysis export.
- Simulator and CSV Replay remain offline sources. Serial live monitoring is not
  in the product catalog. The clean serial-extra install used an injected host
  substitute and did not enumerate or open a physical port.
- Artifact destinations remain explicit create-new paths. Presentation layers do
  not recalculate engineering conclusions or promote evidence classes.

## Executed local evidence

| Gate | Actual result |
|---|---|
| Focused regression after fixes | PASS — 44 tests |
| Full pytest and package statement coverage | PASS — 2,459 tests; 13,834/13,834 statements; 100% |
| Ruff | PASS — `src`, `tools`, `tests`, and public adapter example |
| mypy | PASS — 218 source files |
| Development dependency consistency | PASS — no broken requirements |
| Product-quality acceptance | PASS — 15/15 checks |
| 10,000-record Replay bound | PASS — 0.495200 s; 13.102 MiB traced peak |
| 10,000-point live bound | PASS — 0.177198 s; 1.348 MiB traced peak; 2,048 retained; 7,952 evicted |
| Real Windows Tk accessibility smoke | PASS — 3/3 at scaling 1.0, 1.5, and 2.0 |
| Markdown relative-link check | PASS — 138 files; 175 links; 0 broken |
| Repeated source-tree build | PASS — two byte-identical wheel/sdist builds after deterministic sdist normalization |
| Fresh base-wheel install | PASS — no runtime dependencies; headless import; installed CLI/demo/public adapter |
| Fresh `[serial]` install | PASS — injected `SYNTHETIC_PORT`; discovery/open/write against physical ports all false |
| Hosted CI | NOT RUN — increment is not pushed |
| Formal commit-bound release candidate/audit | NOT RUN — clean committed source identity is required |
| Physical controller, AFE, or instrument test | NOT RUN |

The repeated working-tree builds produced:

- wheel: 285,555 bytes,
  `c67b48fdff6c42552ad4a18abcf8db213f842e82da9e0e01d540f28d835f9bac`;
- normalized sdist: 780,402 bytes,
  `c1d8db3083d5287abeb27f5cebe84c59fc1a8104a694c8d63188c58fb299f6f6`.

These hashes identify the reviewed uncommitted source-tree build only. They are
not release identities and must not be substituted for the later clean-commit
candidate manifest.

## Evidence boundary and remaining work

All newly executed acquisition evidence was `SYNTHETIC`, `CSV_REPLAY`, or
`HOST_TEST`. Test coverage describes executed software statements; it does not
prove electrical safety, wiring, calibration accuracy, bandwidth, instrument
accuracy, timing determinism, or long-duration reliability.

Remaining product work includes the separately gated real-device closure:
versioned protocol identity/handshake, disconnect and reconnect tests, sustained
soak and memory checks, and later read-only serial acquisition after an explicit
port and wiring approval. Physical calibration and frequency-response closure
also require a reviewed fixture, reference instrument, stimulus source, safe
limits, and bench evidence. Phase response, raw-waveform/FFT analysis, automated
instrument control, and applying coefficients to hardware are not implemented.

## Next governance gate

The next step is owner review and explicit approval of one combined local commit.
Only after the tree has a clean committed identity can the formal
release-candidate and release-audit tools run. Push, hosted CI, Ready/merge, tags,
Release creation, package publication, and hardware access remain separate
approval events.
