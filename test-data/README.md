# Test data

No bench data exists. Generated files must include `source=SYNTHETIC`; future measurements must include the hardware, wiring, instrument, conditions, timestamp, and raw values.

Golden compatibility data:

- `golden/crc16_ccitt_false.json` freezes the CRC algorithm vectors;
- `golden/afe_v1_valid.csv` freezes 20 valid AFE v1 wire records;
- `golden/afe_v1_invalid.csv` stores Base64-encoded rejected records and their expected error families;
- `golden/expected_frames.json` freezes the model meaning of every valid wire record.
- `golden/profile_neutral_envelope_v1.json` freezes AFE-shaped and MSP430-shaped
  token/CRC records at the envelope layer only. It does not claim MSP430 business
  parsing, serial I/O, or hardware validation.
- `golden/msp430_equipment_health_v1.json` freezes 10 valid and 11 invalid
  repository-owned business-profile records derived from the peer product's
  public UART Protocol v1 contract at commit `151fdcfa60661bce1ba04af13c1d3509706f7d4a`;
  its scope explicitly excludes peer runtime code, serial I/O, and inherited
  hardware evidence.
- `golden/csv_replay_v1_valid.csv` freezes five complete Replay v1 records and an explicit END count;
- `golden/csv_replay_v1_invalid.json` freezes rejected schema/semantic mutations and their stable error families.
- `golden/phase2_public_api.json` freezes Phase 2 imports, schemas, enums, signature shapes, error bases, and replay hashes;
- `golden/phase2_workflow_v1.json` freezes one shared Simulator/CSV/UNSUPPORTED workflow meaning end to end.
- `golden/phase3_public_api.json` freezes the Phase 3 public imports, schemas, enums, signature shapes, error bases, constants, and golden-file hashes;
- `golden/phase3_dc_sweep_input_v1.json` is a fixed `SYNTHETIC` DC input whose accepted points have gain 2 and offset 12 mV while one point is explicitly high-saturation excluded;
- `golden/phase3_dc_sweep_result_v1.json` freezes the exact structured DC result for that input;
- `golden/phase3_hysteresis_result_v1.json` freezes an exact `SYNTHETIC` result with 1750 mV rising threshold, 1550 mV falling threshold, and 200 mV width.
- `golden/phase4_public_api.json` freezes seven Phase 4 namespaces, schemas,
  profile identities, enums, signatures, error bases, and protocol/composite
  fixture hashes.
- `golden/phase4_composite_v1.json` freezes exact AFE and MSP430 in-memory
  external-backend → SerialSession → profile → receive-only SerialAdapter →
  ReadWorkflow results, including sequence wrap, CRC rejection, sentinels,
  provenance, and no-write behavior.
- `golden/phase5_human_reports_v1.json` freezes exact sizes and SHA-256 values
  for text, Markdown, HTML, SVG, and manifest artifacts rendered from the
  standard synthetic DC and hysteresis results. It verifies deterministic
  presentation and explicitly adds no hardware evidence.
- `golden/phase5_demo_v1.json` freezes the exact 12-file deterministic
  portfolio-demo output, including workflow results, human reports, artifact
  hashes, limitations, and the explicit `SYNTHETIC`/`HOST_TEST` boundary.
- `golden/phase5_public_api.json` freezes the Phase 5 product imports, schema
  versions, enums, dataclasses, signatures, errors, user-issue mappings, CLI
  commands/options, exit codes, serialized fields, stable constants, and six
  earlier/current golden-manifest hashes.

These files verify host-software compatibility only. They are not measurements and carry no BENCH evidence claim.
