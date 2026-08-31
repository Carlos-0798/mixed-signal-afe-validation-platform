# Software Phase 5 Step 3 Report

**Date:** 2026-08-31<br>
**Milestone:** stable product application services and CLI workflows<br>
**Evidence class:** HOST_TEST, SYNTHETIC, and CSV_REPLAY<br>
**Physical port/display/hardware operation:** none<br>
**Verified AFE hardware performance claims:** 0

**Implementation commit:**
`ee16652328436a9ef28846cf9c9676e647c4bcfa`

## Outcome

Software Phase 5 Step 3 is complete; Phase 5 implementation is now 3 of 8
checkpoints. An installed `analog-validation` command can run bounded Simulator
and CSV Replay reads, formal DC evaluation, formal hysteresis evaluation, and
structured result export through the same application services and worker that
a later Dashboard will use.

`ports` is discovery-only. `observe` requires an exact port, profile, channel,
unit, record bound, and explicit receive-only confirmation. Serial integration
tests used a memory backend with a write trap; no physical COM port was
enumerated or opened during this checkpoint, and the connected MSP430 was not
read, reset, flashed, or otherwise touched.

## Delivered behavior

| Component | Delivered behavior |
|---|---|
| explicit factories | Simulator, projected CSV Replay, lazy optional serial discovery, and exact AFE/MSP receive-only adapter construction |
| application services | shared read, DC, and hysteresis orchestration above frozen workflow/analysis/criteria/export APIs |
| result handoff | thread-safe single publication only after a safe service checkpoint |
| CLI | human and `product-cli-output.v1` JSON views for simulate/replay/observe plus stable reserved commands |
| output safety | atomic JSON/CSV result export, default no-overwrite, size and SHA-256 reporting |
| status semantics | worker state, product status, and engineering outcome remain separate |
| failure semantics | stable exits 0/1/2/3/4/5/70/130; expected errors have what/cause/safe-next-step and no default traceback |
| cancellation | completion-event wait, 50 ms interrupt polling, cooperative stop, bounded cleanup, and exit 130 |

The product services do not reimplement engineering math. They call
`run_read_workflow`, `analyze_*`, `evaluate_*`, and `build_*_export`. Simulator
DC/hysteresis use deterministic read-only observations followed by offline
analysis; they do not invoke an output runner or claim to stimulate a physical
circuit.

## Executed verification

| Gate | Actual result |
|---|---|
| Phase 5 focused product tests | PASS — 336 tests |
| Product package coverage | PASS — 1,538/1,538 statements, 100% |
| Full pytest suite | PASS — 1,854 tests |
| Formal + optional + product coverage | PASS — 8,863/8,863 statements, 100% |
| Phase 1–4 golden compatibility | PASS — unchanged within the full suite |
| Ruff rule check | PASS — full repository |
| Ruff formatting for Step 3 changed Python files | PASS |
| mypy on `src`, `tools`, and `tests` | PASS — 158 files |
| Patch whitespace | PASS |
| Isolated sdist/wheel build | PASS — `0.1.0.dev0` |
| Wheel archive inspection | PASS — 80 files, product CLI and three `py.typed` markers present, one console entry point |
| Repository-external base-wheel install | PASS — version, Simulator read/DC/hysteresis, Replay read, result-file publication |
| Missing optional serial dependency | PASS — `ports --json` returned 4 / `OPTIONAL_DEPENDENCY` before discovery |
| Reserved command honesty | PASS — `report --json` returned 4 / capability unavailable |
| Subprocess interrupt | PASS — main-thread `KeyboardInterrupt` produced exit 130, `CANCELLED`, cleanup, and no traceback |
| Physical serial, GUI, or AFE test | NOT RUN |

The repository-wide `ruff format --check .` also reports 76 historical files
that would be restyled by the currently installed Ruff formatter. They were not
mechanically reformatted in this feature commit because that would obscure the
Step 3 review. Ruff's rule checker passed, and every Step 3 Python file passed
the formatter. Whole-repository style normalization remains a separate
maintenance item rather than a hidden green claim.

## End-to-end results

The installed final wheel was executed from
`C:\Users\24046\AppData\Local\Temp\analog-validation-wheel-step3-20260831-c`,
outside the repository:

| Workflow | Result |
|---|---|
| `version --json` | `0.1.0.dev0` |
| `simulate read --samples 3 --json` | `COMPLETED`, 3 SYNTHETIC measurements |
| `simulate dc --points 6 --output ... --json` | engineering `PASS`, result artifact written |
| `simulate hysteresis --json` | engineering `PASS` |
| `replay read ... --samples 2 --json` | source `CSV_REPLAY` |
| `ports --json` without serial extra | exit 4, `OPTIONAL_DEPENDENCY`; no discovery |
| `report --json` | exit 4; reserved Step 4 feature, no fabricated report |

The fresh `simulate dc` JSON artifact was 10,733 bytes with SHA-256
`3A77A24091D517C50DA2F8474FC20A4C3FBCDA9FD7AFC55E7513D27FF5EF2D49`.
The hash identifies this exact run artifact; timestamp and run identity fields
mean it is not presented as a cross-run deterministic hash.

The deterministic Simulator hysteresis integration result retained the formal
mean high threshold 991.5 mV, mean low threshold 916.0 mV, and mean width
75.5 mV. These values are a software model regression, not a measured Schmitt
trigger.

## Build artifacts

| Artifact | Size | SHA-256 |
|---|---:|---|
| `mixed_signal_afe_validation_platform-0.1.0.dev0-py3-none-any.whl` | 189,042 bytes | `92361F2052CAE9EF3531E9724EF7EB206A1A22AF38CEB99733DF7E34CE4EE6F5` |
| `mixed_signal_afe_validation_platform-0.1.0.dev0.tar.gz` | 336,453 bytes | `A8EEA40AB407427DC4B78E582C4F582098BBB0B09D94AB830AC6DAFDE9C49F09` |

Generated archives, temporary environments, and smoke-test outputs are local
verification artifacts and are not committed release binaries.

## Safety and evidence boundary

- Every workflow JSON explicitly says `NO_PERFORMANCE_VALIDATION`.
- Simulator output is deterministic synthetic evidence only.
- Replay output describes the selected file and mapping only.
- Serial factories expose receive-only adapters and no application write API.
- The in-memory MSP430 chain asserted zero backend writes and one deterministic
  close, but did not test an OS driver, USB control lines, firmware identity, or
  electrical behavior.
- A subprocess interpreter interrupt was verified. Windows console-control
  process-group delivery under the desktop test host was not promoted to an
  interactive-terminal guarantee.
- The earlier Phase 4 five-record MSP430 UART result remains a separate narrow
  `BENCH_CONTROLLER` claim; Step 3 did not repeat or broaden it.
- Physical AFE gain, saturation, cutoff, hysteresis, ADC accuracy, wiring,
  protection, and reliability all remain unverified.

## Remaining work and next gate

Step 3 intentionally does not provide human HTML/Markdown reports, plots,
Dashboard state/widgets, the six-step beginner wizard, or the reproducible
portfolio demo. `report`, `dashboard`, and `demo` are visible reserved commands
that fail honestly with exit code 4.

The next checkpoint is Software Phase 5 Step 4 only: build presentation-only
report models, human text/Markdown, deterministic SVG charts, and self-contained
local HTML from finalized result bundles without refitting or changing the
engineering outcome.
