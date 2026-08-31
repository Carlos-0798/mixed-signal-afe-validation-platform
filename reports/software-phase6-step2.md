# Software Phase 6 Step 2 Verification Report

**Date:** 2026-08-31<br>
**Status:** PASS — hosted CI established<br>
**Evidence class:** HOST_TEST / SYNTHETIC / clean package installation<br>
**Physical serial or hardware operation:** none<br>
**Verified AFE bench-performance claims:** 0<br>
**Passing implementation commit:** `90bb89c`<br>
**Passing GitHub Actions run:** `33444546631`

## Outcome

The repository now has a read-only GitHub Actions workflow that independently
checks the complete host suite on Windows and Ubuntu with Python 3.10, 3.12,
and 3.14.  A separate quality job enforces 100% package statement coverage,
Ruff, mypy, and dependency consistency.  A Windows packaging job builds the
sdist and wheel, installs the wheel into fresh base and `[serial]`
environments, runs the installed CLI/demo, and exercises only an injected
serial substitute.

The final hosted run passed every job.  No real port was enumerated or opened,
no controller was operated, and no release was published.

## Why this checkpoint matters

A local test proves behavior in the developer's current environment.  Hosted
CI starts from fresh runner images and repeats the declared gates after each
change, which catches hidden dependencies and version-specific assumptions.
This checkpoint did exactly that: the first run exposed genuine Python support
and test-portability gaps that Python 3.12 on the development machine could not
show.

## Diagnostic history retained

| Run | Result | What it revealed |
|---|---|---|
| `33443949315` | FAIL | Python 3.10 used 3.11-only `Self`/`tomllib`; Python 3.14 exposed an invalid `NaN == NaN` test assumption; Linux Ruff found two missing executable bits |
| `33444351044` | FAIL | All 3.12/3.14, quality, build, and install gates passed; Python 3.10 exposed version-dependent `Callable[...]` class detection in two API-ownership tests |
| `33444546631` | PASS | All six OS/Python host combinations plus quality and packaging passed |

The failed runs are not hidden or treated as passing evidence.  They show the
normal engineering loop: discover a mismatch, identify whether code or test
logic owns it, add a bounded correction, and rerun the complete gate.

## Final hosted matrix

| Gate | Result |
|---|---|
| Ubuntu / Python 3.10 | PASS — complete host suite |
| Ubuntu / Python 3.12 | PASS — complete host suite |
| Ubuntu / Python 3.14 | PASS — complete host suite |
| Windows / Python 3.10 | PASS — complete host suite |
| Windows / Python 3.12 | PASS — complete host suite |
| Windows / Python 3.14 | PASS — complete host suite |
| Python 3.12 coverage | PASS — 11,470/11,470 statements, 100% |
| Ruff | PASS |
| mypy | PASS — 192 source/tool/test files |
| Dependency checks | PASS |
| Isolated sdist/wheel build | PASS |
| Fresh base wheel install and CLI/demo | PASS |
| Fresh `[serial]` install with injected substitute | PASS — no real port operation |

The final local pre-push gate also passed 2,193 tests with 100% statement
coverage, Ruff, mypy, and `pip check`.

## Workflow safety and supply-chain boundary

- Workflow permissions are limited to `contents: read`.
- Checkout, Python setup, and artifact upload actions are pinned to reviewed
  full commit SHAs.
- Concurrency cancels superseded branch runs.
- Uploaded distributions have a seven-day retention bound.
- No publish, tag, release, repository-write, secret-consuming, port-discovery,
  or physical-device job exists.
- The serial-extra smoke injects `SYNTHETIC_PORT`; it does not query the host's
  port inventory and the backend still exposes no `write()` method.

## Evidence boundary

This is cross-version host-software, packaging, and clean-install evidence.  It
does not establish physical AFE gain, offset, saturation, cutoff frequency,
hysteresis, ADC/DAC accuracy, protection, bandwidth, noise, safety, or
reliability.  The connected MSP430 was not enumerated, opened, reset, flashed,
read, or written during this checkpoint.

## Next checkpoint

Step 3 upgrades the single package version source to `0.1.0b1`, aligns package
metadata and user-facing documentation, and adds a changelog.  It does not
create a Git tag or GitHub Release.
