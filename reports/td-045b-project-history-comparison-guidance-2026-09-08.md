# TD-045B project history comparison guidance acceptance

Status: **COMPLETE — local and uncommitted**<br>
Date: 2026-09-08<br>
Evidence: `HOST_TEST` with Simulator-produced `SYNTHETIC` results and immutable
evidence-label fixtures. No serial port, MSP430, AFE, or laboratory instrument
was discovered, opened, or operated.

## Product outcome

The **Projects & history** comparison now gives a new user an interpretation
guide before the detailed rows. It shows:

- the common project ID, baseline run, candidate run, and both batch states;
- whether the exact saved project snapshot changed;
- matched, baseline-only, candidate-only, and not-started preset coverage;
- exact evidence labels on both sides and the preset IDs where those labels
  match, differ, or are unavailable;
- preset IDs already marked changed by `validation-run-comparison.v1`; and
- the fixed numeric convention `candidate - baseline`, with an explicit warning
  that the sign alone is not an improvement or regression decision.

The detailed table remains authoritative for individual record fields,
configuration SHA-256 values, metrics, and copied engineering outcomes. The new
guide does not recalculate or upgrade PASS/FAIL.

## Contract and compatibility boundary

- `validation-project.v1`, `validation-run-manifest.v1`,
  `validation-run-manifest.v2`, and `validation-run-comparison.v1` are unchanged.
- Existing v1 manifests remain readable and display `LEGACY_V1`; no saved file
  is rewritten.
- The Phase 5 public imports, dataclasses, signatures, CLI paths, serialized
  fields, exit codes, and golden hashes are unchanged.
- The comparison still verifies both manifests and referenced artifacts before
  presentation and still requires the same project ID.
- Project snapshot SHA-256 drift is shown separately from evidence-label drift.
- Evidence classes remain distinct. `SYNTHETIC`, `CSV_REPLAY`, `HOST_TEST`,
  `SPICE_IDEAL`, `BENCH_CONTROLLER`, and `BENCH` are not treated as equivalent.
- SHA-256 remains an integrity check, not authorship or authentication.

## Test-first record

The first targeted run failed during collection because the new
`_comparison_guidance_text` and `_build_comparison_guidance` functions did not
exist. This was the expected red test for the new behavior.

After the minimal implementation, 17 unit tests passed. Focused mypy then found
that expanding a dynamically typed two-item tuple could not prove the helper's
three-argument call shape. The call was changed to explicit manifest indices;
runtime behavior did not change. The repeated focused unit and real-Tk chain
passed.

Boundary tests cover complete same-evidence comparisons, changed project
snapshots, `SYNTHETIC` versus `CSV_REPLAY` labels, one-sided results,
not-started presets, unavailable evidence, legacy-v1 batch labeling, long-list
summaries, initial empty guidance, and guidance reset after history clearing.

## Executed verification

| Gate | Result |
| --- | --- |
| Workspace/widget and five-scaling real-Tk focused tests | **22 passed** |
| Changed Dashboard modules | **481/481 statements, 100%** |
| Full pytest suite | **2,694 passed in 49.68 s** |
| Full package statement coverage | **16,091/16,091, 100.00%** |
| Phase 5 public API golden + product quality | **17 passed in 1.80 s** |
| Standard/high-contrast accessibility smoke + project real-Tk matrix | **15 passed in 24.53 s** |
| Ruff | **PASS** |
| mypy | **PASS across 227 source files** |
| `pip check` | **PASS — no broken requirements** |
| `git diff --check` | **PASS** |

The real Windows Tk project chain ran at scaling 1.0, 1.25, 1.5, 1.75, and
2.0 in separate processes. It retained keyboard range selection, cooperative
batch cancellation, cleanup-before-close, history refresh, visible controls at
1040×760, comparison rows, exact `SYNTHETIC` text, one-sided coverage, and the
delta convention.

## Files changed in TD-045B

- `src/analog_validation_app/dashboard/project_workspace.py`
- `src/analog_validation_app/dashboard/project_widgets.py`
- `tests/unit/test_dashboard_projects.py`
- `tests/integration/test_dashboard_project_workflow.py`
- `CHANGELOG.md`
- `README.md`
- `docs/PROJECT_STATUS.md`
- `docs/TECHNICAL_DEBT.md`
- `docs/UX_DESIGN_AUDIT.md`
- `docs/dashboard.md`
- `docs/test-projects-and-history.md`
- `reports/README.md`
- this report

## Remaining boundaries

TD-040C remains open for raw READ/LIVE observation persistence, trace overlay,
and a separately designed trust/signature model. Those features were not mixed
into this display-layer change. The Tk 8.6.15 screen-reader limitation and the
Proposed ADR-0004 runtime decision also remain unchanged. A real-user study is
still needed for claims about novice usability beyond the automated behavior
checks.

No commit, push, PR mutation, tag, release, package publication, history rewrite,
reset, checkout, clean, or hardware action was performed.
