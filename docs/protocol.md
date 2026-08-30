# AFE UART CSV protocol

Software Phase 1 Step 5 已将共享 CRC 和有界 ASCII framing 迁移到正式 `analog_validation.protocol` 包。实现边界、错误分类和初学者说明见 `docs/framing-and-crc.md`。本文后续的 telemetry/command 字段仍是 Phase 0 业务形状；它们将在 Step 6 进入版本化 AFE v1 profile。

## Transport

- UART: 115200 baud, 8 data bits, no parity, 1 stop bit.
- Encoding: printable 7-bit ASCII.
- Record terminator: LF (`\n`); a received CRLF is accepted.
- Maximum serialized record: 128 bytes including the terminator.
- Namespace: every record begins with `AFE`.
- CSV is deliberately restricted: fields may contain only the documented tokens and integers; quoting, embedded commas, and embedded whitespace are not supported.

## CRC-16/CCITT-FALSE

| Parameter | Value |
|---|---|
| Width | 16 bits |
| Polynomial | 0x1021 |
| Initial value | 0xFFFF |
| RefIn / RefOut | false / false |
| XorOut | 0x0000 |
| Check for ASCII `123456789` | 0x29B1 |

The CRC covers the ASCII bytes from `AFE` through the last data field, including intervening commas but excluding the comma before the CRC, the four CRC hex characters, CR, and LF.

Example payload and framing:

```text
payload = AFE,TEL,120,45120,0,500,2487,4974,1,0000
wire    = payload + , + CRC16(payload) + \n
```

## Telemetry

```text
AFE,TEL,<seq>,<time_ms>,<channel>,<input_mv>,<output_mv>,<gain_milli>,<threshold>,<fault_hex>,<crc16>\n
```

| Field | Phase 0 range/format |
|---|---|
| seq | unsigned 16-bit decimal, wraps modulo 65536 |
| time_ms | unsigned 32-bit decimal, wraps modulo 2^32 |
| channel | unsigned 8-bit decimal |
| input_mv, output_mv | signed 16-bit decimal; negative values can describe detected invalid conditions but are not safe hardware inputs |
| gain_milli | unsigned 16-bit decimal; 1000 means x1.000 |
| threshold | `0` or `1` |
| fault_hex | exactly four uppercase hexadecimal digits |
| crc16 | exactly four uppercase hexadecimal digits |

## Commands

```text
AFE,CMD,<seq>,GET,STATUS,<channel>,<crc16>
AFE,CMD,<seq>,SET,GAIN,<channel>,<gain_id>,<crc16>
AFE,CMD,<seq>,SET,FILTER,<channel>,<filter_id>,<crc16>
AFE,CMD,<seq>,RUN,DC_SWEEP,<channel>,<crc16>
AFE,CMD,<seq>,RUN,HYSTERESIS,<channel>,<crc16>
AFE,CMD,<seq>,RUN,FREQUENCY_SWEEP,<channel>,<crc16>
AFE,CMD,<seq>,SAVE,CALIBRATION,<crc16>
```

当前 parsing validates framing, CRC, types, lengths, and the listed command shapes. Firmware acknowledgements, timeout policy, duplicate-sequence handling, and fault-bit assignments remain later-phase decisions.

The protocol belongs to the AFE product, not to any MSP430, STM32, or RP2040 board. Phase 1 must add a versioned capability exchange before host software enables optional ADC, DAC, PWM, edge-capture, or calibration commands. Board-specific pin numbers and SDK names are never transmitted as part of this public protocol.

## Parser rejection rules

Reject the complete record if it is non-ASCII, overlong, missing required fields, contains unsupported message/command tokens, has malformed numeric or hexadecimal fields, violates a field range, or has a CRC mismatch. A caller reading a byte stream must buffer only through the length limit and discard input through the next LF after an overlong record.
