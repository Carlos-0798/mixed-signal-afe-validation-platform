# Test projects, presets, run history, and comparisons

**Implemented evidence:** `HOST_TEST` / `SYNTHETIC` / `CSV_REPLAY`<br>
**Hardware access required:** no<br>
**Hardware performance claim:** none

## Why this feature exists

Running one analysis from a long command is useful while developing, but it is
not a complete test-automation product. A reusable product also needs to answer:

- Which exact settings were intended?
- Which tests belong together?
- What actually ran, and with which software version?
- Did a later run change an outcome or metric?
- Can an old run still be interpreted after the editable project changes?

Analog Validation Studio answers those questions with four separate objects:

1. a **project** is a versioned, bounded JSON document;
2. a **preset** is one named, immutable offline workflow configuration in that
   project;
3. a **run directory** is a create-new snapshot of one selected batch;
4. a **comparison** is a presentation-only difference between two verified run
   manifests from the same project.

This is deliberately local and file-based. There is no account, database,
cloud synchronization, background directory scan, or hidden default location.

## First offline project

From an activated or explicitly addressed installation:

```powershell
analog-validation project create `
  --output .\work\afe-project.json `
  --project-id afe-demo `
  --name "AFE Demo Project"

analog-validation project inspect --input .\work\afe-project.json

analog-validation project run `
  --input .\work\afe-project.json `
  --output .\work\run-001 `
  --run-id run-001
```

The starter project contains six Simulator presets:

| Preset | Workflow | Engineering conclusion |
|---|---|---|
| `read-default` | Five input observations | none |
| `dc-default` | 24-point DC transfer analysis | PASS/FAIL/INCOMPLETE |
| `hysteresis-default` | Directional Schmitt analysis | PASS/FAIL/INCOMPLETE |
| `calibration-default` | 12-point linear calibration | PASS/FAIL/INCOMPLETE |
| `frequency-default` | Single-pole amplitude response | PASS/FAIL/INCOMPLETE |
| `live-default` | Finite 20-sample live snapshot | none |

Simulator conclusions remain `SYNTHETIC`. A software PASS says the generated
data satisfied the reviewed software criteria; it does not validate an AFE.

## Run selected presets

Omit `--preset` to run all presets. Repeat it to form an explicit ordered
subset:

```powershell
analog-validation project run `
  --input .\work\afe-project.json `
  --output .\work\run-002 `
  --run-id run-002 `
  --preset dc-default `
  --preset frequency-default
```

Execution is sequential and bounded. A project can contain at most 32 presets,
and a run manifest can contain at most 32 records. Every output directory must
be new; existing files or directories are never replaced.

The batch owner can request cooperative cancellation before a preset, between
presets, or while a worker is active. An active worker receives the request,
finishes its bounded cleanup, and publishes one terminal record before the batch
stops. Later presets are never started. In the CLI, Ctrl+C follows this path and
returns exit code `130` after the cancelled manifest has been atomically saved.
There is no forced thread termination.

Batch progress reports the current preset ID, its one-based number, total preset
count, completed terminal-record count, and one of `PREPARING`, `RUNNING`,
`CANCELLING`, `FINALIZING`, or `FINISHED`. A preset counts as completed only
after its worker and cleanup have reached a terminal state. CLI progress is
human-readable `stderr`; `--json` keeps the single machine-readable document on
`stdout`.

The Dashboard Projects & history page consumes these same events. Its progress
bar is determinate: it never estimates work that the core has not reported. The
status text shows the current phase and preset, while the history table shows
the terminal batch status, planned count, completed record count, and
not-started count. **Cancel batch safely** sends one cooperative request and is
then disabled. The page remains locked until current-worker cleanup and atomic
manifest publication finish. Closing the window during a batch requests the
same cancellation and waits for that safe terminal point.

## What a run stores

A run directory contains:

```text
run-001/
  project.snapshot.json
  run-manifest.json
  inputs/
    NN-<preset>.csv              # executed CSV Replay inputs only
  NN-<preset>.result.json          # analysis presets only
  NN-<preset>.coefficients.json    # calibration only
