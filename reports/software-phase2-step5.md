# Software Phase 2 Step 5 Report

**Date:** 2026-08-30<br>
**Milestone:** strict immutable CSV Replay v1 schema and parser<br>
**Evidence class:** HOST_TEST<br>
**Hardware used:** none

## Outcome

Software Phase 2 Step 5 is complete. The formal package now defines a bounded `csv-replay.v1` format, immutable record/dataset models, strict in-memory and local-file parsers, and stable replay error families.

The parser establishes whether a local dataset is structurally and semantically complete. It does not yet play records, control timing, expose EOF through an adapter, or convert file rows into current `CSV_REPLAY` Measurements; those are Step 6 responsibilities.

## Frozen format

CSV Replay v1 uses exactly 13 ordered columns and three row types:

1. exact header;
2. one `META` row containing version and dataset identity;
3. zero or more `DATA` rows;
4. one final `END` row declaring the exact DATA count.

Every DATA row has an explicit record/raw-record identity, ISO 8601 UTC timestamp ending in `Z`, channel, value, controlled unit, status, declared source, and canonical quality flags. Record IDs are unique and timestamps are nondecreasing.

The explicit `END` count means a complete empty dataset can be distinguished from a truncated file.

## Immutable public models

- `CsvReplayRecord` validates safe identifiers and reuses formal Measurement consistency rules without exposing the file row as current bench evidence;
- `CsvReplayDataset` freezes records into a tuple, rejects duplicates/time reversal/count mismatches, and can exist only with a matching declared END count;
- `source` becomes `declared_source` in Python to show that spelling is validated but evidence authenticity is not.

## Parser safety controls

- strict UTF-8; BOM, NUL, lone CR, embedded ASCII controls, and malformed CSV are rejected;
- exact header, column count, row order, version, dataset identity, and reserved-empty fields;
- 10 MiB input limit, 100,000 DATA-record limit, and 1,024-character field limit;
- canonical decimal grammar plus explicit `NaN`, `Infinity`, and `-Infinity` tokens;
- strict existing enums for units, status, source, and quality flags;
- safe bounded identifier grammar excludes whitespace, commas, and leading spreadsheet-formula characters;
- `.csv` loader only calls stat/read and does not modify source bytes or metadata;
- no `eval`, `exec`, command processing, code import, or unit/source guessing.

## Stable errors

| Error | Meaning |
|---|---|
| `ReplayError` | base replay access/acceptance failure |
| `ReplayFormatError` | invalid structure or record semantics |
| `ReplayLimitError` | byte, field, or record limit exceeded |
| `UnsupportedReplayVersion` | unsupported replay schema version |

These are separate from serial/wire `ProtocolError` and live-device `AdapterError` families.

## Golden compatibility data

- `csv_replay_v1_valid.csv` freezes five records: valid analog input, saturated output, missing input, non-finite output, and boolean state;
- `csv_replay_v1_invalid.json` freezes eight rejected mutations covering header, version, END count, quality order, missing END, time reversal, duplicate ID, and unknown source;
- all golden content is software fixture data and contains no physical measurement claim.

## Executed verification

| Gate | Result |
|---|---|
| CSV Replay unit tests | PASS — 84 |
| CSV Replay golden tests | PASS — 9 |
| Focused replay module coverage | PASS — 233/233 statements, 100% |
| Full pytest suite | PASS — 545 tests |
| Formal package statement coverage | PASS — 1,841/1,841, 100% |
| Full-repository Ruff | PASS |
| mypy on `src dashboard tools tests` | PASS — 58 source files |
| Local dependency check | PASS — no broken requirements |
| Isolated sdist and wheel build | PASS |
| Replay module in wheel | PASS |
| Replay golden files/tests in sdist | PASS |
| Repository-external wheel install | PASS |
| Installed public replay parser smoke | PASS — complete one-record dataset |
| Installed-package dependency check | PASS — no broken requirements |

## Beginner explanation

Parsing and playback are intentionally separate:

- parsing answers “is this file complete and unambiguous?”;
- playback answers “which record should be returned now, at what speed, and what happens at pause or EOF?”

Combining both immediately would make malformed-file errors, timing behavior, and adapter lifecycle difficult to test independently. Freezing the file contract first gives Step 6 a trusted immutable input.

## Evidence boundary

The parser can confirm that `BENCH_DMM` is a valid source name, but it cannot confirm that a meter existed or that the row was honestly produced. Future replay Measurements must use `CSV_REPLAY` as their current source while retaining original references and declared metadata.

No serial port, controller, ADC, DAC, PWM, instrument, analog component, wiring, voltage, or physical file acquisition was used. `VERIFIED_BENCH` remains zero.

## Next checkpoint

Software Phase 2 Step 6 will implement `CsvReplayAdapter` with sequential reads, speed scaling, pause/resume, explicit EOF, current `CSV_REPLAY` provenance, immutable source preservation, and the same shared read-only adapter contract already used by Simulator.
