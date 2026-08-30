# Shared Read Workflow

**Schema:** `read-workflow.v1`  
**Current evidence:** HOST_TEST / SYNTHETIC / CSV_REPLAY  
**Hardware validation:** none

Software Phase 2 Step 7 adds one read-only application workflow above `DeviceAdapter`. Simulator and CSV Replay now receive the same immutable request and execute through the same `run_read_workflow` function.

## Why this layer exists

An analysis runner should ask for “two mV samples from this analog channel” rather than contain branches such as “if Simulator do this, if CSV do that, if MSP430 do something else.” The adapter handles where data comes from; the workflow handles a complete acquisition attempt.

This separation lets future Serial, MSP430, and instrument adapters join the product by satisfying the public adapter contract. The upper workflow and later analysis do not need board registers, file columns, COM-port details, or vendor SDK calls.

## Versioned request

`ReadWorkflowRequest` contains one or more unique `ChannelReadRequest` values. Each channel request explicitly declares:

- channel name;
- `ANALOG` or `DIGITAL` operation;
- expected `MeasurementUnit`;
- positive integer sample count.

Analog reads cannot use the boolean unit; digital reads must use it. A request is immutable after construction and cannot contain an empty list or duplicate channels.

## Atomic capability preflight

Before the first read, the workflow confirms all requested capabilities:

- required read command;
- analog or digital channel presence;
- analog channel unit declared by its input range.

If any requirement is missing, no read occurs. The result is `UNSUPPORTED`, contains no partial Measurements, and lists stable tokens such as:

```text
command:READ_DIGITAL_STATE
digital-channel:afe.ch0.threshold
analog-unit:afe.ch0.input:mV
```

This prevents a workflow from consuming some source data before discovering that it cannot finish.

## Result states

| Status | Meaning | Engineering PASS? |
|---|---|---|
| `COMPLETED` | Every requested Measurement was acquired | No |
| `UNSUPPORTED` | Capability preflight found a missing command, channel, or unit | No |
| `INCOMPLETE` | Capability existed, but replay reached EOF before all samples were available | No |

`INCOMPLETE` retains any Measurements collected before EOF and lists exact remaining counts, for example `samples:ANALOG:afe.ch0.input:1`. Unexpected communication, CRC, adapter, or programming failures remain typed exceptions and are never relabeled as a capability problem.

These are acquisition states, not `TestRunOutcome.PASS`/`FAIL`. Phase 3 analysis runners must evaluate Measurements against explicit criteria before producing an engineering conclusion.

## Lifecycle ownership

The workflow accepts only a disconnected adapter so ownership is unambiguous. For one call it performs:

```text
DISCONNECTED
  -> connect
  -> confirm capabilities
  -> atomic preflight
  -> read zero or more Measurements
  -> disconnect
DISCONNECTED
```

Disconnect runs after completed, unsupported, incomplete, and exceptional paths. If a caller already owns an active connection, the workflow rejects the call instead of unexpectedly disconnecting someone else's session.

## Public example

```python
from analog_validation import (
    ChannelReadRequest,
    MeasurementUnit,
    ReadOperation,
    ReadWorkflowRequest,
    SimulatorAdapter,
    run_read_workflow,
)

request = ReadWorkflowRequest(
    requirements=(
        ChannelReadRequest(
            "afe.ch0.input",
            ReadOperation.ANALOG,
            MeasurementUnit.MILLIVOLT,
            sample_count=3,
        ),
        ChannelReadRequest(
            "afe.ch0.threshold",
            ReadOperation.DIGITAL,
            MeasurementUnit.BOOLEAN,
        ),
    )
)

result = run_read_workflow(SimulatorAdapter(), request)
assert result.is_completed
assert len(result.measurements) == 4
assert not any(item.is_bench_evidence for item in result.measurements)
```

The identical request can be passed to a CsvReplayAdapter that advertises matching channels and units.

## Current boundary

- no output stimulus is requested or authorized;
- no analysis, calibration, limit evaluation, or PASS/FAIL is performed;
- no serial port, board SDK, controller, instrument, or physical AFE is used;
- software fixture ranges are not validated electrical limits;
- `SYNTHETIC` and `CSV_REPLAY` remain non-bench evidence.
