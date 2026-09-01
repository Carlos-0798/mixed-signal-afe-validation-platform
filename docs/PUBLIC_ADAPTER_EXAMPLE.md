# Build a read-only adapter from the public API

## What this proves

An adapter is a small translation layer between a data source and Analog
Validation Studio's stable measurement/workflow contract. The source might
later be a controller, instrument, data-acquisition module, network-isolated
process, or file format. The rest of the product should not need a branch for
every vendor.

The repository example at
[`examples/public_adapter/read_only_voltage_adapter.py`](../examples/public_adapter/read_only_voltage_adapter.py)
uses only Python's standard library and symbols imported directly from the
installed top-level `analog_validation` API. It does not import source-tree
helpers, product internals, a board SDK, pyserial, Tk, or a private module.

## The lifecycle in beginner language

The public `DeviceAdapter` base class owns the safety-relevant order:

1. `connect()` asks the subclass to acquire its resource but authorizes no
   output;
2. `get_capabilities()` requires an explicit channel, unit, safe input range,
   and command list;
3. the shared workflow checks every requested channel before the first read;
4. `read_measurement()` validates channel, unit, type, and evidence source;
5. `disconnect()` runs in a `finally` block even when a read fails.

The example subclass implements only `_connect`, `_disconnect`,
`_get_capabilities`, and `_read_measurement`. These protected hooks are the
documented subclass extension points. It deliberately does not implement
stimulus, generic command, or safe-shutdown output hooks, and its capabilities
advertise only `READ_MEASUREMENT`.

## Run the example

Install the base wheel in a virtual environment, copy the single example file
outside the repository, and run it with that environment's Python:

```powershell
& <venv-python> -I <external-directory>\read_only_voltage_adapter.py
```

Expected JSON includes:

```text
status = COMPLETED
evidence_source = SYNTHETIC
capabilities_read_only = true
output_command_count = 0
measurement_count = 3
connect_count = 1
disconnect_count = 1
connected_after_run = false
application_bytes_written = 0
```

`COMPLETED` means the three requested records were acquired and cleanup
finished. It is not an engineering `PASS`, and `SYNTHETIC` is not physical
bench evidence.

## Adapting a future real source

Keep these boundaries when replacing the deterministic tuple:

- choose the evidence source from what was actually observed; never label
  generated, replayed, or host-only data as `BENCH_*`;
- declare every readable channel and unit, and return exactly that channel,
  unit, and evidence source in each `Measurement`;
- map finite timeouts/end-of-data to a typed bounded behavior;
- release file, driver, socket, or port resources in `_disconnect`;
- add no output capability until a separate design supplies explicit safe
  ranges, owner authorization, and a verified safe-shutdown path;
- keep controller-specific decoding in the adapter/profile, not in the shared
  workflow.

A physical serial adapter additionally requires the optional serial package and
a separately approved device/port procedure. Installing or copying this example
does not authorize hardware discovery, port opening, writes, reset, flashing,
or measurement claims.

## How the release gate prevents a false proof

The release verifier copies this file into a temporary directory outside the
repository and runs it with the freshly installed base wheel using Python
isolated mode (`-I`). That mode ignores `PYTHONPATH` and user-site packages.
The gate asserts the exact lifecycle, provenance, measurement count, read-only
capability, zero-write, and cleanup JSON before a candidate can be marked PASS.
