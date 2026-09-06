# Private Beta `0.1.0b1` Release Notes — Draft

> **DRAFT — NOT PUBLISHED.** This document is an owner-review preview. It does
> not create a tag, GitHub Release, public repository, PyPI package, license, or
> v1.0 claim.

## Product summary

Analog Validation Studio is a controller-neutral, software-first platform for
repeatable analog front-end test workflows. The private beta provides a CLI,
guided desktop Dashboard, deterministic simulator, CSV Replay, versioned AFE
and optional MSP430 compatibility profiles, analysis runners, structured
exports, evidence-aware reports, and a documented public adapter contract.

## Verified software scope

- Python 3.10, 3.12, and 3.14 host testing on Windows and Ubuntu;
- deterministic wheel and source-distribution construction;
- clean base and optional `[serial]` installs outside the repository;
- reproducible synthetic demo output in normal and Unicode paths;
- public-API-only read adapter execution outside the repository;
- full package statement coverage, Ruff, mypy, and dependency consistency;
- create-new output behavior and privacy-minimal machine manifests.

All beta evidence is `HOST_TEST`, `SYNTHETIC`, or explicitly identified
`CSV_REPLAY`. It carries the boundary `NO_NEW_HARDWARE_VALIDATION`.

## Installation preview

The invited tester receives a wheel, source distribution,
`release-manifest.json`, and `release-audit.json`. They verify SHA-256 values,
create a fresh virtual environment, install the wheel with `--no-deps`, run
`pip check`, confirm `0.1.0b1`, and execute the synthetic demo. The exact
beginner workflow is in [Installation](INSTALLATION.md) and
[User testing](USER_TESTING_GUIDE.md).

## Important limitations

- no configurable AFE hardware has been assembled or measured by this beta;
- simulation and software PASS results are not bench measurements;
- real serial support is optional and excluded from the default tester path;
- macOS and long-duration physical transport operation are not yet verified;
- firmware, laboratory-instrument automation, and production qualification are
  outside this beta;
- the owner-selected MIT License is included; release publication remains
  a separate decision;
- legacy commits contain de-identified-history review items; publishing the
  complete Git history requires an owner decision about history remediation.

See [Known limitations](KNOWN_LIMITATIONS.md) for the maintained list.

## Owner decisions still required

The owner must separately review the exact commit, branch target, hashes, CI
URL, known limitations, history audit, repository visibility, license state,
release notes, and feedback disposition before any merge, tag, pre-release, or
public portfolio claim. `1.0.0` is not authorized by this draft.
