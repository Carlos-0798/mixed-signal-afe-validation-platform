# Software Phase 5 Step 4 Report

**Date:** 2026-08-31
**Milestone:** evidence-visible human reports and deterministic charts
**Evidence class:** HOST_TEST rendering from SYNTHETIC finalized inputs
**Physical port/display/hardware operation:** none
**Verified AFE hardware performance claims:** 0

**Implementation commit:**
`0a6913306b8d0573ce88619faf5ccdf3911dfa75`

## Outcome

Software Phase 5 Step 4 is complete; Phase 5 implementation is now 4 of 8
checkpoints. The installed `analog-validation report` command accepts strict
JSON or CSV `result-export.v1`, creates a presentation-only view, and atomically
publishes plain text, Markdown, self-contained HTML, deterministic SVG, and a
hash manifest.

The implementation does not import or call engineering analysis, device
adapters, serial backends, board SDKs, Tkinter, or network code. It copies the
finalized outcome, evidence, metrics, criteria, predicted values, transition
brackets, limitations, and lineage. It cannot refit DC data, redetect hysteresis
transitions, re-evaluate criteria, or turn a non-PASS result into PASS.

## Delivered behavior

| Component | Delivered behavior |
|---|---|
| presentation contract | Immutable, bounded `human-report.v1` view built only from `ResultExportBundle` |
| text formats | Deterministic complete `report.txt` and escaped `report.md` |
| chart formats | DC included/excluded/invalid points plus frozen predicted line; hysteresis directions, adjacent transition brackets, and copied final thresholds |
| HTML | UTF-8, inline CSS, embedded exact SVG, no scripts or remote resources |
| publication | Five fixed files, staging-directory write, create-new atomic rename, no overwrite |
| traceability | Canonical result SHA-256, report/input/software schemas, run/config/device/profile identity, record IDs, criteria, limitations, and not-verified list |
| CLI | JSON or human summary, automatic `.json`/`.csv` detection, stable user issues, engineering-outcome-preserving exit code |
| hardware honesty | Every report/manifest says `NO_NEW_HARDWARE_VALIDATION` |

## Executed verification

| Gate | Actual result |
|---|---|
| Phase 5 focused product tests | PASS — 431 tests |
| Product package coverage | PASS — 2,196/2,196 statements, 100% |
| Step 4 report/CLI/golden subset | PASS — 180 tests; new presentation/reporting/CLI statements covered |
| Full pytest suite | PASS — 1,949 tests |
| Formal + optional + product coverage | PASS — 9,521/9,521 statements, 100% |
| Phase 1–4 golden compatibility | PASS — retained inside the full suite |
| Phase 5 report golden compatibility | PASS — two cases, ten exact artifacts |
| Ruff rule check | PASS |
| Ruff formatting for Step 4 changed Python files | PASS |
| mypy on `src`, `tools`, and `tests` | PASS — 164 files |
| pip dependency check | PASS — no broken requirements |
| Patch whitespace | PASS |
| Isolated sdist/wheel build | PASS — `0.1.0.dev0` |
| Wheel archive inspection | PASS — 82 files; report modules, typed markers, and console entry point present |
| Repository-external base-wheel install | PASS — no pyserial/Tk import, Simulator DC result, five report artifacts, HTML/SVG parsing |
| Physical serial, GUI, instruments, or AFE test | NOT RUN |

One initial PowerShell-focused-test command passed an unexpanded wildcard to
pytest and collected no tests. It was corrected by resolving the file list in
PowerShell; the corrected 431-test gate passed. This was a command-selection
error, not a product test failure.

The repository-wide formatter still proposes historical formatting-only edits
tracked separately in TD-034. Ruff's rule checker passed, and every Step 4
Python file passed the formatter without mixing that repository-wide cleanup
into this feature.

## Frozen report artifacts

The committed `phase5-human-report-golden.v1` manifest is HOST_TEST evidence over
two existing SYNTHETIC input results:

| Case | Canonical result SHA-256 | Frozen output |
|---|---|---|
| DC sweep | `a137b527303a7a8938b4bba7f74d28f35e9a9ca013474cd5946f4d6da9591547` | five exact artifacts; included/excluded points and frozen predicted line |
| Hysteresis | `e7534508afea6dcf231387de293408d0a1b247ad3ee4a496b970dba4456f58db` | five exact artifacts; rising/falling paths, adjacent brackets, 1750/1550 mV copied thresholds |

These values prove deterministic software presentation. The thresholds and DC
fit are synthetic software regressions, not measurements of a comparator or
analog front end.

## Build and external-install evidence

| Artifact | Size | SHA-256 |
|---|---:|---|
| `mixed_signal_afe_validation_platform-0.1.0.dev0-py3-none-any.whl` | 205,551 bytes | `12A5F29BA964110E7283528833C6114BE6F5522F42741177517ABE0587380060` |
| `mixed_signal_afe_validation_platform-0.1.0.dev0.tar.gz` | 369,934 bytes | `CB30B5DD5C191B4ED40FF90D4C46D0DDA69FA5D691816F25920B88875547A2DA` |

The final wheel was installed into a fresh virtual environment under
`%LOCALAPPDATA%\Temp`, outside the repository. From that environment the base
package imported without loading pyserial or Tk, produced a fresh SYNTHETIC DC
result, then generated exactly five report files. The HTML parser and SVG XML
parser accepted the outputs, and the manifest retained
`NO_NEW_HARDWARE_VALIDATION`.

The host's Windows application-control policy blocked the pip-generated
console-wrapper executable from running inside the temporary directory. The
external smoke therefore invoked the installed wheel's same
`analog_validation_app.cli:main` entry point through the virtual environment's
Python interpreter. This verifies the installed CLI implementation and report
pipeline, but does not claim that the temporary-directory `.exe` wrapper was
allowed by this host policy.

Generated archives, environments, and smoke outputs are local verification
artifacts, not committed release binaries.

## Safety and evidence boundary

- The connected MSP430 was not enumerated, opened, read, reset, flashed, or
  written during Step 4.
- No AFE, breadboard, ADC, comparator, instrument, or school laboratory resource
  was used.
- Synthetic or replay input remains labelled as such in every output.
- The HTML renderer rejects caller-substituted SVG, including an SVG-looking
  script-injection payload.
- Reports omit raw serial frames, absolute output paths, usernames, and USB
  identity; the CLI may show the user's local destination for immediate use.
- Existing output paths are rejected, and partial staging directories are
  cleaned after tested write or rename failures.
- A report's exit code follows the already-finalized engineering outcome; a
  successfully written FAIL report still exits 1.
- The earlier Phase 4 receive-only MSP430 result remains a separate narrow
  `BENCH_CONTROLLER` record and was not repeated or broadened.

## Remaining work and next gate

Step 4 does not provide a Dashboard, beginner wizard, one-command portfolio
demo, calibration/frequency specialized report mapping, PDF, CI, v1.0 release,
or physical AFE validation.

The next checkpoint is Software Phase 5 Step 5 only: implement a headless,
immutable Dashboard state model and presenter first, then a lazy local
Tkinter/ttk desktop shell. The existing worker and report view remain the only
sources of task state and finalized result presentation; widgets may not parse
profiles, open devices, or calculate engineering conclusions.
