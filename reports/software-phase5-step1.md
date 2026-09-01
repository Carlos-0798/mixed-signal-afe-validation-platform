# Software Phase 5 Step 1 Report

**Date:** 2026-08-31<br>
**Milestone:** product contracts, reviewed catalog, stable issues, and CLI foundation<br>
**Evidence class:** HOST_TEST and repository-external package installation<br>
**Hardware/serial/display operation:** none<br>
**Verified AFE hardware performance claims:** 0

**Implementation commit:**
`6c204bb0ff925bd73cf9cd3df1f905b16d4d884a`

## Outcome

Software Phase 5 Step 1 is complete; Phase 5 implementation is now 1 of 8
checkpoints. The repository has an installed product identity and controlled
entry boundary without moving engineering logic out of the frozen core.

This checkpoint does not run a validation job. It establishes the contracts
that later CLI and Dashboard workflows must share, proves a base installation
does not require pyserial or a display, and removes misleading Phase 0 Dashboard
placeholders after all previous golden behavior remains green.

## Delivered product boundary

| Component | Delivered behavior |
|---|---|
| `models.py` | Immutable bounded `product-job.v1` and `product-result.v1`; explicit source/profile/job; product output requests rejected; source/evidence and status/outcome consistency enforced |
| `catalog.py` | Exact reviewed source/profile catalog; Simulator and Replay analysis declarations; receive-only Serial declaration; no profile-version guessing |
| `issues.py` | Typed expected-error mapping to `user-issue.v1` with code, severity, what happened, possible cause, and safe next step; unexpected details hidden |
| `cli.py` | One `analog-validation` parser with help/version/profiles, deterministic human and `product-cli-output.v1` JSON views, stable usage exit code 2, and no default traceback |
| package boundary | Typed public exports, one package version, `python -m analog_validation_app`, and `py.typed` |
| architecture tests | Lower layers cannot import the product package; product package contains no GUI/driver/legacy runtime import and no copied protocol or analysis implementation |

Every catalog profile is product-read-only. `afe/1` and
`msp430-equipment-health/1` remain separate identities; the latter is only a
public receive-only compatibility profile for an independent peer product.

## Retired legacy surface

The root `dashboard/` Python source and `tests/test_dc_sweep.py` /
`tests/test_hysteresis.py` were removed. They were Phase 0 placeholders and
weaker migration comparisons, not the formal product Dashboard or the formal
analysis implementation. The authoritative DC and hysteresis implementations,
tests, golden results, and public contracts remain under `src/analog_validation`
and the Phase 3 test suites.

This reduces the risk that a future contributor edits the wrong algorithm or
mistakes a placeholder for a completed product feature.

## Executed verification

| Gate | Actual result |
|---|---|
| Step 1 focused tests | PASS — 127 tests |
| Product package coverage | PASS — 389/389 statements, 100% |
| Full pytest suite | PASS — 1,645 tests |
| Formal + optional + product package coverage | PASS — 7,714/7,714 statements, 100% |
| Phase 1–4 golden compatibility | PASS — unchanged within the full suite |
| Full-repository Ruff | PASS |
| mypy on `src`, `tools`, and `tests` | PASS — 147 files |
| Dependency consistency | PASS — no broken requirements |
| Isolated sdist/wheel build | PASS — `0.1.0.dev0` |
| Archive inspection | PASS — product package and one console script present; root Dashboard absent |
| External base-wheel install | PASS — clean repository-external venv, `--no-deps`, no pyserial available |
| Installed commands | PASS — console help/version/profiles, JSON variants, and module entry point |
| Unknown command behavior | PASS — exit 2; empty stdout; what/why/safe-next-step stderr; no traceback |
| Optional import isolation | PASS — `serial`, `analog_validation_pyserial`, and `tkinter` not imported |
| Documentation relative links | PASS — 103 Markdown files checked, zero missing relative targets |
| Patch whitespace | PASS |
| Physical port, UI window, or hardware test | NOT RUN |

The focused 127 tests replace eight retired legacy test cases, so the complete
suite increased by a net 119 tests from 1,526 to 1,645.

## Build and clean-install evidence

Final isolated artifacts:

| Artifact | Size | SHA-256 |
|---|---:|---|
| `mixed_signal_afe_validation_platform-0.1.0.dev0-py3-none-any.whl` | 167,576 bytes | `2FDD998C711AB3607E30AF96C13C8DAD24AD23BC211D40F517990D4F321AFD47` |
| `mixed_signal_afe_validation_platform-0.1.0.dev0.tar.gz` | 297,584 bytes | `263092205C95719401EFF2968666008B00486EECC0B53955CC0EC00F394B687E` |

The inspected wheel entry point is exactly:

```text
analog-validation = analog_validation_app.cli:main
```

The final external verification used a clean short-path virtual environment
outside the repository. It installed the wheel with `--no-deps` and confirmed
the import resolved from that environment's `site-packages`. `importlib` found
no `serial` package, and the product commands did not load optional serial or
Tk modules.

Example installed human output:

```text
Analog Validation Studio 0.1.0.dev0
```

Unknown-command output used the stable structure:

```text
ERROR [INVALID_REQUEST]
What happened: ...
Possible cause: ...
Safe next step: ...
```

Generated build artifacts and the external virtual environment are local
verification outputs, not committed release binaries.

## Safety and evidence boundary

- Product requests cannot set `allow_output=true`.
- The serial catalog entry exposes `READ` only and does not create a write API.
- Simulator evidence can only be `SYNTHETIC`; Replay can only be `CSV_REPLAY`;
  serial results require explicit `HOST_TEST` or `BENCH_CONTROLLER` provenance.
- Mandatory limitations and outcome/status checks prevent cancelled,
  unsupported, incomplete, or failed work from appearing as PASS/FAIL evidence.
- No COM port was discovered or opened, no bytes were transmitted, and no
  Tkinter window was imported or created.

The earlier Phase 4 five-record MSP430 receive-only HIL remains the only narrow
physical result and was not rerun or upgraded. It does not validate exact
firmware, sensors, fan, wiring, disconnect recovery, long-duration transport,
or any physical AFE behavior.

## Remaining work and next gate

Step 1 intentionally does not provide:

- an owning/cancellable worker or product event stream;
- Simulator/Replay/Serial job execution from the product CLI;
- report generation or deterministic charts;
- Dashboard state/presenter/widgets;
- a complete beginner workflow or installed demo.

The next checkpoint is Phase 5 Step 2 only: implement a bounded single-owner
worker with cooperative cancellation, monotonic bounded events, deterministic
cleanup, and injected host-side fault/race tests. It will not access a real COM
port or create a Dashboard window.
