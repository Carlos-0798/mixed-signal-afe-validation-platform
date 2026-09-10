# SYNTHETIC voltage import examples

All three tables are deterministic synthetic test fixtures. They are not exports from
any instrument or vendor and establish no physical hardware accuracy.

Each table represents the same five DC points: input 100, 300, 500, 700, and
900 mV, with output exactly twice the input. Their timestamps normalize to
2026-09-09 12:00:00 through 12:00:04 UTC.

| Source | Layout | Mapping |
| --- | --- | --- |
| `synthetic-comma-utc-v.csv` | Comma, explicit UTC timestamps, both channels in V | `synthetic-comma-utc-v.mapping.json` |
| `synthetic-semicolon-elapsed-mv.csv` | Semicolon, elapsed seconds, both channels in mV | `synthetic-semicolon-elapsed-mv.mapping.json` |
| `synthetic-tab-reordered-mixed.csv` | Tab, reordered columns, UTC offset, V input and mV output | `synthetic-tab-reordered-mixed.mapping.json` |

The elapsed mapping includes an explicit synthetic acquisition origin. The
`FixtureEvidence` column preserves the SYNTHETIC label in the raw source. After
conversion, replay records are labeled `CSV_REPLAY`; `VALID` means the values
parsed as finite and within the configured range. Neither label proves bench
validation.

From the repository root, create and verify a new local package:

```powershell
analog-validation import-csv convert --input examples/voltage-import/synthetic-comma-utc-v.csv --mapping examples/voltage-import/synthetic-comma-utc-v.mapping.json --output outputs/synthetic-voltage-import
analog-validation import-csv verify --input outputs/synthetic-voltage-import
```

The output parent must exist, and the destination package must not already
exist. The package contains the unchanged source bytes, explicit mapping,
canonical replay, portable project, and integrity manifest. For the other
layouts, substitute the matching source and mapping paths above. Golden tests
freeze their equivalent replay data and portable artifact hashes.
