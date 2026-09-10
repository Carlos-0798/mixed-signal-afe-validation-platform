# Import voltage data for offline replay

The **Import data** Dashboard tab and `import-csv` CLI accept ordinary CSV
voltage measurements and create a portable replay project. This first import
scope supports one input voltage and an optional paired output voltage. It
does not provide universal instrument support, device discovery, acquisition,
or proof that the file came from physical hardware.

Imported values remain **CSV_REPLAY** evidence. A `VALID` record means the
selected value passed syntax, finite-number, and range checks. It does not
establish measurement accuracy or a hardware acceptance result.

## Dashboard workflow

1. Open **Import data**, choose a local CSV, and select its comma, semicolon,
   or tab separator. Review the column names and first five data rows.
2. Select distinct time and input-voltage columns. Select an output-voltage
   column if the source contains paired observations. Choose **V** or **mV**
   explicitly for each voltage column; units are never inferred from a header.
3. Select timestamp or elapsed-seconds mode. For elapsed time, enter the
   actual acquisition start time with a timezone. Review the allowed voltage
   range in mV, then preview the conversion.
4. Resolve any reported original row/column errors. Save the mapping for
   reuse if desired. Publish into a new folder beneath an existing directory.
5. Load the published preset, review its analysis criteria, and run the
   existing offline workflow. Importing alone does not execute analysis.

Selecting a source captures its exact bytes in memory. Changing the mapping
or separator reinterprets that snapshot; it does not silently reread the file.
If the first selection cannot be parsed with the chosen separator, select the
correct separator and choose the file again, as the source panel instructs.
Choose the source again to import a newer on-disk version. The package stores
the captured bytes, including the original BOM and line endings, as `source.csv`.

## Accepted source data

The source must be a regular local file containing UTF-8, with an optional
UTF-8 BOM. Symbolic links and Windows reparse points in an import path are
rejected. Maximums are **2 MiB**, **10,000 data rows**, **64 columns**, and
**1,024 characters per cell**. There must be a header and at least one data row.

The separator must be selected explicitly. Quoted fields are supported by
strict CSV parsing. Header names are stripped and Unicode NFC normalized;
empty or duplicate names after normalization are rejected. Every data row
must have exactly the header's column count. Blank rows, malformed quoting,
NUL characters, and oversized input fail the complete import; rows are not
silently skipped. Errors identify the original physical CSV row when possible,
including records containing quoted newlines.

Only selected columns are interpreted as measurements or time. Selected
voltage cells must contain finite dot-decimal numbers; scientific notation is
accepted. Empty cells, `NaN`, infinities, decimal commas, and unit-suffixed
values are rejected. Values in V are multiplied by 1,000; replay values are
always mV. Both selected channels must fall within the inclusive configured
range, initially 0–3,300 mV. Unselected columns remain in the preserved source.

Time must be nondecreasing after conversion to UTC:

- **Timestamp:** ISO 8601 with seconds and an explicit `Z` or `±HH:MM` timezone,
  for example `2026-09-09T12:00:00.125Z`. Fractional seconds may contain at most
  six digits. A separate acquisition origin must not be supplied.
- **Elapsed seconds:** nonnegative finite seconds, added to an explicitly
  supplied timezone-aware acquisition origin. There is no invented Unix epoch
  or current-time fallback. Output timestamps use Python datetime's microsecond
  resolution; sub-microsecond intervals can produce equal timestamps.

The first voltage maps to `afe.ch0.input`; optional output maps to
`afe.ch0.output`. Each original data row produces one or two replay records
with stable original-row identifiers and the same converted UTC timestamp.

## CLI examples

Run these commands after installing the project in the active environment.
Paths shown are examples; the output directory must not already exist.

```console
analog-validation import-csv inspect --input capture.csv --delimiter comma --json
analog-validation import-csv convert --input capture.csv --mapping scope-mapping.json --output imported-capture --json
analog-validation import-csv verify --input imported-capture --json
```

`inspect` reports columns, total row count, source SHA-256, and at most five
raw data rows with their original row numbers. It writes no files and does
not infer units or validate selected measurement semantics. Separator choices
are `comma`, `semicolon`, and `tab`.

`convert` uses the mapping's separator, validates the complete source, and
publishes the package. `verify` checks a package directory without acquiring
measurements or running analysis. All three actions use the existing
`product-cli-output.v2` envelope. Successful JSON goes to stdout; expected
errors use the existing issue JSON on stderr and nonzero CLI exit codes.
Omit `--json` for concise human-readable output.

An example mapping for a scope export with elapsed time is:

```json
{
  "schema_version": "voltage-import-mapping.v1",
  "name": "Scope voltage capture",
  "time_column": "Time (s)",
  "input_column": "CH1",
  "input_unit": "V",
  "output_column": "CH2",
  "output_unit": "V",
  "time_mode": "elapsed_seconds",
  "start_time_utc": "2026-09-09T12:00:00Z",
  "delimiter": ",",
  "minimum_mv": 0.0,
  "maximum_mv": 3300.0
}
```

