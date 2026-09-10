# Dashboard interaction design audit

Status: the baseline is merged to `main` through Dashboard UX PR #7; TD-043A
through TD-046B are local, uncommitted follow-ons. This audit covers software
interaction only. It does not access a serial port and does not add any
hardware-validation claim.

## Reference basis

The review used the following public design and teaching references:

- Nielsen Norman Group, [10 Usability Heuristics for User Interface
  Design](https://www.nngroup.com/articles/ten-usability-heuristics/): visible
  system status, user control, error prevention, consistency, recognition over
  recall, and actionable error recovery.
- U.S. Web Design System, [Step
  indicator](https://designsystem.digital.gov/components/step-indicator/): use
  a step indicator for a linear multi-step process, keep Back/Next navigation
  separate, and show an explicit `step of total` heading.
- Microsoft Learn, [Save a file with a Windows App SDK
  picker](https://learn.microsoft.com/en-us/windows/apps/develop/files/pickers-save-file):
  use the system picker, suggest a relevant filename and extension, and offer
  only supported formats.
- Microsoft Learn, [Keyboard
  interactions](https://learn.microsoft.com/en-us/windows/apps/develop/input/keyboard-interactions):
  make actionable controls keyboard reachable and keep focus order logical.
- Microsoft Learn, [Commanding
  basics](https://learn.microsoft.com/en-us/windows/apps/design/basics/commanding-basics)
  and [Dialogs and
  flyouts](https://learn.microsoft.com/en-us/windows/apps/design/controls/dialogs-and-flyouts/):
  use concise action-specific labels, keep command priority visible, and ask
  for additional information or confirmation in a clear dialog.
- W3C WAI, [Error
  identification](https://www.w3.org/WAI/WCAG22/Understanding/error-identification),
  [Focus order](https://www.w3.org/WAI/WCAG22/Understanding/focus-order.html),
  [Focus visible](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible),
  and [Status
  messages](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html):
  identify errors in text, preserve a meaningful focus sequence, keep keyboard
  focus visible, and expose important state changes without needless
  interruption.
- TkDocs, [Windows and
  dialogs](https://tkdocs.com/tutorial/windows.html) and [Event
  loop](https://tkdocs.com/tutorial/eventloop.html): use native platform file
  dialogs, keep Tk calls on the UI thread, and move long-running work out of
  event handlers.

WCAG and web-design sources are used here as transferable interaction
principles. This document does not claim formal WCAG, screen-reader, or
Windows-certification conformance.

## Findings and disposition

| Area | Evidence in the product | Disposition |
| --- | --- | --- |
| Process orientation | Six fixed steps, a current-step heading, and separate Previous/Continue actions | Meets the selected linear-wizard pattern |
| System status | Worker state, event count, progress, outcome, evidence source, limitations, and saved artifacts remain visible as text; the Tk 9.1 adapter can publish distinct status changes when the runtime provides `tk accessible` | Meets the visual status baseline; the current Tk 8.6.15 candidate cannot expose these values to screen readers |
| Primary and secondary actions | Forward/commit actions receive primary emphasis; navigation, discovery, reset, and close actions are secondary; `Choose save location...` correctly signals that a dialog follows | Corrected so `Start new test` no longer competes visually with Save |
| Short and long pages | Pages start at the top; the vertical scrollbar and wheel activate only when content exceeds the viewport | Corrected and covered by fake-toolkit plus real-Tk tests |
| Native save flow | The operating-system save picker is parented to the app, suggests `analog-validation-result.json` or `.csv`, and restricts the picker to the selected supported format | Corrected in this follow-up |
| Format integrity | Manual paths whose suffix conflicts with the selected JSON/CSV format are rejected before a file is created | Corrected in this follow-up |
| Repeated-run output safety | Each newly finalized analysis clears the previous destination so create-new export cannot accidentally reuse it | Corrected in this follow-up |
| Accidental data loss | Modify, review-again, new-test, and close actions ask before discarding the only unsaved finalized analysis; the default answer is No | Corrected in this follow-up |
| Input limits | Count fields show their allowed range and the combined hysteresis limit before validation | Corrected in this follow-up |
| Terminology and source boundaries | Source/Test selectors use readable display aliases that round-trip to stable enum values; Configure shows a plain-language guide for all six tests and the selected source; Simulator and Replay explicitly retain `SYNTHETIC` or `CSV_REPLAY`, while Serial selection states that no port has been discovered or opened | Corrected without changing evidence, result, project, or manifest contracts |
| Relevant source controls | Replay and Serial details are mutually exclusive; Replay exposes a native CSV picker, required path, optional bounds, and Cancel preserves the current path | Corrected while retaining Review as the only file-read and strict-validation boundary |
| Disabled-action explanation | The action area follows the existing wizard permissions and names the next action, the review requirement before Run, or the field correction required after validation failure | Corrected without adding a second permission state machine |
| Result interpretation | A first-read summary separates run completion, engineering decision, exact evidence meaning, claim boundary, and next action; detailed limitations and issue recovery remain directly below | Corrected without recomputing or upgrading any result |
| History comparison interpretation | A guide names baseline/candidate runs and batch states, snapshot drift, matched/one-sided/not-started coverage, evidence-label mismatch, changed presets, and arithmetic delta direction before the detailed table | Corrected without changing manifest/comparison schemas or assigning improvement/regression |
| Project first use and empty states | The page names the next valid action, previews the current Setup/evidence boundary, distinguishes no/one/multiple history runs, and maps Save/Add/Review/Run/Compare/Clear to existing workspace permissions | Corrected without introducing a second state machine; invalid or not-yet-rendered Setup previews recover safely |
| Batch Review comprehension | Before Run, a structured frozen-review table shows exact project/run identity, create-new destination, project-order presets, readable Source/Test names, and each exact evidence label | Corrected as a read-only projection of the accepted Review; it clears when Run consumes that Review and does not read Replay or change execution contracts |
| Error explanation and recovery | The issue card shows severity/code, what happened, a possible cause, and a safe next step; validation also names, focuses, highlights, and scrolls to the exact field when a stable internal field key is available | Corrected and covered by fake-toolkit plus five-scaling real-Tk tests; unknown fields keep the text-only fallback |
| Keyboard and scaling | Interactive controls opt into focus traversal; each step moves focus away from disabled/hidden prior controls; automated Windows Tk checks cover a 1040×760 window at scaling 1.0, 1.25, 1.5, 1.75, and 2.0 and reject horizontally clipped or over-compressed critical controls on Setup, Results, and Projects | Six-column configuration groups now use three-column reflow and result widths obey the viewport; this is not a full accessibility certification |
| High contrast | Startup reads the Windows high-contrast flag without changing it; enabled mode uses system window/text/highlight/disabled colors for ttk controls, native canvases, focus, selection, and errors while retaining textual meaning | Automated standard/forced-high-contrast Tk rendering passed at five scaling levels; changing the OS theme while open requires restart and real-user assistive-technology validation remains pending |
| Screen reader semantics | A runtime gate detects the official Tk metadata API; a future-capable runtime receives stable names, roles, help text, chart/table text alternatives, and deduplicated step/issue/run/result notifications | Current Tk 8.6.15 has no API. Windows UI Automation saw 37 unnamed application panes, so screen-reader Dashboard support is explicitly blocked rather than inferred from Tab behavior |
| Responsiveness | A single worker owns long-running acquisition and the UI polls immutable state; Tk rendering stays on the UI thread | Meets the selected Tk event-loop pattern |
| Evidence integrity | `SYNTHETIC`, `CSV_REPLAY`, and host evidence remain explicit, and the UI does not turn software PASS into hardware validation | Meets the project evidence boundary |

## Deliberately deferred improvements

These are useful follow-ups, but they need a larger contract or dedicated user
study and should not be slipped into a low-risk UX patch:

1. After approval of Proposed ADR-0004, implement a Simulator-only PySide6 Qt
   Widgets vertical slice, then run UI Automation event, Narrator/NVDA,
   state-parity, and real-user tests. The isolated prototype exposed correct
   names/roles/focus and a changing status property, but did not test event
   announcements or the full workflow.
2. Test Remote Desktop and keyboard-only long sessions with real users. The
   automated lower-width boundary is 1040 pixels; smaller displays are not yet
   supported.
3. Add keyboard accelerators only after deciding on a visible, documented set;
   hidden shortcuts would reduce discoverability for the beginner workflow.
4. Consider localization only after all user-facing strings have stable message
   identifiers; translating ad hoc literals would create drift.

## Manual acceptance additions

For each test below, use Simulator only:

1. Complete a DC analysis and choose **Finish & close** before saving. The app
   must ask whether to discard the unsaved result, with **No** as the safe
   default. Choose No and confirm the result remains visible.
2. Choose **Start new test**, **Modify setup**, and **Review same setup** before
   saving. Each action must provide the same escape route. After one successful
   export, these prompts should no longer appear for that finalized result.
3. Select JSON but type a path ending in `.csv` (and vice versa). Save must fail
   with a readable suffix error and must not create a file.
4. Run two analyses in sequence. The second Result page must start with an empty
   destination field even when the first result was saved.
5. Open the save picker for each format. It should suggest a matching filename,
   show only that format, and leave the existing field unchanged after Cancel.
6. At 1040×760, traverse Setup, Results, and Projects using only the keyboard.
   No required field or action may require horizontal scrolling.
7. Start Windows high contrast before launching the Dashboard. Confirm focus,
   selection, disabled controls, error borders, charts, and text remain visible.
   Change the OS theme while the app is open and confirm the documented restart
   requirement rather than assuming live theme switching.
8. With Simulator selected, enter Configure for each of the six tests. Confirm
   the field guide changes with the test and always labels the source as
   `SYNTHETIC`; a software PASS must not be described as hardware validation.
9. At Source, Test, Configure, failed validation, and Review, compare the action
   hint with enabled buttons. It must never invite Run before a valid compiled
   review, and a failed validation must say which recovery action comes next.
10. Create two Simulator project runs, select both history rows, and compare.
    Confirm the guide names baseline/candidate, `SYNTHETIC`, result coverage,
    changed presets, and `candidate - baseline`. A positive delta must not be
    described as improvement without consulting the requirement direction.
11. Open Projects & history before creating a project. Confirm Save, Add,
    Review, Run, Compare, and Clear are unavailable and the page explains Create
    or Open. Create a project, choose one preset and an output directory, Review,
    then change the Run ID; Run must become unavailable and the page must ask for
    Review again. No Serial discovery may occur.
12. Review two Simulator presets selected in reverse click order. Confirm the
    frozen table uses project order, names the project, run, exact create-new
    destination, readable Source/Test values, and `SYNTHETIC` for both rows.
    Choose Run and confirm the consumed Review table clears while the real batch
    progress and terminal history take over.
