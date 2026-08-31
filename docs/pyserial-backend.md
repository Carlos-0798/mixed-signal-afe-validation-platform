# Optional pyserial Backend and Receive-Only HIL

## Purpose

`analog_validation_pyserial` is the optional operating-system integration for
real serial ports. The formal `analog_validation` core still uses only the
Python standard library, so simulation, CSV replay, analysis, and report code
do not require pyserial or a connected controller.

This separation is important for a reusable product:

```text
pyserial / Windows COM
        ↓
PySerialBackend                    optional OS integration
        ↓
SerialSession                      bounded bytes, timeout, close
        ↓
Msp430HealthV1SerialProfile        CRC, fields, sequence, sentinels
        ↓
SerialAdapter → ReadWorkflow       controller-neutral product API
```

The operating-system backend does not parse MSP430 or AFE fields. Conversely,
the profiles and workflows do not import pyserial or know that `COM4` exists.

## Installation

Base software without physical serial support:

```powershell
python -m pip install mixed-signal-afe-validation-platform
```

Optional real-port support:

```powershell
python -m pip install "mixed-signal-afe-validation-platform[serial]"
```

For repository development:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,serial]"
```

The tested optional dependency range is `pyserial>=3.5,<4`. Importing
`analog_validation_pyserial` does not import pyserial immediately. If a caller
actually requests discovery/open without the extra installed, it receives the
typed `PySerialUnavailableError` and an installation hint.

## Receive-only contract

`PySerialBackend` exposes only:

- logical port discovery;
- open with one immutable `SerialConnectionSettings` value;
- one bounded read with a finite timeout;
- idempotent close.

It deliberately has no `write()` method and never exposes its private pyserial
object. Software and hardware flow control are disabled. The port object is
created with `port=None`, DTR and RTS are requested inactive, and only then is
the selected logical port opened.

This proves that this product path does not call pyserial's application-data
write API. It does **not** prove that every operating system, USB bridge, or
driver can open a port without a momentary RTS/DTR transition. The pyserial
documentation warns that some drivers may activate those lines automatically
at open. A future device that uses control lines for reset/boot selection needs
a separate electrical review.

Port discovery retains only the logical port and bounded display description.
Hardware IDs and USB serial numbers are not read into the product inventory.

## MSP430 passive HIL tool

The repository-owned HIL entry point requires an explicit port and never uses
`COM4` as a library default:

```powershell
.\.venv\Scripts\python.exe -m tools.msp430_read_only_hil `
  --port COM4 `
  --frames 5 `
  --read-timeout-seconds 0.25 `
  --max-polls-per-operation 20
```

It performs read-only discovery and then runs unsolicited telemetry through
the real backend, `SerialSession`, strict MSP430 profile, `SerialAdapter`, and
the unchanged `ReadWorkflow`. It does not send `PING`, `STS`, `CFG`, `CMD`, or
any other bytes; it does not flash firmware or change FRAM.

Evidence is written below the Git-ignored `work/evidence/` directory. Each file
uses `msp430-receive-only-hil.v1`, contains raw ASCII and SHA-256 per record,
CRC/profile outcomes, sequence/uptime, raw sentinels/faults, derived
Measurements, timeout/lifecycle counters, and explicit claim limitations. The
writer uses create-new mode and refuses to overwrite an earlier capture.

## Legacy heartbeat versus Protocol v1

The peer controller's published Protocol v1 says CRC-protected production
records share the UART with temporary human-readable bring-up lines. Current
firmware emits one `HB ...` line immediately before each `TEL,...` frame.

The core Protocol v1 parser remains strict: `HB` has no CRC, is not a protocol
message, and remains a retained `REJECTED` raw event. The HIL evidence layer may
classify only the exact documented heartbeat syntax as an out-of-profile
diagnostic. It separately requires its sequence and uptime to match a captured
telemetry frame. Malformed, unaligned, or any other unprotected line remains an
anomaly; the parser is never relaxed to accept it as telemetry.

## Evidence boundary

A successful capture supports only this claim:

> A physical controller on the selected port emitted unsolicited records that
> this repository's frozen MSP430 Protocol v1 compatibility path received,
> CRC-checked, sequence-checked, mapped, and consumed without sending command
> bytes.

It does not prove:

- the exact flashed firmware version, because passive Protocol v1 telemetry has
  no firmware-version field;
- AFE gain, cutoff, hysteresis, saturation, ADC accuracy, or electrical range;
- DS18B20, NTC, INA219, fan, MOSFET, external 5 V, or physical wiring;
- disconnect recovery when no disconnect was intentionally induced;
- that `BENCH_CONTROLLER` Measurements are trustworthy external-sensor readings
  when the controller itself reports missing/fault sentinels.

The accepted Step 7 evidence and complete limitations are summarized in
[`reports/software-phase4-step7.md`](../reports/software-phase4-step7.md).
