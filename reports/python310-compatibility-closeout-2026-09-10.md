# Python 3.10 compatibility closeout — 2026-09-10

## Result and revision

The owner authorized synchronization of the timestamp correction and one further
manual hosted verification. [Run 34533435977](https://github.com/Carlos-0798/mixed-signal-afe-validation-platform/actions/runs/34533435977)
completed successfully: **8/8 jobs, attempt 1**, on
`709c18fdb4dd10783888b272d2739a706a36951e`.
[PR #11](https://github.com/Carlos-0798/mixed-signal-afe-validation-platform/pull/11)
was merged as `f9cbfff596a38aa30dad3c02b023daa94692fd1c`; its tree is identical
to the tested revision. Subsequent closeout edits are documentation only and
are not represented as another hosted run.

## Correction and compatibility

Python 3.10 rejected some fractional-second widths already permitted by the
Replay and voltage-table contracts. Preserve the existing grammar checks, then
pad accepted fractions to six digits before standard-library parsing. For
example, `.1` becomes `.100000`, preserving the same instant exactly.

The fix covers Replay timestamps, voltage CSV time columns, and elapsed-time
acquisition origins with explicit timezones. It introduces no dependency,
public API/schema change, artifact rewrite, precision truncation, or new input
grammar. Two runtime files and their two unit-test files changed; 69 new
parametrized cases cover the accepted precision and rejection boundaries.
GUI code, integration assertions, and workflow triggers are unchanged.

The first run, `34531879037` at `4a73e32`, remains **6 passed / 2 failed**.
Its cause, local CPython 3.10 reproduction, and correction checks are retained in
the [first-attempt report](cloud-ci-recheck-2026-09-10.md).

## Executed hosted evidence

| Job | Actual result |
|---|---|
| Windows / Python 3.10 | 3,116 passed, 1 skipped |
| Windows / Python 3.12 | 3,116 passed, 1 skipped |
| Windows / Python 3.14 | 3,116 passed, 1 skipped |
| Ubuntu / Python 3.10 | 3,088 passed, 29 skipped |
| Ubuntu / Python 3.12 | 3,088 passed, 29 skipped |
| Ubuntu / Python 3.14 | 3,088 passed, 29 skipped |
| Coverage, lint, and types | 3,088 passed, 29 skipped; 17,574/17,574 package statements (100%); Ruff, mypy on 252 files, and dependency checks passed |
| Windows / Python 3.12 candidate verification | 11/11 candidate gates; audit `PASS_WITH_REVIEW` |

Ubuntu skips 28 Windows-specific Tk tests and one Windows console-entry test.
The Windows matrix skips that console-entry test when the expected executable
is not beside its interpreter. The package gate separately verifies the real
installed console entry point. Skips are not counted as executed passes, and
the Ubuntu result does not validate a Linux GUI or macOS.

The package job passed two independent byte-identical wheel/sdist builds,
clean base and serial-extra installs, normal/Unicode-path synthetic demos,
the external public adapter, and the injected host-only serial substitute.
Its complete pytest/100% statement-coverage command passed; inner pytest detail
counts were not exported and are not inferred from the six matrix jobs.
Downloaded archive digests and contained wheel/sdist/manifest identities were
checked against GitHub and the candidate records.

The audit has zero current-tree privacy findings and zero high-confidence
credential findings. Its nine historical review groups match the already
accepted eight local-path groups and one GitHub noreply group. Those disclosures
remain in history; the machine result stays `PASS_WITH_REVIEW`. No history
rewrite or renewed visibility/license decision was made.

## Local evidence and remaining limits

The final local combined patch passed 280 targeted tests. Its full execution
recorded **3,113 passed and four real-Tk focus failures**, with 100% coverage of
17,574 statements. Those exact four tests subsequently passed 4/4 in an
unchanged serial recheck. All three hosted Windows suites then passed them.
These are separate executions, not a claim that the original local suite was
all green. Desktop focus sensitivity remains documented; its external cause
was not established. No assertion was weakened and no new skip was introduced.

TD-054 is closed. Feature expansion remains paused; TD-053 still requires real
source samples before selecting another format. Screen-reader support,
unverified GUI platforms, real-device acquisition, and physical AFE validation
retain their existing limitations.

## Delivery boundary

The corrected source is integrated into public `main`. This is an installable
`0.1.0b1` source beta suitable for portfolio review, not a new tag, GitHub
Release, or package-registry publication. The repository was already public
before this correction.

Only one new manual dispatch was made for this correction; no automatic rerun
was used. Local-first testing and `workflow_dispatch`-only CI remain unchanged.
No budget/billing setting was changed. No serial port was enumerated/opened,
and no MSP430, AFE, or laboratory instrument was accessed.

All new results are `HOST_TEST`, using synthetic/Replay fixtures. `SYNTHETIC`,
`CSV_REPLAY`, `SPICE_IDEAL`, `BENCH_CONTROLLER`, and `BENCH` are not interchangeable;
this verification adds no hardware-performance claim.
