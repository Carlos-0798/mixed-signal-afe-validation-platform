# Development Environment Setup Report

**Date:** 2026-08-29  
**Scope:** Windows host software environment only  
**Hardware evidence:** None

## Installed host software

| Component | Verified result |
|---|---|
| OS | Windows 11 Home 64-bit, build 26200 |
| Python | python.org CPython 3.12.10 64-bit |
| Git | Git for Windows 2.55.0.windows.3 |
| VS Code | 1.135.0 x64 |
| VS Code extensions | Python 2026.4.0, Pylance 2026.3.1, Ruff 2026.74.0 |
| LTspice | 26.0.1; present but not required by Software Phase 1 |

The project `.venv` reports the independent python.org executable as `sys._base_executable`; it no longer depends on the Codex cached Python runtime. The previous environment is retained as `.venv-codex-backup-20260829`.

## Installed project tools

- pip 26.2.1;
- setuptools 84.0.0;
- wheel 0.48.0;
- build 1.6.0;
- pytest 8.4.2;
- pytest-cov 7.1.0 / coverage 7.16.0;
- Ruff 0.16.5;
- mypy 2.3.1.

`pip check` reported no broken requirements.

## Executed verification

| Check | Actual result |
|---|---|
| Unit tests | PASS: 23 passed in 0.16 s |
| Phase 0 package coverage | 88% total |
| mypy on `dashboard` and `tools` | PASS: no issues in 15 source files |
| Isolated sdist and wheel build | PASS |
| Wheel installation outside repository | PASS |
| Import from clean wheel environment | PASS, distribution version 0.0.1 |
| Ruff check | TOOL PASS / CODE GATE NOT YET PASS: 3 existing Phase 0 findings |

The Ruff findings are one `itertools.pairwise` modernization, one `collections.abc.Iterable` import modernization, and one test import-format finding. They do not indicate an installation failure and are left for the planned Phase 1 source migration rather than silently changing the Phase 0 implementation during environment setup.

## Git baseline

- Git `user.name` is `Carlos-0798`.
- Git `user.email` is configured to the account's GitHub-provided `noreply` address; the exact address is intentionally omitted from this report.
- The first Phase 0 baseline is established by this environment setup workflow; use `git log` for the resulting commit identifier.

## Evidence boundary

This report verifies host installation, Python tests, packaging, static analysis availability, and clean package import only. It does not verify AFE circuitry, MSP430 behavior, serial communication, wiring, ADC accuracy, instruments, or any physical measurement.
