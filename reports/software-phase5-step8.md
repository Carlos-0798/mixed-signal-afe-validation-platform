# Software Phase 5 Step 8 Verification Report

**Date:** 2026-08-31<br>
**Status:** PASS — Software Phase 5 closed as Software Beta<br>
**Evidence class:** HOST_TEST / SYNTHETIC / repository-external package installation<br>
**Physical serial or hardware operation:** none<br>
**Verified AFE bench-performance claims:** 0<br>
**Implementation commit:** `f77ff1b`

## Outcome

Software Phase 5 is complete at 8/8 checkpoints. The product-facing Python
imports, schema versions, CLI commands/options, exit codes, dataclass and
function shapes, serialized report/demo fields, worker states, error families,
and user-issue mappings are now protected by an executable golden contract.

The repository then passed its complete host-software quality gate, built an
sdist and wheel in an isolated build environment, and installed that wheel into
two fresh short-path environments outside the repository:

- a base environment with no pyserial dependency; and
- a `[serial]` environment with pyserial 3.5.

The base installation ran the installed console entry point, generated two
byte-identical 12-file demos in normal and Unicode paths, and launched/closed a
real Windows Tk Dashboard. The serial installation used an injected host
substitute only. It enumerated zero real ports, opened zero ports, and sent zero
application bytes.

This is a Software Beta closure, not a v1.0 release and not hardware evidence.

## Why this checkpoint matters

Earlier steps showed that the product works. Step 8 protects what outside users
can depend on. A golden compatibility contract plays a role similar to a
documented connector pinout: internal implementation may change, but an
existing script, plug-in, report reader, or user workflow must not break
silently.

The external-install tests answer a separate question: does the product work
after packaging, without relying on the repository checkout, editable imports,
or development dependencies? Testing both base and serial extras also proves
that optional hardware integration does not become a mandatory dependency of
the standalone software product.

## Frozen product contract

`phase5-public-api-golden.v1` freezes:

| Contract area | Frozen value |
|---|---:|
| Public namespaces | 4 |
| `analog_validation_app` exports | 164 |
| `analog_validation_app.cli` exports | 13 |
| `analog_validation_app.dashboard` exports | 35 |
| `analog_validation_app.dashboard.app` exports | 8 |
| Schema versions | 14 |
| Enum sets | 10 |
| Dataclass field contracts | 36 |
| Public call signatures | 35 |
| Error inheritance relationships | 24 |
| Exception-to-user-issue examples | 25 |
| CLI command paths | 16 |
| Exit codes | 8 |
| Serialized field groups | 13 |
| Earlier/current golden hashes | 6 |

The executable contract is
`tests/golden/test_phase5_public_api_golden.py`; its inspectable expected data
is `test-data/golden/phase5_public_api.json`. The change and migration policy is
documented in `docs/phase5-public-api.md`.

The freeze also confirms that the product layer exposes no generic hardware
write/control surface. Private implementation details remain free to evolve.

## Quality gates

| Gate | Actual result |
|---|---|
| New Phase 5 public-contract tests | PASS — 15 |
| Complete golden suite | PASS — 154 |
| Full pytest suite | PASS — 2,189; 0 skipped |
| Package statement coverage | PASS — 11,470/11,470; 100% |
| Ruff | PASS — `src`, `tools`, and `tests` |
| mypy | PASS — 191 source/tool/test files |
| Local dependency check | PASS — no broken requirements |
| Phase 1–4 compatibility | PASS — retained by full/golden suites |
| Isolated sdist and wheel build | PASS — version `0.1.0.dev0` |
| Wheel contents | PASS — console metadata, product/demo modules, and all three `py.typed` markers |
| Sdist closure contents | PASS — demo examples, Phase 5 goldens, and public-contract test included |
| Repository-external base installation | PASS |
| Repository-external `[serial]` installation | PASS — pyserial 3.5 |
| Installed base headless import | PASS — neither `tkinter` nor `serial` loaded |
| Installed CLI version/profiles/demo | PASS |
| Installed normal/Unicode demo comparison | PASS — 12 files each, byte-identical |
| Installed real Windows Dashboard launch/close | PASS — safe idle close |
| Serial-extra host substitute | PASS — zero real discovery/open/write |
| Physical COM/MSP430/instrument/AFE test | NOT RUN |

