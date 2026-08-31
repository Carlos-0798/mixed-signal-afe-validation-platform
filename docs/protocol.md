# AFE UART CSV Protocol

This is the current public protocol summary. The only supported AFE business profile is versioned `AFE,1,...`; the Phase 0 unversioned façade was retired at the end of Software Phase 1.

Detailed field and capability semantics are defined in [AFE v1 Profile](afe-v1-profile.md). CRC and envelope behavior are defined in [CRC and Framing Core](framing-and-crc.md), and legacy/canonical channel names are defined in [AFE Channel Naming Mapping v1](afe-channel-mapping.md).

## Transport target

- UART target: 115200 baud, 8 data bits, no parity, 1 stop bit;
- encoding: printable 7-bit ASCII;
- record terminator: LF; CRLF is accepted on input;
- maximum serialized record: 128 bytes including the terminator;
- AFE namespace: every AFE business payload begins with `AFE`;
- restricted CSV: no quoting, embedded commas, or embedded whitespace on the wire.

These are software protocol definitions. No physical UART link or baud-rate tolerance has been verified.

## CRC-16/CCITT-FALSE

| Parameter | Value |
|---|---|
| Width | 16 bits |
| Polynomial | `0x1021` |
| Initial value | `0xFFFF` |
| RefIn / RefOut | false / false |
| XorOut | `0x0000` |
| ASCII `123456789` check | `0x29B1` |

The CRC covers the ASCII payload from `AFE` through its final data field, including commas between fields. It excludes the comma before the CRC, the four CRC characters, CR, and LF.

## Versioned message families

```text
AFE,1,TEL,<seq>,<time_ms>,<channel>,<input_mv>,<output_mv>,<gain_milli>,<threshold>,<fault_hex>,<crc16>
AFE,1,CMD,<seq>,...,<crc16>
AFE,1,CAP_REQ,<seq>,<crc16>
AFE,1,CAP,<seq>,DEVICE,...,<crc16>
AFE,1,CAP,<seq>,CHANNEL,...,<crc16>
AFE,1,CAP,<seq>,END,<entry_count>,<crc16>
```

The profile supports status/digital reads, gain/filter configuration, analog/PWM stimulus requests, DC/hysteresis/frequency test requests, calibration save, safe shutdown, and multi-record capability exchange. A command shape existing on the wire does not authorize it: a future adapter must still enforce configuration, advertised capability, safe range, and shutdown gates.

## Golden compatibility contract

- `test-data/golden/afe_v1_valid.csv` freezes 20 valid records;
- `test-data/golden/expected_frames.json` freezes their model meanings;
- `test-data/golden/afe_v1_invalid.csv` freezes 9 rejected inputs and error families;
- `tests/golden/test_protocol_golden.py` verifies exact parse/re-encode compatibility;
- `tests/integration/test_synthetic_telemetry_pipeline.py` verifies a deterministic 100-frame synthetic pipeline.

The synthetic stream is labeled `SYNTHETIC`; its derived Measurements are explicitly checked to be non-bench evidence.

## Rejection rules

A complete record is rejected for non-ASCII data, excessive length, invalid namespace/version/type, missing or extra fields, invalid tokens, malformed CRC/fault fields, CRC mismatch, unknown enum/command/capability bits, or out-of-range values.

Software Phase 4 Steps 1–6 now provide a profile-neutral bounded byte-stream state machine, a namespace-neutral ASCII token/CRC envelope, a driver-neutral host-tested serial lifecycle, bounded memory-only raw events, independent AFE v1 plus read-only MSP430 Equipment Health v1 serial profiles, and one receive-only SerialAdapter composition into the shared workflow. The existing AFE framing API is a compatibility wrapper over the neutral envelope. All 20 valid plus 9 invalid AFE cases retain their exact contracts; 10 valid plus 11 invalid repository-owned MSP430 fixtures freeze its separate `TEL/ACK/STS/CFG/LOG`, 32-bit sequence, sentinel/fault, CRC, field, state, and limit behavior. Real serial streaming still requires a concrete OS backend and separate HIL evidence; the two business protocols remain distinct.

## Independence boundary

The AFE protocol belongs to the independent AFE validation product, not to MSP430, STM32, RP2040, or any particular instrument. MSP430 Equipment Health Controller compatibility uses its own read-only v1 profile and does not change AFE v1 semantics; the future live adapter and HIL work will consume that separate profile rather than merge the products.
