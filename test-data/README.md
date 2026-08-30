# Test data

No bench data exists. Generated files must include `source=SYNTHETIC`; future measurements must include the hardware, wiring, instrument, conditions, timestamp, and raw values.

Golden compatibility data:

- `golden/crc16_ccitt_false.json` freezes the CRC algorithm vectors;
- `golden/afe_v1_valid.csv` freezes 20 valid AFE v1 wire records;
- `golden/afe_v1_invalid.csv` stores Base64-encoded rejected records and their expected error families;
- `golden/expected_frames.json` freezes the model meaning of every valid wire record.
- `golden/csv_replay_v1_valid.csv` freezes five complete Replay v1 records and an explicit END count;
- `golden/csv_replay_v1_invalid.json` freezes rejected schema/semantic mutations and their stable error families.
- `golden/phase2_public_api.json` freezes Phase 2 imports, schemas, enums, signature shapes, error bases, and replay hashes;
- `golden/phase2_workflow_v1.json` freezes one shared Simulator/CSV/UNSUPPORTED workflow meaning end to end.
- `golden/phase3_public_api.json` freezes the Phase 3 public imports, schemas, enums, signature shapes, error bases, constants, and golden-file hashes;
- `golden/phase3_dc_sweep_input_v1.json` is a fixed `SYNTHETIC` DC input whose accepted points have gain 2 and offset 12 mV while one point is explicitly high-saturation excluded;
- `golden/phase3_dc_sweep_result_v1.json` freezes the exact structured DC result for that input;
- `golden/phase3_hysteresis_result_v1.json` freezes an exact `SYNTHETIC` result with 1750 mV rising threshold, 1550 mV falling threshold, and 200 mV width.

These files verify host-software compatibility only. They are not measurements and carry no BENCH evidence claim.
