# Calibration Product Workflow Verification

**Date:** 2026-09-05  
**Milestone:** Post-beta calibration product closure  
**Evidence class:** HOST_TEST / SYNTHETIC / CSV_REPLAY  
**Hardware used:** none  
**Repository state:** local `codex/calibration-workflow` worktree; not committed,
not pushed, not merged, not released

## Outcome

The previously implemented linear-fit math is now connected to one complete
product workflow. Simulator and CSV Replay can supply observed/reference pairs;
the shared compiler and bounded worker run the calibration service; explicit
criteria produce a provenance-consistent `TestRunResult`; and the same finalized
evaluation feeds machine exports, the CLI, Dashboard, and human reports.

This closes the host-software calibration workflow. It does not calibrate an
assembled AFE, prove instrument accuracy, write coefficients to a controller,
or validate any physical signal path.

## Delivered capability

- `calibration-criteria.v1` and `calibration-evaluation.v1` evaluate
  after-calibration RMSE, mean absolute error, maximum absolute error, RMSE
  reduction, and included-point count.
- Product `CALIBRATION_ANALYSIS` compiles two bounded analog reads and supports
  deterministic Simulator and strict CSV Replay sources.
- `result-export.v1` preserves criteria, metrics, before/after error values,
  point decisions, record/raw-record lineage, provenance, and limitations.
- `calibration-coefficients.v1` saves one deterministic, bounded JSON artifact
  containing the linear mapping and exact observed/reference lineage.
- Coefficient files use create-new publication by default. Loading performs
  schema/domain validation and inspection only; it does not apply values to a
  measurement, change a reviewed run, access serial, or flash firmware.
- CLI paths include `simulate calibration`, `replay calibration`, and
  `coefficients inspect`; result and coefficient destinations remain separate.
- The Dashboard exposes calibration configuration, reviewed execution,
  separate result/coefficient save controls, existing-file validation, and
  explicit no-auto-apply text.
- Human reports copy finalized before/after signed errors into an SVG chart and
  never recalculate PASS/FAIL during presentation.
- Phase 3 and Phase 5 public compatibility goldens freeze the additive schemas,
  imports, signatures, command paths, and CLI output-version change.

## Executed verification

| Gate | Actual result |
|---|---|
| Full pytest and package statement coverage | PASS — 2,322 tests; 12,558/12,558 statements; 100% |
| Ruff | PASS — `src`, `tools`, `tests`, and public adapter example |
| mypy | PASS — 209 source, tool, test, and example files |
| Development dependency consistency | PASS — no broken requirements |
| Product-quality acceptance | PASS — 10/10 checks |
| 10,000-record Replay bound | PASS — 0.504951 s; 13.102 MiB peak on this Windows/Python 3.12 host |
| Repeated isolated build | PASS — wheel and normalized sdist were byte-identical across two builds |
| Fresh base install | PASS — no runtime dependency; headless import; installed version/demo/public adapter |
| Fresh `[serial]` install | PASS — injected host substitute only; no physical discovery/open/write |
| Installed calibration chain | PASS — Simulator calibration → result/coefficient save → validation-only coefficient load → five-artifact report |
| Hosted CI | NOT RUN — local increment is not pushed |
| Formal commit-bound release candidate/audit | NOT RUN — a clean committed source identity is required |
| Physical AFE or instrument test | NOT RUN |

The installed calibration smoke produced a `SYNTHETIC` engineering `PASS` with
the deterministic Simulator mapping `reference = 2 * observed + 12 mV`. That
number proves only the configured software model and product plumbing; it is
not a measured gain or offset.

## Safety and compatibility conclusions

- The public product remains controller-neutral. No MSP430 implementation is
  imported into the calibration math or product service.
- MSP430 and future devices can integrate through versioned public adapters,
  profiles, replay artifacts, or result/coefficient formats while remaining
  independent products.
- TestRun v1 intentionally requires observed and reference channels in one
  product run to share the current evidence source. The lower-level fit still
  retains both source fields for future calibrated bench workflows.
- Existing coefficient files cannot silently authorize an output action. A
  future apply/deploy workflow requires a separate design, capability review,
  confirmation step, and evidence policy.

## Remaining limitations and next feature

- No automatic coefficient application, coefficient registry, calibration
  expiry policy, uncertainty budget, traceable instrument certificate, or
  firmware write-back exists.
- No physical AFE, reference source, DMM, oscilloscope, function generator, or
  school laboratory resource was used.
- The next approved product increment is the frequency-response workflow:
  formal TestRun/criteria mapping, Replay input, Bode/cutoff presentation,
  structured export, CLI, Dashboard, and report integration. It must preserve
  the same host-vs-bench evidence boundary.
