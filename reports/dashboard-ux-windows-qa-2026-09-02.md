# Dashboard UX Windows QA — 2026-09-02

## Scope and evidence boundary

This check exercised the local Analog Validation Studio UI, its shared product
workflow, and temporary result exports on Windows. It did not enumerate, open,
read, reset, flash, or write an MSP430 or any other physical device. The
**Find serial ports** action was not invoked.

Evidence class: `HOST_TEST` for the Windows interaction and `SYNTHETIC` for
Simulator observations. Hardware claim: `NO_NEW_HARDWARE_VALIDATION`.

## Verified interaction chains

1. Confirmed that the completed first frame contained the modern header,
   `Setup & run` and `Results & evidence` tabs, and a visible page scrollbar.
2. Entered non-numeric `abc` in the DC point count. Validation stopped before
   Run and displayed `INVALID_REQUEST` with the cause and safe next step.
3. Corrected the count to 12, reviewed the exact Simulator/DC boundaries, ran
   the analysis, and reached `SUCCEEDED` with six worker events and zero drops.
4. Verified the finalized DC result: `PASS`, 12 included points, gain `2.0`,
   offset `12.0 mV`, R-squared `1.0`, and RMSE `0.0 mV`.
5. Exported that finalized result to new JSON and CSV files. Both parsed as
   `result-export.v1`; the JSON contained 12 points, 24 evidence-record IDs,
   `PASS`, and `SYNTHETIC` provenance.
6. Tried the same JSON destination again. The file was not replaced, and the
   result page displayed `WARNING [OUTPUT_EXISTS]` with an actionable next step.
7. Used **Review same setup** followed immediately by **Run reviewed test** and
   confirmed a clean second completion without cross-job event leakage.
8. Used **Start new test** and confirmed that the previous result was cleared
   and a clean Source step was presented.
9. Selected CSV Replay/READ. A malformed one-row file was rejected before Run
   because it did not contain the required 13 columns.
10. Replaced it with a valid five-record file. Review bound the declared dataset,
    Run completed with five events and zero drops, and the visible values were
    exactly 100, 200, 300, 400, and 500 mV with `CSV_REPLAY` provenance.
11. Ran Simulator/HYSTERESIS_ANALYSIS with 12 rising and 22 falling points. The
    result was `PASS`: mean high threshold `991.5 mV`, mean low threshold
    `916.0 mV`, mean width `75.5 mV`, and width span `0.0 mV`.
12. Used the mouse wheel to inspect run status, point tables, evidence,
    limitations, and artifacts. Every QA window was closed through
    **Finish & close**, and no Analog Validation Studio window remained.

A bounded READ intentionally produces no engineering PASS/FAIL and no analysis
export bundle. An analysis PASS above means only that deterministic synthetic
records met the reviewed software criteria.

## Defects found and corrected during QA

- Configuration errors were hidden because the issue panel rendered only on
  the Review step. The panel now remains visible whenever an issue exists.
- A rare immediate-rerun race could deliver the prior job's terminal event after
  the next job started. The controller now reconciles the prior terminal queue
  before replacing the active request; a 5,000-iteration stress check passed.
- A rejected duplicate export could leave the prior success message visible on
  the Results tab. Export failures now replace that message with the structured
  issue and safe next step.
- Returning from Review to Configure revoked the prepared job internally but
  left the presentation panel marked `can_run=true`. The transition now clears
  that stale review authorization, so the user must validate the edited setup
  again before Run.
- An initial implementation exposed the result-reference transition by editing
  the frozen Phase 5 action enum and golden manifest. Final review moved that
  behavior behind the existing presenter boundary and restored the compatibility
  golden unchanged.

## Rendering changes exercised

- Both notebook pages use a width-tracking Canvas with a visible vertical
  scrollbar and Windows mouse-wheel routing.
- The root window remains hidden until widget creation, the initial render, and
  `update_idletasks()` complete.
- Dashboard and wizard renders are gated by immutable revision numbers, so an
  unchanged 50 ms poll does not clear and repopulate the result table.

No incomplete black first frame or recurring redraw flicker was observed after
the completed first paint in this session. This is a result for the tested
Windows session, not a claim about every GPU, remote desktop session, scaling
factor, or display configuration.

## Automated gates after the fixes

- Strict pytest/coverage gate: **2,263 passed** and **100.00%** statement
  coverage across `analog_validation`, `analog_validation_app`, and
  `analog_validation_pyserial` (11,820 statements, zero missed).
- Ruff over `src`, `tools`, `tests`, and `examples/public_adapter`: **passed**.
- mypy over the same production, tooling, test, and public-example surfaces:
  **passed**, 204 source files checked.
- Development-environment `pip check`: **passed**.
- Read-only development-environment audit: **22 PASS, 0 WARN, 0 FAIL**. The
  audit reported zero serial-port enumerations, zero opened ports, zero device
  writes, no network access, and no hardware-validation claim.
- Host-only product-quality acceptance: **all 10 checks passed**. On this host,
  the 10,000-record Replay case completed in 0.562387 s with 13.102 MiB peak
  traced memory; the 10,000-event bounded-queue case completed in 0.034579 s,
  retained its configured maximum of 256 events, and cleaned up successfully.
  These wall-clock observations are not real-time or cross-machine guarantees.
- Two isolated wheel/source-archive builds were byte-identical after the
  repository's deterministic sdist normalization.
- Built wheel:
  `mixed_signal_afe_validation_platform-0.1.0b1-py3-none-any.whl`, 254,634
  bytes, SHA-256
  `d2502b4474995b4762026b72a6c434f4e441c9348fdc6c3da537ad3c2c00689d`.
- Built source archive:
  `mixed_signal_afe_validation_platform-0.1.0b1.tar.gz`, 701,828 bytes,
  SHA-256
  `2180a65ee910b2f2ca8ee93c011eeed9c7b9f2d5841dc529a4b9e6eac5004b34`.
- Fresh base-wheel install and `pip check`: **passed** with no runtime
  dependency, no pyserial package, and no Tk import during headless import.
- Fresh `[serial]` install and `pip check`: **passed**. Its transport probe used
  an injected host-only substitute: no physical discovery, port open, or
  application write surface occurred.
- Installed synthetic demo in normal and Unicode paths: **passed** and
  byte-identical; 12 artifacts, `PASS`, `SYNTHETIC`.
- External public-API-only read adapter: **passed** with three synthetic
  measurements and zero output commands or written bytes.
- `git diff --check`: **passed**.

These engineering and build/install gates passed for the current working-tree
change set. The separate create-new release-candidate command was intentionally
not claimed: it binds a candidate to a clean Git commit, while these reviewed
Dashboard changes remain uncommitted. No release manifest or distributable
Release was published.

The temporary exports were retained only as local QA evidence. No commit,
push, pull-request mutation, tag, release, or publication was performed.
