# Test data

No bench data exists. Generated files must include `source=SYNTHETIC`; future measurements must include the hardware, wiring, instrument, conditions, timestamp, and raw values.

Golden compatibility data:

- `golden/crc16_ccitt_false.json` freezes the CRC algorithm vectors;
- `golden/afe_v1_valid.csv` freezes 20 valid AFE v1 wire records;
- `golden/afe_v1_invalid.csv` stores Base64-encoded rejected records and their expected error families;
- `golden/expected_frames.json` freezes the model meaning of every valid wire record.

These files verify host-software compatibility only. They are not measurements and carry no BENCH evidence claim.