```

`project.snapshot.json` preserves the exact portable project document used for
the run. New runs use `validation-run-manifest.v3`. The manifest stores its
SHA-256 plus a canonical configuration SHA-256
for each executed preset. It also copies terminal worker/product status,
finalized engineering outcome, evidence source, measurement count, bounded
numeric metrics, limitations, issue code, software version, and artifact
hashes. It never recalculates a finalized PASS or FAIL.

The v2/v3 manifest records the ordered `planned_preset_ids`, every terminal record,
and the ordered `not_started_preset_ids`. Its batch status means:

- `COMPLETE`: every preset in the project was planned and reached a terminal
  worker/cleanup state;
- `PARTIAL`: an intentional strict subset was planned and every selected preset
  reached a terminal state;
- `CANCELLED`: a cancellation request was accepted, cleanup finished, and any
  later presets are explicitly not started;
- `ERROR`: worker execution or cleanup failed; that failure record is retained
  and later presets are explicitly not started.

These are execution states. `COMPLETE` does not mean engineering PASS, and no
state upgrades `SYNTHETIC`, `CSV_REPLAY`, or `HOST_TEST` evidence to BENCH.
The v3 manifest also maps every executed CSV Replay preset to a safe run-relative
input artifact, exact byte count, and SHA-256. The runner copies that input into
staging before preparation and executes the staged copy. If several executed
presets reference the same resolved source file, one copy is stored and each
preset retains its own reference. A preset cancelled before it starts is not
opened and has no input-artifact record.

The loader still accepts strict `validation-run-manifest.v1` and v2 documents with
their exact original fields. Loading or presenting a v1 file never rewrites it;
v1 simply has no encoded batch status or not-started list.
The Dashboard therefore renders its batch status as `LEGACY_V1`; it does not
infer `COMPLETE` from the presence of old records.

Read and live-monitor presets do not currently publish raw output-observation files;
their history records contain the terminal status, source, counts, limitations,
and bounded summary metrics. A CSV Replay source file is now retained as a v3
input artifact; this does not create a new result dataset or change its
`CSV_REPLAY` evidence class. Analysis presets publish their existing strict
`result-export.v1` artifact, and calibration also publishes its separate
coefficient artifact.

## Verify history

History is intentionally explicit. Supply each manifest that should be
included; the command neither searches a drive nor recursively scans a folder:

```powershell
analog-validation project history `
  --run .\work\run-001\run-manifest.json `
  --run .\work\run-002\run-manifest.json
```

The loader rejects duplicate inputs, mixed project IDs, malformed/oversized
JSON, non-terminal records, inconsistent summaries, missing artifacts, input
byte-count changes, and SHA-256 mismatches. It also cross-checks that each
manifest project ID, preset
ID, and canonical configuration SHA-256 actually belongs to the exact saved
project snapshot. Up to 64 explicit manifests can be summarized at once.

## Compare two runs

```powershell
analog-validation project compare `
  --left .\work\run-001\run-manifest.json `
  --right .\work\run-002\run-manifest.json
