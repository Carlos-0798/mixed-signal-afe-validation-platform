# CSV Replay v1 Format

CSV Replay v1 is the immutable local-file interchange format used by the future `CsvReplayAdapter`. Step 5 defines and validates complete datasets; it does not yet play, pause, time-scale, or convert rows into live adapter Measurements.

## Why the format is strict

A test platform must not guess whether `3.3` means volts, millivolts, ADC counts, or a ratio. It must also distinguish what a file claims from what the current software run actually observed. CSV Replay v1 therefore requires explicit units, UTC timestamps, status, declared source, quality flags, identifiers, schema version, and a terminating record count.

## Fixed columns

The first row must match this order exactly:

```text
row_type,schema_version,dataset_id,record_id,raw_record_id,timestamp_utc,channel,value,unit,status,source,quality_flags,record_count
```

Every logical row has exactly 13 fields. Columns cannot be added, removed, renamed, or reordered under `csv-replay.v1`.

| Column | Meaning |
|---|---|
| `row_type` | `META`, `DATA`, or `END` |
| `schema_version` | Exactly `csv-replay.v1` |
| `dataset_id` | Stable identifier repeated on every row |
| `record_id` | Unique identity of a DATA record |
| `raw_record_id` | Identity of the original record before a derived transformation |
| `timestamp_utc` | ISO 8601 UTC time ending in `Z` |
| `channel` | Controller-neutral channel name |
| `value` | Canonical decimal, empty missing value, or explicit non-finite token |
| `unit` | Existing `MeasurementUnit` value such as `mV` or `bool` |
| `status` | `VALID`, `SUSPECT`, or `INVALID` |
| `source` | Source declared by the file; this is not independently authenticated evidence |
| `quality_flags` | Empty or pipe-separated flags in enum order |
| `record_count` | Used only by `END` and required to match DATA rows |

## Row sequence

```text
exact header
META,csv-replay.v1,<dataset_id>,<ten empty fields>
zero or more DATA rows
END,csv-replay.v1,<same dataset_id>,<nine empty fields>,<count>
```

- `META` must be the second row and contains only version and dataset ID.
- Every middle row must be `DATA` and repeat the same version and dataset ID.
- `END` must be last and its count must equal the number of DATA rows.
- An empty dataset is valid only as header + META + `END ... record_count=0`.
- Record IDs must be unique and timestamps must be nondecreasing.

The explicit END row distinguishes a complete zero-record dataset from a truncated or partially written file.

## Value and quality consistency

Normal finite numbers use a locale-independent decimal grammar. Commas, underscores, leading plus signs, and implicit units are not accepted. `NaN`, `Infinity`, and `-Infinity` are the only non-finite spellings and require `INVALID` plus `NON_FINITE`. An empty value requires `INVALID` plus `MISSING`.

Quality flags are joined with `|` in the declaration order of `QualityFlag`. Duplicates, unknown names, empty tokens, and noncanonical order are rejected. The existing immutable Measurement rules still apply: `VALID` cannot carry flags and `SUSPECT`/`INVALID` require an explanatory flag.

## Identifier and text safety

Dataset, record, raw-record, and channel identifiers:

- start with an ASCII letter or digit;
- are at most 128 characters;
- use only letters, digits, `.`, `_`, `:`, `/`, and `-`.

This excludes leading spreadsheet-formula characters and ambiguous whitespace. The parser never calls `eval`, imports code from the file, follows commands, or executes spreadsheet expressions.

## Bounded parser limits

| Limit | Value |
|---|---:|
| File/input bytes | 10,485,760 |
| DATA records | 100,000 |
| Characters in one field | 1,024 |

Input must be strict UTF-8 without a BOM or NUL byte. LF and CRLF line endings are accepted; lone CR and embedded ASCII control characters are rejected. The file loader accepts only a `.csv` suffix and performs bounded read-only access.

## Evidence boundary

`source` is called `declared_source` in the Python record model because the parser can validate spelling but cannot authenticate how a file was produced. A row containing `BENCH_DMM` does not by itself prove that a multimeter was used.

Step 6 will emit replayed Measurements with current source `CSV_REPLAY` while retaining the original record reference and declared metadata. Only separately documented raw artifacts, instruments, wiring, conditions, timestamps, and review can support future bench claims.

## Public API

```python
from pathlib import Path

from analog_validation import load_csv_replay, parse_csv_replay

dataset = load_csv_replay("measurements.csv")
assert dataset.is_complete
assert dataset.declared_record_count == len(dataset.records)

same_dataset = parse_csv_replay(Path("measurements.csv").read_bytes())
assert same_dataset == dataset
```

Expected failures use `ReplayFormatError`, `ReplayLimitError`, or `UnsupportedReplayVersion`, all under `ReplayError`.

## Step 5 boundary

Implemented now:

- immutable record and complete-dataset models;
- bounded strict text and file parsing;
- stable replay error families;
- valid and invalid golden compatibility cases.

Deferred to Step 6:

- `CsvReplayAdapter` lifecycle and capabilities;
- sequential reads and explicit EOF state;
- playback speed, pause, and resume;
- conversion to current `CSV_REPLAY` Measurements;
- shared adapter-contract verification.
