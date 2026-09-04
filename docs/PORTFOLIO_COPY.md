# Portfolio copy and publication preview

Status: local draft for owner review; nothing in this file authorizes a remote
change. Last reviewed: 2026-09-03.

This page keeps GitHub and LinkedIn wording synchronized while preserving the
project's evidence boundary. The project is an independent software product.
The MSP430 profile is one peer integration; the separate MSP430 project and the
OSU Lab Bench Monitor Capstone are not part of this repository.

## GitHub repository preview

### Description

> Controller-neutral Python platform for analog-validation workflows:
> deterministic simulation, CSV replay, receive-only serial profiles,
> DC/hysteresis analysis, evidence-aware reports, and a local Dashboard.

### Recommended topics

~~~text
analog-validation
test-automation
python
mixed-signal
data-acquisition
uart
crc16
desktop-application
embedded-systems
~~~

Do not use `hardware-validated`, `production-ready`, or similar topics until a
separate bench-evidence gate supports them. Consider replacing the current
`hardware-validation` topic with `analog-validation` before public exposure so
the short metadata cannot be mistaken for a hardware-performance claim.

### Social-preview candidate brief

- Title: **Analog Validation Studio**
- Subtitle: **Offline · Simulator-first · Evidence-aware**
- Visual: the real DC-sweep Dashboard screenshot in
  [`media/dashboard-dc-evidence.png`](../media/dashboard-dc-evidence.png)
- Required label: **SYNTHETIC EVIDENCE · NO NEW HARDWARE VALIDATION**
- Target: 1280×640 PNG or JPG, with readable text at thumbnail size

Creating or uploading the final social-preview asset remains a separate,
owner-approved action. A README screenshot is not automatically the repository
social preview.

## LinkedIn project preview

### Title

**Analog Validation Studio — Analog Validation & Test Automation Platform**

### Role

**Independent Product Designer and Developer**

### Description

> Designed and implemented a controller-neutral Python platform for repeatable
> analog-validation workflows. Built deterministic simulation and CSV replay,
> receive-only serial adapters, CRC-16/CCITT-FALSE parsing, DC-sweep and
> hysteresis analysis, evidence-aware reports, a desktop Dashboard, CI,
> packaging, and release-governance checks. The current beta is validated with
> synthetic and host-test evidence; physical AFE hardware remains a separate
> future phase. An MSP430 profile is supported as a peer integration, not a
> dependency.

### Suggested skills

- Python
- Test Automation
- Software Architecture
- Embedded Systems
- Data Analysis
- Continuous Integration and Continuous Delivery (CI/CD)

### Featured link

Use the final public repository URL only after the public-view checklist passes.
Use the repository's social preview or DC-evidence screenshot as media only
after confirming that the exact image is public and contains no local paths or
private data.

## Claims gate

Safe after the exact public commit and its hosted CI pass:

- controller-neutral, offline-first analog-validation software;
- deterministic Simulator and CSV-replay workflows;
- opt-in, receive-only serial integration boundary;
- versioned UART CSV plus CRC-16/CCITT-FALSE support;
- tested DC-sweep and hysteresis analysis;
- packaged CLI, local Dashboard, reports, demo, and extension contracts;
- the exact test and coverage counts shown by that public commit's CI.

Not safe without additional evidence:

- a physical AFE was built, calibrated, measured, or validated;
- electrical protection, wiring, accuracy, reliability, or safety was proven;
- the MSP430 board or school instruments were used for the displayed results;
- OSU sponsored, endorsed, or owns this independent project;
- production readiness, certification, or field deployment.

## Approval sequence

1. Review the exact commit diff and rerun the release candidate gate.
2. Push only the approved commit and wait for hosted CI.
3. Review the rendered GitHub page while signed out.
4. Approve repository description, topics, visibility, and license separately.
5. Approve the social-preview image separately.
6. Copy the frozen LinkedIn wording only after the public URL is stable.
