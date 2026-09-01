# Open-source reference review

**Review date:** 2026-09-01<br>
**Scope:** architecture and extension research only<br>
**Runtime dependency added:** none<br>
**Third-party source copied:** none

## Why this review exists

Analog Validation Studio must remain an independent, controller-neutral product
while allowing future AFE controllers, MSP430 peers, serial profiles, and lab
instruments. Mature open-source test projects provide useful design evidence,
but importing a large framework would duplicate the project's frozen analysis,
runner, evidence, and product contracts. The review therefore separates ideas
worth adopting from dependencies that should remain deferred.

Three permissively licensed repositories were downloaded into an external,
untracked reference workspace. Their exact snapshot commits are recorded so a
future review can reproduce what was inspected. The snapshots are not vendored,
packaged, imported, or included in release artifacts.

## Source-level reference snapshots

| Project | Snapshot | License | Strongest relevance | Decision |
|---|---|---|---|---|
| [OpenHTF](https://github.com/google/openhtf) | `f77722967bc97b0366f7d518c2f88556cf414c3a` | Apache-2.0 | phases, measurements, hardware plugs, setup/teardown, output callbacks | Reference its lifecycle and result-separation concepts; do not add it as a dependency because this product already owns typed runners and evidence semantics |
| [PyMeasure](https://github.com/pymeasure/pymeasure) | `68bd427d69620e02ce887495851e3fee812f6dd1` | MIT | adapter/instrument separation, command validation, experiment procedures and results | Use as the primary future SCPI-instrument design reference; keep instrument drivers outside the formal core |
| [PyVISA](https://github.com/pyvisa/pyvisa) | `e3faa8e1d2ddeb754aad223d4a6d7b68f8cc687c` | MIT | replaceable VISA backends and GPIB/RS232/Ethernet/USB resource abstraction | Consider as an optional transport extra only after a real instrument and safe command subset are selected |

## Additional projects reviewed without vendoring

| Project | License | Potential future use | Current decision |
|---|---|---|---|
| [labgrid](https://github.com/labgrid-project/labgrid) | LGPL-2.1-or-later | remote board reservation, power/reset, console and multi-host HIL | Defer until the product actually needs shared remote fixtures; its distributed infrastructure is unnecessary for a local-first beta |
| [OpenTAP](https://github.com/opentap/opentap) | MPL-2.0 | test-step sequencing, result handling and package/plugin ecosystem | Architecture reference only; .NET runtime and package model would duplicate the Python product layer |
| [pytest-embedded](https://github.com/espressif/pytest-embedded) | repository/package-specific, primarily MIT | pytest fixtures for serial/JTAG/QEMU/board services | Do not install now; its strongest integrations are ESP-focused and automatic flashing conflicts with the current receive-only safety boundary |
| [MSPDebug](https://github.com/dlbeer/mspdebug) | GPL-2.0-or-later | MSP430 debug/program/simulation tooling | Keep separate from Analog Validation Studio; programming and reset operations require a device-specific approved procedure |

## Findings applied now

1. **Capability before I/O.** A selected source or future instrument must declare
   identity and capabilities before a workflow can consume data or request an
   output. This matches the current `DeviceAdapter` and preflight design.
2. **Lifecycle ownership.** Setup, execution, cleanup, and evidence publication
   remain distinct. Cleanup failure cannot be converted into PASS.
3. **Transport is not measurement meaning.** A future PyVISA/SCPI backend should
   move bytes and resource operations only; profile/driver code maps instrument
   meaning, and analysis remains transport-independent.
4. **Optional integrations stay optional.** No serial, GUI, VISA, board SDK, or
   third-party test framework becomes a dependency of the base wheel.
5. **One environment diagnostic.** `tools.dev_environment_audit` now reports
   required versus optional host capabilities without opening hardware or
   leaking absolute paths.

## Deferred plugin contract

Python plugin discovery normally imports and executes third-party code. It is
therefore a code-execution boundary, not merely a convenience feature. Before a
future `instrument-provider.v1` or `device-provider.v1` registry is implemented,
the project should require:

- a versioned, non-executable metadata manifest;
- exact provider identity, supported schema/API versions, and capabilities;
- explicit user selection rather than automatic hardware guessing;
- package name/version/hash and license provenance in the run record;
- an allowlist or equivalent trust decision before import;
- contract tests for connect/read/output/safe-shutdown/cleanup behavior;
- bounded errors and deterministic cleanup when import or initialization fails;
- a decision on in-process versus isolated-process execution;
- compatibility and threat-model review before changing the frozen public API.

Until those conditions are designed and approved, an external adapter should
use the documented public Python API directly, as demonstrated by the existing
public-adapter example. "Plugin-ready" means the architecture has a clean
boundary; it does not mean unreviewed packages may execute automatically.

## License and attribution boundary

The reviewed repositories remain under their own licenses and copyrights. No
third-party implementation was copied, translated, vendored, or redistributed,
so this review does not add a runtime dependency or a release notice. If future
work incorporates source rather than independently implementing an interface,
the exact files, license obligations, modifications, and notices must be reviewed
before the change enters Git history or a release artifact.

## Result

The current architecture is directionally consistent with mature test systems:
replaceable hardware boundaries, explicit test phases/workflows, typed
measurements, bounded lifecycle ownership, and separate result publication. The
next useful extension is a narrowly scoped optional instrument adapter after an
actual supported instrument is selected—not adoption of a second orchestration
framework.
