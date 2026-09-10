# Portfolio copy and publication preview

Reviewed 2026-09-10. Current implemented software is on
`codex/calibration-workflow`; [Draft PR #10](https://github.com/Carlos-0798/mixed-signal-afe-validation-platform/pull/10)
is not merged. The repository remains private. This file supplies copy for owner
review; it does not authorize LinkedIn posting or public exposure.

## Project title and role

**Analog Validation Studio — Python Test Automation & Data Analysis**

**Independent Project Developer**

AVS is an independent personal software project. The MSP430 Equipment Health
Controller is a separate peer product. The OSU Lab Bench Monitor Senior Capstone
is a separate team project and contributes no team deliverables to this repository.

## Short description

> Local Python desktop app and CLI that turn voltage CSV files into reusable
> validation workflows, plots, reports, and verifiable test history. Includes
> explicit unit mapping, saved test presets, batch progress/cancellation, and
> traceable input/result artifacts.

## Resume or interview summary

- Designed a controller-neutral Python core and shared CLI/Tkinter execution
  path for voltage-data import, DC gain/offset/linearity, hysteresis, calibration,
  and amplitude-frequency analysis.
- Automated reusable CSV mapping, reviewed batch execution, report generation,
  and project history; preserved partial results after cancellation and retained
  source inputs with versioned manifests and SHA-256 verification.
- Verified the software with **3,048 passing local tests and 100% package
  statement coverage (17,567 statements)**, plus fresh-installed CLI and real
  desktop workflow acceptance at the linked checkpoints.

The test count belongs to the [2026-09-09 product synchronization gate](../reports/private-github-sync-2026-09-09.md).
The installed CLI/GUI evidence belongs to the earlier
[TD-052 acceptance](../reports/td-052-voltage-import-2026-09-09.md), which had
3,047 tests before one added portability regression. Neither is a new test run
for a later documentation change. Do not claim 100% branch coverage.

## Suggested repository metadata

The description and topics below are already synchronized on GitHub. They are
retained here as the reviewed wording, not a request for another settings change.

Description:

> Python desktop app and CLI for repeatable voltage-data validation: CSV import,
> automated analysis, plots, reports, and verifiable test history.

Topics:

~~~text
python
test-automation
data-analysis
csv
desktop-application
tkinter
analog-validation
embedded-systems
~~~

Avoid a `hardware-validation` topic that could imply completed AFE bench work.
Device integration is an extension boundary, not universal board compatibility.

## Reviewer route and visual assets

Start with the [two-minute reviewer guide](REVIEWER_GUIDE.md), then the
[README demo](../README.md#try-the-software),
[architecture](PRODUCT_ARCHITECTURE.md), and recorded verification above.

Current screenshots show the real three-theme voltage importer:
[Workbench](../media/dashboard-import-workbench-20260909.jpg),
[Daylight](../media/dashboard-import-daylight-20260909.jpg), and
[Midnight](../media/dashboard-import-midnight-20260909.jpg).
The table is synthetic and its preview is `CSV_REPLAY`, not a hardware capture.
The [media register](../media/README.md) retains capture dates and hashes.

A social-preview upload or LinkedIn post is a separate action. Reuse only
reviewed assets and label their evidence. Private repository links are usable
only by authorized reviewers, not by ordinary external recruiters.

## Claims and next step

Describe implemented automation and the manual steps it replaces. Quantitative
human time savings and operator-error reduction remain unmeasured. Do not claim
physical AFE accuracy, production deployment, certification, universal devices,
or OSU endorsement. `HOST_TEST`, `SYNTHETIC`, `CSV_REPLAY`, `SPICE_IDEAL`,
`BENCH_CONTROLLER`, and `BENCH` remain separate evidence classes.

Testing is [local-first, with cloud CI only on explicit manual request](LOCAL_TESTING_AND_CI.md).
Hosted CI is not required for routine synchronization or portfolio preparation.
An unexecuted hosted matrix remains NOT_RUN; a historical badge is not evidence
that the current software passed it. A future cloud run needs the owner's
explicit instruction for that run.

The current branch already uses the owner-selected MIT license; main retains
its older license file until separately authorized integration. Do not change
either license as part of presentation work. Before public sharing, assess the
exact proposed source/history and assets, choose the intended revision, and
obtain separate owner approval for visibility and any release or social post.
The [resume checkpoint](PROJECT_RESUME_CHECKPOINT_2026-09-09.md) preserves the
completed scope and sample-driven TD-053 plan.

## Copy-ready LinkedIn project entry

**Title:** Analog Validation Studio — Python Test Automation & Data Analysis

**Role:** Independent Project Developer

**Dates:** Keep the actual August 2026 start date shown on the existing profile.
Use “Present” if maintenance continues; an August–September 2026 range may
describe the completed software phase if that is the owner's intended scope.
The implemented software does not need an “In Development” title qualifier.

**Description:**

> Developed an independent Python desktop application and CLI for repeatable
> voltage-data validation, turning CSV preparation, gain/offset/linearity
> analysis, and reporting into a reusable workflow.
>
> • Defined the product scope and a controller-neutral architecture, with a
> shared analysis core for desktop and CLI workflows.
>
> • Implemented reusable CSV mappings, saved test presets, cancellable batch
> runs, and automated plots and reports; preserved completed results when later
> steps failed.
>
> • Added strict input validation, versioned manifests, archived source data,
> and SHA-256 verification to make results reproducible and traceable.
>
> • Verified the software with 3,048 passing local tests and 100% package
> statement coverage, supported by documented fresh-install CLI and desktop
> workflow checks.
>
> Current evidence covers software, simulator, and CSV-replay workflows;
> physical analog front-end performance remains unvalidated.

**Skills:** Python; Test Automation; Software Architecture; Data Analysis; Debugging.

**Project URL after public verification:**
[GitHub repository](https://github.com/Carlos-0798/mixed-signal-afe-validation-platform).
The old profile's breadboard/PCB wording describes a separate hardware plan;
do not carry it into this software entry as completed work.

## AI-assisted development: accurate interview wording

This optional note is for questions about the development process. The main
project description should demonstrate engineering decisions and delivered
behavior; it need not list every development tool.

> I used AI-assisted development tools during implementation and documentation.
> My responsibilities centered on problem definition, architecture and scope
> decisions, and verification criteria. Changes were checked through regression
> tests and reproducible evidence.

Do not describe AI-assisted implementation as entirely hand-written, or automated
review as human team review. Preserve historical tool references and evidence.
“Manual-only cloud CI” describes when a workflow is requested, and manual task
baselines describe the problem being automated; neither is a claim about code
authorship. Human efficiency measurements remain unperformed.

Publication decisions and the remaining review items are tracked in the
[publication checklist](PUBLICATION_CHECKLIST.md) and
[dated closeout review](../reports/publication-readiness-2026-09-10.md).
