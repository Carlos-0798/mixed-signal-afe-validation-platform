# Frozen Software Phase 4 Compatibility

**Freeze schema:** `phase4-public-api-golden.v1`<br>
**Composite schema:** `phase4-composite-golden.v1`<br>
**Software evidence:** HOST_TEST<br>
**Separate physical evidence:** narrow Step 7 `BENCH_CONTROLLER` UART capture<br>
**Verified AFE hardware performance claims:** 0

## Why this freeze exists

Software Phase 4 created replaceable serial transport, profile, adapter, and
optional operating-system integration boundaries. Unit tests show that each
piece works today. The Step 8 compatibility freeze answers a different
question: will a future CLI, Dashboard, controller plug-in, or external user
notice if a public name, schema, enum, call shape, error family, protocol
fixture, or representative end-to-end result changes accidentally?

Private implementation details remain free to evolve. An intentional breaking
change must introduce the appropriate new schema/profile version, preserve old
fixtures when compatibility is promised, and document migration. Golden files
must never be rewritten merely to make a regression pass.

## Frozen files

| File | Purpose |
|---|---|
| `test-data/golden/phase4_public_api.json` | Public exports, schemas, constants, enums, signatures, errors, and fixture hashes |
| `test-data/golden/phase4_composite_v1.json` | Exact AFE/MSP430 external-backend → session → profile → adapter → workflow meaning |
| `tests/golden/test_phase4_public_api_golden.py` | Reconstructs and verifies the public manifest |
| `tests/golden/test_phase4_composite_golden.py` | Rebuilds both product chains from public interfaces and compares exact results |

The public manifest hashes four earlier protocol fixtures plus the new
composite fixture. It does not hash itself, avoiding a circular dependency.

## Public surface frozen

The manifest freezes 121 exports across seven explicit namespaces:

- `analog_validation.transport`;
- `analog_validation.protocol.envelope`;
- `analog_validation.protocol.afe_channels`;
- `analog_validation.protocol.msp430_health_v1`;
- `analog_validation.profiles`;
- `analog_validation.serial_adapters`;
- `analog_validation_pyserial`.

It also freezes:

- three schemas: `afe-channel-map.v1`, `serial-profile.v1`, and
  `serial-adapter-config.v1`;
- both serial-profile identities, including 16/32-bit sequence widths and the
  128-byte record limit;
- the frozen MSP430 public-interface commit and raw-event privacy notice;
- 12 enum/flag member sets;
- 21 primary constructor/function parameter shapes;
- 17 transport/profile/optional-backend error inheritance relationships;
- hashes for AFE valid/invalid records, the neutral envelope fixture, the
  independent MSP430 fixture, and the Phase 4 composite fixture;
- implementation ownership inside `analog_validation.*` or
  `analog_validation_pyserial.*` rather than peer-project or Dashboard code;
- absence of a public `write()` method on `PySerialBackend`.

## Exact composite meaning

### AFE host chain

An external structural backend emits one complete capability response, two AFE
telemetry records across the `65535 -> 0` sequence wrap, and one damaged-CRC
record. The frozen chain:

```text
external backend
  -> SerialSession
  -> AfeV1SerialProfile
  -> SerialAdapter
  -> ReadWorkflow
```

must complete with projected `afe.ch0.input` and `afe.ch0.threshold`
capabilities, four `HOST_TEST` Measurements, two in-order telemetry events, one
retained `CrcMismatch` rejection, one open/close lifecycle, and no write
surface.

### MSP430 host chain

The independent MSP430 chain emits one valid telemetry record, one
fault/sentinel record across `4294967295 -> 0`, and one damaged-CRC record. The
frozen result preserves valid 42.1 °C and 5012 mV samples while mapping
`-32768` and INA219-fault zero fields to `None + INVALID + MISSING`. It does not
reinterpret unavailable data as physical zero and does not add any control
capability.

Both composites are deterministic in-memory `HOST_TEST` records. They do not
reuse the Step 7 physical capture and do not claim UART electrical behavior,
sensor operation, or AFE performance.

## External implementation rule

`SerialBackend` is a structural Python protocol. A third-party backend does not
need to inherit an internal base class; it must provide the documented
discovery/open/bounded-read/close methods with compatible types. The golden
test assigns its independent backend to this protocol under mypy and runs it
through the installed product chain. This protects extensibility without
requiring vendor code inside the core package.

## Change procedure

When a Phase 4 golden test fails:

1. inspect the exact export, version, member, signature, error, bytes, or result
   difference;
2. treat unexpected drift as a regression and fix the implementation without
   editing golden data;
3. for an intentional compatible addition, document why old consumers remain
   valid;
4. for an intentional breaking change, add a new schema/profile version and
   migration fixture;
5. review evidence-source and write-surface implications explicitly;
6. regenerate a golden file only after the change is accepted;
7. rerun full tests, 100% package coverage, Ruff, mypy, dependency checks,
   isolated build, and repository-external installations.

## Evidence boundary

The compatibility freeze is software evidence. The earlier Step 7 capture
remains a separate five-record receive-only controller UART result. Neither
result proves the exact flashed firmware, external MSP430 peripherals,
disconnect recovery, long-duration reliability, or any AFE gain, cutoff,
hysteresis, saturation, protection, ADC/DAC, bandwidth, or noise behavior.