```

Comparison requires the same `project_id` and verifies both manifests and their
referenced artifacts first. It reports:

- whether the saved project snapshot changed;
- presets added to or missing from either run;
- configuration, terminal status, product status, engineering outcome,
  evidence, count, or issue changes;
- left value, right value, and delta for matching numeric metrics.

The Dashboard adds a presentation-only guide before the detail table. It names
the baseline and candidate, shows each batch state and project-snapshot drift,
separates matched results from baseline-only, candidate-only, and not-started
presets, and preserves exact evidence labels such as `SYNTHETIC` and
`CSV_REPLAY`. Evidence-label mismatch is explicitly not presented as
like-for-like. Delta always means candidate minus baseline; positive or negative
alone does not mean improvement or regression because requirement direction and
configuration still determine the engineering meaning.

Artifact timestamps, job IDs, and result-file hashes alone do not turn an
otherwise identical engineering record into a changed result. Conversely, a
configuration hash change remains visible even if deterministic output metrics
happen to match.

Add `--json` to any project command for the versioned machine-readable view.
During `project run`, progress remains on `stderr`, so redirect or parse
`stdout` independently when using `--json`.
Exit codes retain the normal CLI meanings: engineering failure is `1`, invalid
usage is `2`, incomplete is `3`, unsupported is `4`, expected operational
failure is `5`, unexpected internal error is `70`, and cancellation is `130`.

## CSV Replay projects

The public model also accepts strict CSV Replay presets. A replay path must be
relative to the project file and must resolve inside that project directory.
`project inspect` validates only the project document and does not open the
referenced replay. The explicit `project run` action is the resource-opening
boundary.

At that boundary, each selected Replay input is copied into the create-new run
staging directory before its worker starts. Failure to resolve, read, bound, or
write the copy aborts publication and removes staging; no partial run directory
is exposed. Later history verification uses the retained bytes, size, and hash,
so moving or editing the original project-side CSV cannot silently alter the
completed run. This preserves the actual input file but does not yet provide a
one-click rerun or raw READ/LIVE output persistence.

Serial settings are not allowed in a saved project. This is intentional:
COM-port names, device identity, live ownership, and receive-only confirmation
must be reviewed afresh instead of being silently replayed from an old file.

## Integrity and security boundary

The strict schemas, create-new publication, snapshots, and SHA-256 checks make
accidental changes and one-file tampering detectable. SHA-256 here is an
integrity identifier, not authentication. A person who can rewrite both a
manifest and every referenced artifact can create a new self-consistent set.
Signed manifests, user identity, access control, and a trusted timestamp service
are not implemented.

Project JSON is data, never executable Python. Parsers reject duplicate keys,
NaN/Infinity, NUL, invalid UTF-8, unknown/missing fields, unsafe identifiers,
oversized content, path traversal, and persisted Serial configuration.

## Dashboard workflow

The **Projects & history** tab uses the same public project API as the CLI.
Its top guide identifies the next valid action. Buttons that require a project,
saved changes, a complete batch form, an exact Review, or enough history remain
unavailable until those existing backend conditions are met.

1. Enter a project ID and name, then **Create starter…** and choose a new JSON
   file, or **Open project…** to load an existing one. Cancelling a file dialog
   leaves the current project unchanged.
2. Select presets with Ctrl/Shift, or **Select all**. To create a custom preset,
   first configure the form on **Setup & run**, then enter a new preset ID/name
   here and choose **Add current Setup as preset**. This captures the form
   without running it. The preview shows the current Setup test and exact
   `SYNTHETIC`/`CSV_REPLAY` boundary; Serial cannot be persisted and no port is
   discovered. **Save project as…** writes the modified project to a
   new JSON file; the original is retained. Serial configurations are rejected.
3. Enter a unique run ID and choose a **new output directory name**. Its parent
   must already exist. The directory picker selects a name; Run creates it.
4. Choose **Review selected batch**. The frozen summary names the exact project,
   run ID and create-new destination, then lists every preset in project-row
   order with readable Source/Test names and its exact `SYNTHETIC` or
   `CSV_REPLAY` evidence label. Changing the selection, destination or ID
   requires a fresh review. **Run reviewed batch** consumes and clears this
   summary as real progress begins.
5. The background batch leaves Tk's event loop responsive. Its determinate bar
   and text show the actual phase, current preset, sequence/total, and completed
   terminal-record count. **Cancel batch safely** requests cooperative
   cancellation once; the active worker cleans up, later presets stop, and the
    v3 manifest preserves terminal records plus explicit not-started IDs and
    inputs for the Replay presets that actually started. A
   single test and a project batch cannot run at the same time.
6. Completed batches enter the history table. **Load run manifests…** selects
   existing histories explicitly and validates them before updating the table.
   Zero history explains how to create or load the first run; one run asks for a
   second same-project manifest; two or more enable selection for comparison.
   Select one history row to inspect its v3 Replay input references in a separate
   read-only table with archived path, byte count, and full SHA-256. A v1/v2 row
   explains that it predates this feature, while an empty v3 row identifies a
   Simulator-only run or Replay presets that never started. Select two rows to
   return to comparison; no CSV is opened and no result is recalculated.
   **Clear view** clears only the table, not saved files.
7. Select exactly two history rows and choose **Compare selected runs**. With the
   table focused, Shift+Up/Down extends or shrinks the selection and Ctrl+A
   selects all rows; Ctrl+click also permits individual selections. Row order
   defines baseline then candidate. The table shows worker/product/outcome/evidence,
   configuration identities, metric values, units, and candidate-minus-baseline
   deltas. The guide above it explains identity, coverage, evidence-label
   mismatch, changed presets, and delta direction. The two runs must belong to
   the same project.

Closing during a batch requests the same cooperative cancellation and waits for
worker cleanup plus manifest publication before closing. Unsaved preset changes
require a discard confirmation. In-place preset editing, graphical trace
overlays, signed/authenticated manifests, and raw READ/LIVE observation
persistence remain future work. A project can contain 32 presets, so a batch can
last substantially longer than one test.