Mapping JSON is limited to 64 KiB. Duplicate keys, unknown fields, missing
required identity fields, non-finite JSON constants, and unsupported versions
are rejected. `output_column` and `output_unit` must be supplied together or
both omitted/null. Mapping names are limited to 256 characters. In timestamp
mode, set `time_mode` to `timestamp` and `start_time_utc` to null. Mapping writes
are create-new operations, so saving over an existing mapping is rejected.

**For every new recording in elapsed-seconds mode, update `start_time_utc` to
that recording's actual acquisition start.** Saved mappings retain the origin;
reusing a template's old timestamp would attach incorrect dates to new data.
The import cannot independently verify that the supplied origin is truthful.

## Published package and verification

| File | Purpose |
| --- | --- |
| `source.csv` | Exact captured source bytes |
| `mapping.json` | Canonical explicit interpretation of those bytes |
| `replay.csv` | Existing `csv-replay.v1` records in UTC and mV |
| `project.json` | Existing `validation-project.v1` with one offline preset |
| `import-manifest.json` | `voltage-import-manifest.v1` provenance and hashes |

The project contains only a relative `replay.csv` reference, allowing the whole
folder to be moved. The publication API returns absolute paths for immediate
Dashboard use. A paired import with at least three source rows creates a
`DC_ANALYSIS` preset; an import with one channel or fewer than three rows creates
a `READ` preset. Its profile is `afe@1`, sample count equals source rows, and replay
range comes from the mapping.
The `afe` profile/channel identifiers here describe the existing logical replay
contract; they do not assert that a physical AFE or MSP430 supplied the data.

The existing DC workflow requires at least three included points. For one or
two paired source rows, the generated read setup avoids an inevitably incomplete
DC fit; both channels still remain in the replay file. A read setup initially
reads `afe.ch0.input`; select the output channel in Setup to inspect it separately.

**The generated preset is a starting configuration.** Existing defaults such
as target gain, tolerances, and output limits are not inferred from the CSV or
certified for the instrument/circuit. Review them before interpreting PASS/FAIL.
Data can import successfully yet be unsuitable for a meaningful DC fit, for
example repeated identical input voltages.

The manifest records the source filename basename, dataset identity, row and
record counts, explicit CSV_REPLAY evidence, a hardware-claim limitation,
time mode and acquisition origin, and exact filename/SHA-256/byte-size entries
for the four artifacts. Verification strictly checks that contract and
bounded artifact paths, then regenerates replay and project bytes from the
stored source and mapping. Rehashing an inconsistent replay or edited project
does not make it pass verification. Treat the original import package as an
immutable record; save adjusted analysis configurations separately.

The ordinary UTF-8 source limit is 2 MiB. The generated strict replay retains
the existing parser's separate 10 MiB limit; conversion fails if its output
cannot satisfy that contract. Project JSON remains bounded at 1 MiB, and the
import manifest at 64 KiB.

Hashes detect byte changes and reproduction checks internal consistency.
Neither proves instrument identity, acquisition circumstances, calibration,
or authorship. A fully consistent copy verifies, as does a newly generated
consistent package; verification is not authentication or a digital signature.

Publication writes a sibling staging directory and exposes the final directory
only after all files are complete. Existing destinations, including a path
created concurrently, are never replaced. Windows uses native no-replace
rename behavior. Linux requires native `renameat2(RENAME_NOREPLACE)`; unsupported
platforms, runtimes, or filesystems fail closed. Mapping files use an atomic
create-new hard link. The destination parent must already exist and support
these filesystem operations. Ordinary failed publications remove their staging
files and do not expose a partial final package. A filesystem cleanup error is
surfaced and can leave a hidden staging directory for later inspection.

## Python API and compatibility

Pure parsing and conversion live in `analog_validation_app.tabular_import`:
`VoltageImportMapping`, `TabularImportSource`, `VoltageImportPreview`,
`parse_voltage_table(bytes, delimiter=...)`,
`preview_voltage_import(source, mapping, dataset_id=...)`, and
`mapping_to_dict` / `mapping_from_dict`. These do not access files or devices.

`analog_validation_app.import_packages` provides:

- `load_voltage_table(path, delimiter=',')`
- `load_voltage_mapping(path)` and `write_voltage_mapping(path, mapping)`
- `publish_voltage_import(output_directory, preview, source_name='source.csv')`
- `verify_voltage_import(output_directory)`

`delimiter`, `dataset_id`, and `source_name` are keyword-only where shown.
Publishing and verifying return a frozen `VoltageImportPublication` with
`output_directory`, `replay_path`, `project_path`, `manifest_path`, and
`configuration`. Import errors use `VoltageImportError`, a
`ProductRequestError` subtype with optional `row_number` and `column` details.

This addition preserves existing replay, project, result, coefficient, run
manifest, and CLI output schemas. Existing replay workflows continue to use
their original parser and execution services. CSV import does not open or
enumerate devices, import serial backends, or grant hardware access.