One first full-suite run encountered a transient Tk resource-read error and
honestly reported one skipped test. A direct real-Tk smoke then succeeded, all
three accessibility scaling cases passed, and the complete formal suite was
rerun successfully with 2,189 passed and zero skipped. Only the final complete
run is used as the Phase 5 exit gate.

## Build artifacts

Generated artifacts are local verification outputs and are not committed
release binaries.

| Artifact | Size | SHA-256 |
|---|---:|---|
| `mixed_signal_afe_validation_platform-0.1.0.dev0-py3-none-any.whl` | 246,532 bytes | `25ca6a8465aa3010f749eb7d8e48eb029ff432730d67f3ca16d2b4c61ecba681` |
| `mixed_signal_afe_validation_platform-0.1.0.dev0.tar.gz` | 448,950 bytes | `5d3ff5b51b9b07b7cc305560bf6c74eae244272c69f352b4f4e33942528d079a` |

## Repository-external installation matrix

### Base installation

The base wheel was installed with `--no-deps` in a fresh short-path virtual
environment outside the repository. `pip check` passed. Importing the product
did not import Tkinter or pyserial, which proves that CLI/core use remains
headless and driver-independent.

The installed console entry point then:

- returned the exact product/version JSON;
- returned the reviewed AFE and independent MSP430 profile catalog;
- generated one demo in a normal path and one in a Unicode path;
- produced exactly 12 files in each location;
- produced equal relative names and SHA-256 values for every file;
- retained the frozen canonical result and manifest hashes; and
- launched a real withdrawn Tk window and closed it after a bounded interval
  with `closed_safely=True`, default Simulator/AFE identity, idle worker state,
  and `NO_NEW_HARDWARE_VALIDATION`.

### Serial-extra installation

The same wheel plus `[serial]` installed pyserial 3.5 and passed `pip check`.
The smoke test injected a synthetic port enumerator into the public receive-only
backend and verified:

- one logical `SYNTHETIC_PORT` substitute was returned;
- no real operating-system inventory was requested;
- no port was opened;
- no `write()` method exists; and
- the installed CLI still returned the exact product/version contract.

The serial extra therefore proves packaging and extension-boundary behavior
only. It adds no current-board or physical-UART evidence.

## Safety, privacy, and evidence boundary

- The connected MSP430 was not enumerated, opened, read, reset, flashed,
  written, or otherwise operated.
- No physical COM port, AFE, ADC, DAC, comparator, breadboard, wiring,
  instrument, supply, or school laboratory resource was accessed.
- Simulator and demo values retain `SYNTHETIC`; compatibility tests retain
  `HOST_TEST`.
- The earlier Phase 4 five-frame result remains a separate narrow
  `BENCH_CONTROLLER` UART/Profile record and was not repeated or broadened.
- A software `PASS` means a fixed software model met its declared criteria. It
  does not establish physical gain, offset, saturation, cutoff, hysteresis,
  protection, ADC/DAC accuracy, bandwidth, noise, safety, or reliability.
- The AFE hardware has not been built or bench-validated; verified AFE hardware
  performance claims remain zero.

## Phase 5 exit decision

All Phase 5 exit gates are satisfied. The safe maturity statement is:

> Analog Validation Studio is a host-verified Software Beta with a stable
> product contract, deterministic offline demo, installable CLI, local
> Dashboard, evidence-aware reports, and optional receive-only serial extension
> boundary.

It is not yet safe to call the project v1.0, production-ready, cross-platform
release-validated, long-duration serial-validated, or physical-AFE validated.

## Next phase

Software Phase 6 owns release engineering: hosted CI, clean-environment and
supported-Python matrix, release-candidate versioning, installation/user
documentation audit, privacy/licensing/publication review, and an owner-approved
GitHub release decision. Real COM reliability and future AFE hardware remain
separately authorized evidence tracks; neither is required to preserve this
software-only product baseline.
