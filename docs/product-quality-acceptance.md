# Product-quality acceptance

## Scope

Software Phase 5 Step 7 checks whether the local product remains responsive,
bounded, keyboard-usable, offline, and private by default at its reviewed
limits. These are host-software checks. They are not hard real-time benchmarks
and do not validate a physical AFE.

Rerun the measured acceptance with:

```powershell
.\.venv\Scripts\python.exe -m tools.product_quality_acceptance
```

Use `--output <new-file.json>` to retain a create-new machine record.

## Reviewed targets and recorded Windows result

The following result was recorded on 2026-08-31 with CPython 3.12.10 on Windows
11 AMD64. Wall-clock values vary by host; the fixed limits are deliberately
broad product-interaction guards rather than performance marketing claims.

| Check | Target | Recorded result | Status |
|---|---:|---:|---|
| Parse strict CSV Replay | 10,000 records in ≤ 5.0 s | 0.823268 s | PASS |
| Parser peak traced memory | ≤ 128 MiB at 10,000 records | 13.102 MiB | PASS |
| Process progress volume | 10,000 events in ≤ 5.0 s | 0.048879 s | PASS |
| Retained worker events | ≤ 256 | 256 | PASS |
| Dropped-event accounting | visible and monotonic | 9,747 dropped; last index 10,003 | PASS |
| Worker cleanup | terminal `SUCCEEDED`, cleanup complete | yes | PASS |
| Complete demo publication | ≤ 5.0 s | 0.040913 s, 12 artifacts | PASS |

The parser tiers of 100, 1,000, and 10,000 records were all executed. The event
queue kept its newest bounded snapshot rather than allowing memory to grow with
the producer.

## Accessibility acceptance

- Outcome, evidence class, worker state, limitations, missing requirements, and
  safe next steps are expressed in text; color is supplementary.
- Buttons, selection controls, cancellation, and the finalized-point table are
  explicit keyboard focus targets using standard Tk traversal.
- A real Windows Tk smoke created the workflow at Tk scaling values 1.0, 1.5,
  and 2.0 and confirmed positive requested geometry and focus traversal.
- The HTML report includes a responsive viewport, semantic headings, scoped
  table headers, text status, and no script dependency.
- This is an automated accessibility baseline, not a claim of certification
  against every WCAG or platform assistive-technology criterion.

## Privacy and hostile-input acceptance

- Demo generation was run with socket creation replaced by a fail-fast trap;
  it completed without requesting a network socket.
- Architecture tests reject network, serial-driver, Tk, subprocess, device,
  protocol, and analysis implementations inside the demo module.
- Different normal and Unicode output paths produced byte-identical artifacts.
- Existing destinations and missing parents fail closed; staging is cleaned
  after guarded write or rename failures.
- Absolute output paths, usernames, COM identifiers, and raw serial payloads do
  not appear in committed demo artifacts.
- Existing report/replay tests retain HTML/Markdown/SVG escaping, spreadsheet
  formula prevention, strict UTF-8, bounded fields, maximum-size input, and
  default no-overwrite coverage.

## Clean-install observation

The wheel installed and passed `pip check` in a fresh short-path environment
outside the repository. Two installed demos in normal and Unicode destinations
were byte-identical. A first attempt to place the virtual environment below the
repository's already deep `work/` path failed with Windows `WinError 206`; this
is recorded as a path-length condition, not counted as a passing install.

## What remains unverified

- sustained behavior beyond the bounded 10,000-record/event acceptance;
- hard deadlines, process scheduling latency, or real-time guarantees;
- screen-reader behavior across all Windows configurations;
- long-duration physical serial transport;
- physical AFE electrical performance or safety.
