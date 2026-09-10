# Hosted CI recheck and Python 3.10 timestamp correction — 2026-09-10

## Executed cloud result

The owner explicitly requested one hosted test attempt. Workflow
[34531879037](https://github.com/Carlos-0798/mixed-signal-afe-validation-platform/actions/runs/34531879037)
ran once on `main` at `4a73e32b1390f3f17b5bc4c3597017f1e2b9720a`.
GitHub accepted the dispatch and executed the jobs; this was not another
account-blocked `NOT_RUN`. Its final result is **FAILURE: six jobs passed and
two failed**. No rerun or additional dispatch occurred during that attempt.

| Hosted job | Recorded result |
|---|---|
| Ubuntu / Python 3.10 | 1 failed, 3,018 passed, 29 skipped |
| Windows / Python 3.10 | 1 failed, 3,046 passed, 1 skipped |
| Ubuntu / Python 3.12 | 3,019 passed, 29 skipped |
| Ubuntu / Python 3.14 | 3,019 passed, 29 skipped |
| Windows / Python 3.12 | 3,047 passed, 1 skipped |
| Windows / Python 3.14 | 3,047 passed, 1 skipped |
| Coverage, lint, and types | PASS: 17,567/17,567 statements; Ruff, mypy on 252 files, and dependency checks passed |
| Deterministic release-candidate verification | PASS: 11/11 candidate gates; release audit `PASS_WITH_REVIEW`, with historical disclosures retained |

Ubuntu skips include 28 Windows Tk tests and one Windows console-entry test.
The Windows matrix skips that console-entry test because the expected executable
is not beside its interpreter; the package job separately checks an installed
console entry point. Skipped tests are not described as executed passes.

The package gate verified two byte-identical builds, clean base/serial-extra
installs, ordinary/Unicode-path synthetic demos, and an injected host-only serial
substitute. Its inner pytest counts were not exported, so a precise package-test
count is not inferred from the matrix. The artifact ZIP digest and contained
wheel/sdist/manifest identities match. Its nine history-review groups correspond
to the previously accepted eight local-path groups and one GitHub noreply group;
no additional review category was found. The machine result remains
`PASS_WITH_REVIEW`, not an unconditional privacy-clearance claim.

Both failures are the same test:
`test_live_monitor_csv_replay_preserves_replay_evidence`.
A valid timestamp such as `2026-01-01T00:00:00.1Z` passes the Replay format's
explicit one-to-six-digit fraction rule, but Python 3.10's `fromisoformat`
rejects fractions of one, two, four, or five digits. Python 3.12 and 3.14 accept
them. This is a supported-input compatibility defect, not a new billing failure.
Review of the ordinary voltage-table import found the same standard-library
dependency behind its explicitly supported fractional timestamp grammar.

## Local correction and compatibility

Keep the existing grammar validation, then normalize an accepted fractional
second to six digits before calling the standard-library parser. Padding zeros
preserves the exact time: `.1` and `.100000` represent the same 100000 microseconds.
Apply this to Replay timestamps and explicit-timezone voltage-table timestamps,
including mapping epochs. Keep invalid dates, unsupported precision, and invalid
timezone forms rejected.

No public API, schema, minimum Python version, stored artifact, test fixture,
evidence category, or CI trigger is changed. No new dependency is introduced.
The correction was prepared locally after the failed cloud revision; the hosted
result above does not verify this follow-up. The owner subsequently authorized
committing/synchronizing the correction and one further manual hosted check.

## Local verification

- Initial Replay-only correction: 136 targeted tests, followed by 3,070 full-suite
  tests and 17,570/17,570 statement coverage passed on local Windows/Python 3.12.
  This intermediate result predates the additional voltage-import correction.
- Final combined correction: 280 targeted tests passed. The two test files add
  69 parametrized regression cases covering exact UTC values, all supported
  fraction widths, explicit offsets, mapping round trips, retained evidence,
  and rejected syntax/calendar/UTC-overflow inputs.
- Final full-suite execution: **3,113 passed and four failed**, with
  **17,574/17,574 statements covered (100%)**. All four failures were existing
  real-Tk keyboard-focus assertions, across one project-history scenario and
  three theme/scaling scenarios. A serial rerun of those exact four tests,
  without source or assertion changes, passed **4/4**. Both executions are
  retained; they are not combined into a fictitious single all-green suite.
  This demonstrates non-reproduction, not proof of what stole window focus.
- Full-scope Ruff, mypy on 252 files, and `pip check` passed for the final code.
  Public API/schema golden files and existing fixture/artifact bytes are unchanged.
- A separate official CPython 3.10.11 Windows embeddable interpreter reproduced
  four accepted Replay fraction widths failing at `4a73e32`; the same 22-case
  public-parser check passed 22/22 against the correction. This is focused local
  compatibility evidence, not a rerun of the Python 3.10.21 hosted jobs.
- The same Python 3.10.11 interpreter checked 47 voltage timestamp scenarios
  through both public entry points (CSV time column and elapsed-time origin):
  94 checks total. The baseline passed 70/94; its 24 failures were exactly the
  four affected fraction widths across three timezones and two entry points.
  The final correction passed **94/94**, preserving UTC values, one-microsecond
  elapsed increments, `CSV_REPLAY` provenance, and error row/column locations.

The local desktop focus failures remain an acceptance-environment limitation to
observe on a quiet or dedicated desktop. GUI runtime and integration-test files
were not changed, and no test was skipped or assertion weakened to make it pass.
The external receipt retains initial, final, and focused-rerun logs separately.

The final local diff/relative-link/current-tree privacy/project-boundary checks
also passed. The reviewed patch contains two runtime files, two unit-test files,
three current-state documents, and this report. It remained uncommitted at the
first-attempt closeout; the subsequent owner authorization permits integration
and a new manual hosted check. A future result must be tied to its own revision.

## Publication and continuation

The repository was already made public in the prior owner-approved publication
step and remains public. That source-publication decision is distinct from a
claim that every current platform test passed. For the published `4a73e32`
revision, prefer Python 3.12 or 3.14 until the timestamp correction is integrated.
The full matrix remains failed; do not label it green based on six passing jobs.

The next narrow step is to integrate the reviewed correction and perform the
new owner-authorized hosted recheck. The local-first,
manual-only CI policy remains in effect. No automatic trigger, budget/billing
adjustment, visibility change, tag, Release, package-registry publication,
hardware access, or history rewrite was performed in this recheck.

All new results are `HOST_TEST`, with synthetic/Replay fixtures. They establish
no new `BENCH_CONTROLLER`, `BENCH`, or AFE hardware-performance result.
