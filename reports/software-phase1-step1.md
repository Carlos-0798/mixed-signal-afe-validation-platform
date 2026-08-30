# Software Phase 1 Step 1 Report

**Date:** 2026-08-29  
**Milestone:** installable package and version foundation  
**Evidence class:** HOST_TEST  
**Hardware evidence:** None

## Outcome

Software Phase 1 Step 1 is complete. The project now has a formal controller-neutral package at `src/analog_validation/` instead of relying on imports that work only because the current directory is the repository.

The package version has one source of truth:

```text
0.1.0.dev0
```

Setuptools reads this value from `analog_validation.version.__version__`; package code and installed distribution metadata are tested for equality.

## Changes

- adopted the standard `src` package layout;
- created the public `analog_validation` package;
- added the `py.typed` marker for future typed public APIs;
- moved package version metadata to one source;
- added editable-install and repository-external import tests;
- excluded the legacy `dashboard` prototype from the formal wheel;
- retained the legacy code in the repository until its planned one-time migration in later Phase 1 steps.

## Executed verification

| Check | Actual result |
|---|---|
| Editable install | PASS |
| Package/metadata version equality | PASS: `0.1.0.dev0` |
| pytest | PASS: 25 tests |
| New package coverage | PASS: 100% of the current 3 executable statements |
| Ruff on `src` and `tests/unit` | PASS |
| mypy on `src` and `tests/unit` | PASS: no issues in 3 source files |
| Isolated sdist build | PASS |
| Isolated wheel build | PASS |
| Wheel installation outside repository | PASS |
| Import from installed wheel | PASS |
| Legacy `dashboard` present in wheel | No |

The 100% coverage number applies only to the very small Step 1 package/version surface. It is not a claim that the future protocol, configuration, analysis, adapter, CLI, or Dashboard is complete.

## Issue found and resolved

A stale Phase 0 root-level `.egg-info` directory initially caused installed metadata to report `0.0.1` while the new package reported `0.1.0.dev0`. The generated stale metadata was moved out of the repository, and the equality test now prevents recurrence from passing silently.

## Remaining Phase 1 work

- stable error hierarchy;
- provenance and quality-aware measurement models;
- capability and test-run models;
- CRC/framing migration into the formal package;
- AFE v1 profile;
- safe configuration validation;
- complete Phase 1 coverage and documentation closure.

No serial driver, GUI toolkit, board SDK, physical controller, AFE circuit, or laboratory instrument was used or validated in this step.
