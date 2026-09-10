# Analog Validation Studio

**Turn voltage CSV files into repeatable tests, plots, and traceable reports.**

A local Python desktop app and CLI for students and engineers who repeatedly
check analog measurement data. Map columns and units once, review the test
criteria, then reuse the same analysis and reporting workflow for later files.

**Independent personal engineering project · Python 3.10+ · Tkinter/ttk · offline operation**

[Two-minute project review](docs/REVIEWER_GUIDE.md) ·
[Try the software](#try-the-software) ·
[Verification evidence](#verification) ·
[Architecture](#architecture)

Current software scope is implemented and locally verified through voltage CSV
import. This private `0.1.0b1` candidate is on `codex/calibration-workflow` in
[Draft PR #10](https://github.com/Carlos-0798/mixed-signal-afe-validation-platform/pull/10);
the default `main` still contains an earlier runtime. No public release is claimed.

## The problem and the result

Repeated gain, offset, and linearity checks often require reformatting a CSV,
copying spreadsheet formulas, recreating plots, and manually recording which
criteria produced a result. AVS connects those steps in one reusable workflow:

**Import data → review criteria → run analysis → inspect results → export reports → reuse the project.**

| Repeated manual work | Implemented automation |
|---|---|
| Rename columns and convert V/mV for every file | Explicit, reusable CSV mapping with converted-value preview |
| Reapply calculations and acceptance limits | Shared analysis core with saved projects and test presets |
| Copy results into charts and reports | JSON/CSV plus text, Markdown, HTML, and SVG from finalized results |
| Track interrupted runs and locate source files | Cooperative cancellation, retained partial results, archived Replay inputs, and verified history |

These operations are automated in the software. Human time savings and reduced
operator-error rates have not yet been measured; see the
[task-value evaluation](docs/TASK_VALUE_VALIDATION_PLAN.md).

## What I built

- **A controller-neutral core:** immutable measurements, public adapter/profile
  contracts, explicit units, and DC/hysteresis/calibration/amplitude-response analysis.
- **One execution path for GUI and CLI:** reviewed configuration, progress,
  cooperative cancellation, cleanup, and consistent success/error outcomes.
- **Reusable test workflows:** voltage-table import, saved presets, batch runs,
  input retention, history comparison, and versioned manifests readable across
  supported older schema versions.
- **An installable desktop product:** guided Tkinter/ttk UI, Workbench/Daylight/
  Midnight themes, automated reports, packaging, compatibility tests, and local
  quality gates. The base installation has no third-party runtime dependency.

This project demonstrates Python software engineering, test automation, data
processing, and hardware/software interface design. The
[reviewer guide](docs/REVIEWER_GUIDE.md) connects each contribution to code and evidence.

## Product preview

![Workbench theme: checked voltage import with explicit units and CSV_REPLAY evidence](media/dashboard-import-workbench-20260909.jpg)

Real Windows application, captured 2026-09-09. The six-row input is synthetic;
the imported preview is labeled `CSV_REPLAY`. This shows data preparation,
not a hardware measurement.

[Daylight](media/dashboard-import-daylight-20260909.jpg) ·
[Midnight](media/dashboard-import-midnight-20260909.jpg) ·
[Screenshot provenance and hashes](media/README.md)

<details>
<summary>Earlier result-view screenshots (2026-09-03, before the current themes)</summary>

![Completed synthetic DC analysis in the earlier Dashboard](media/dashboard-dc-result.png)

![Earlier result view showing synthetic provenance and hardware limitations](media/dashboard-dc-evidence.png)

These preserved screenshots demonstrate result/report presentation at that
checkpoint. The current software demo below generates a fresh report and chart.

</details>

## Try the software

Windows PowerShell; Python 3.10+ (primary local verification: Python 3.12).
The repository currently requires authorized GitHub access. Clone the current
product branch into a **new** directory; a default-branch clone installs the
older baseline. Installation may download build tools; running the demo is offline.

~~~powershell
git clone --branch codex/calibration-workflow --single-branch https://github.com/Carlos-0798/mixed-signal-afe-validation-platform.git avs-review
cd avs-review
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\analog-validation.exe demo --output .\portfolio-demo
.\.venv\Scripts\analog-validation.exe dashboard
~~~

**Expected result:** the demo runs a 24-point `SYNTHETIC` DC case and creates
12 artifacts. Open `portfolio-demo/report/report.html` to inspect the metrics,
criteria, chart, and conclusion; `result.json` and `manifest.json` retain the
machine-readable result and file identities. A software PASS is not hardware
validation. Repeating the command requires a new output name; existing evidence
is never overwritten.

In the Dashboard, use **Import data** for a supported voltage CSV, check the
converted preview, then continue through **Setup & run → Review → Run → Results**.
See [voltage import](docs/voltage-data-import.md),
[the deterministic demo](docs/software-demo.md), and
[installation help](docs/INSTALLATION.md). No board or serial driver is needed.

## Reuse a test project

~~~powershell
.\.venv\Scripts\analog-validation.exe project create --output .\demo-project.json --project-id demo --name "Demo project"
.\.venv\Scripts\analog-validation.exe project run --input .\demo-project.json --output .\run-001 --run-id run-001
~~~

The default project runs six Simulator presets. Each new run records the
configuration, outcomes, evidence class, and artifact hashes. History verifies
stored results before displaying them; it does not silently recalculate PASS/FAIL.
Saved projects exclude serial settings. See [projects and history](docs/test-projects-and-history.md).

## Architecture

~~~mermaid
flowchart TD
    Inputs["Simulator / voltage CSV / opt-in receive-only serial"]
    Adapters["Import mapping / public adapters and profiles"]
    Core["Typed measurements / reviewed criteria / analysis"]
    Worker["Shared execution / progress / cancellation / cleanup"]
    UI["Desktop Dashboard and CLI"]
    Results["Finalized results / reports / verifiable history"]
    Inputs --> Adapters --> Core
    UI --> Worker
    Worker --> Core
    Core --> Results
    Results --> UI
~~~

Device-specific parsing stays outside the analysis layer. GUI and CLI use the
same core; report rendering does not refit data or invent a new conclusion.
Atomic create-new publication and SHA-256 verification help detect damaged or
mismatched artifacts; hashes are not digital signatures or proof of hardware origin.

[Architecture details](docs/PRODUCT_ARCHITECTURE.md) ·
[Decisions](docs/adr/README.md) ·
[Public adapter example](docs/PUBLIC_ADAPTER_EXAMPLE.md)

## Verification

| Evidence checkpoint | Recorded result |
|---|---|
| [Local product synchronization, 2026-09-09](reports/private-github-sync-2026-09-09.md) | **3,048 tests passed; 17,567/17,567 package statements covered (100%)**; Ruff, mypy, pip check, and 15 product-quality checks passed |
| [Installed voltage-import acceptance, 2026-09-09](reports/td-052-voltage-import-2026-09-09.md) | 23 installed CLI commands across seven scenarios; real Tk import/review/report workflow; three synthetic table layouts produce identical Replay bytes |
| Cloud tests | Manual-only; no current hosted matrix PASS is claimed. Local tests are the primary gate |
| AFE hardware bench tests | Not run |

The full-suite counts belong to the linked product checkpoint, not to a new
run for each documentation edit. Coverage measures statements, not all branches
or real-world correctness. `HOST_TEST`, `SYNTHETIC`, `CSV_REPLAY`, `SPICE_IDEAL`,
`BENCH_CONTROLLER`, and `BENCH` remain distinct. Current demonstrations add no
hardware evidence: **`NO_NEW_HARDWARE_VALIDATION`**.

[Local testing and manual CI](docs/LOCAL_TESTING_AND_CI.md) ·
[Executed reports](reports/README.md) ·
[Known limitations](docs/KNOWN_LIMITATIONS.md)

## Scope and next step

The current focus is repeated voltage-data validation. Import supports explicit
UTF-8 delimited tables with voltage units and time mapping; it is not a universal
board driver, arbitrary-unit importer, or Excel workbook engine. New devices
need an interpretable format or a tested adapter/profile. Receive-only serial
support is opt-in; default demos do not enumerate or open ports.

Feature expansion is paused after local delivery. The next candidate is one
sample-driven input extension, selected from a real user dataset or protocol.
Screen-reader limitations and real-device/long-duration acquisition remain
documented gaps. Physical AFE validation and instrument-controlled sweeps are
future, separate work. See [current status](docs/PROJECT_STATUS.md) and
[the resume checkpoint](docs/PROJECT_RESUME_CHECKPOINT_2026-09-09.md).

AVS is independent of the MSP430 Equipment Health Controller and the
OSU Lab Bench Monitor Senior Capstone. A prior narrow `BENCH_CONTROLLER` UART
capture does not validate an AFE, sensors, wiring, or laboratory instruments.

<details>
<summary>Historical release-engineering evidence</summary>

The earlier Software Phase 6 baseline reached **7/8 checkpoints**. Its merged
software gate recorded **2,277 tests passed** and
**11,911/11,911 package statements covered**. The Step 7 release audit was
`PASS_WITH_REVIEW`; those records do not clear the present Git history for
publication. Historical reports remain unchanged:
[Step 7 audit](reports/software-phase6-step7.md) and
[2026-09-04 handoff](reports/PROJECT_MILESTONE_UPDATE_2026-09-04.md).

</details>

## License and development

This branch uses the owner-selected [MIT License](LICENSE).
[Third-party notices](THIRD_PARTY_NOTICES.md), [contributing](CONTRIBUTING.md),
[security](SECURITY.md), and [publication checklist](docs/PUBLICATION_CHECKLIST.md)
describe the development and distribution boundaries. Repository visibility,
merging the Draft PR, and publishing a release remain separate owner decisions.
