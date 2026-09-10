# Reviewer guide — about two minutes

**Review branch:** `main`. The default branch contains the current product
integrated through [PR #10](https://github.com/Carlos-0798/mixed-signal-afe-validation-platform/pull/10).
This is an installable software beta, not a tagged GitHub Release.

## The problem and personal contribution

Repeated voltage-data validation requires preparing tables, normalizing units
and time, calculating gain/offset/linearity, checking criteria, and assembling
reports. Separate scripts and spreadsheets can make the original inputs and
settings difficult to reconstruct.

Analog Validation Studio is an **independent personal Python engineering
project** implementing that sequence through reusable CLI and desktop workflows:
adapters, typed measurements, analysis, cancellable execution, and traceable
reports. It is separate from the OSU Lab Bench Monitor capstone and MSP430
Equipment Health Controller project.

## Follow one input through the product

1. **Input:** open the [five-point synthetic CSV and mapping](../examples/voltage-import/README.md).
   Three layouts express identical data with different separators, column
   orders, and V/mV units. They are not instrument exports.
2. **Prepare and analyze:** `analog-validation import-csv convert` applies the
   explicit mapping and creates a source-preserving replay/project package;
   `import-csv verify` reproduces its conversion. `project run` executes the
   generated DC preset through the shared analysis workflow. This automates
   repetitive column rearrangement, unit conversion, replay-file construction,
   and formula/criteria application. See the [import guide](voltage-data-import.md).
3. **Report:** `analog-validation report` renders a finalized JSON/CSV result as
   readable text/Markdown/HTML and SVG charts; the source result stays separately
   retained. The Dashboard's **Save report bundle** also includes canonical JSON.
   Rendering preserves the engineering conclusion. See
   [report examples](human-reports.md).
4. **Reuse and compare:** save mappings and presets for another dataset, then
   use `project history` and `project compare` to verify retained inputs and
   compare runs, replacing manual collection of prior files, settings, and
   metrics. See [projects and history](test-projects-and-history.md).
   For a new recording, update any saved elapsed-time acquisition origin.

## Engineering choices worth discussing

- **One implementation of the workflow:** the CLI and Dashboard share the
  [workflow compiler](../src/analog_validation_app/product_workflows.py) and
  [DC analysis core](../src/analog_validation/analysis/dc_sweep.py), separating
  presentation from numerical conclusions.
- **Explicit input interpretation:** the [table importer](../src/analog_validation_app/tabular_import.py)
  rejects invalid selected cells instead of guessing or silently dropping rows.
  [Import packages](../src/analog_validation_app/import_packages.py) preserve
  original bytes and publish complete new directories without overwriting.
- **Recoverable execution:** [project execution](../src/analog_validation_app/projects.py)
  supports cooperative cancellation and preserves completed results when a
  later preset fails. Versioned manifests retain compatibility and provenance;
  hashes establish consistency, not author authentication.

## Evidence and limits

The [private-sync local gate](../reports/private-github-sync-2026-09-09.md)
records **3,048 passing tests and 17,567/17,567 package statements covered**,
plus Ruff, mypy, dependency, and product-quality checks. Statement coverage does
not establish branch coverage or defect-free software.

The earlier [TD-052 acceptance](../reports/td-052-voltage-import-2026-09-09.md)
separately records 3,047 tests, 23 fresh-install CLI commands, and a real installed
Tk import-to-report workflow. Those installation checks were not all rerun for
the later gate. [Cloud CI is manual-only](LOCAL_TESTING_AND_CI.md);
reviewing or demonstrating the project requires no cloud run.

No human time-saving percentage or operator-error reduction has been measured.
Synthetic/replay success establishes no AFE hardware accuracy or universal
device compatibility. Default analysis criteria still require review; see
[known limitations](KNOWN_LIMITATIONS.md).

Feature expansion is paused for job-search preparation. **TD-053** will select
one further input format only after real, interpretable samples establish a
need; it is not a promise to support every instrument. The
[resume checkpoint](PROJECT_RESUME_CHECKPOINT_2026-09-09.md) preserves that route.
