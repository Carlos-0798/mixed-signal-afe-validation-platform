# Dashboard interaction design audit

Status: implemented and merged to `main` through Dashboard UX PR #7. This audit
covers software interaction only. It does not access a serial port and does not
add any hardware-validation claim.

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
| System status | Worker state, event count, progress, outcome, evidence source, limitations, and saved artifacts remain visible as text | Meets the visual status baseline; assistive-technology announcement remains a manual audit item |
| Primary and secondary actions | Forward/commit actions receive primary emphasis; navigation, discovery, reset, and close actions are secondary; `Choose save location...` correctly signals that a dialog follows | Corrected so `Start new test` no longer competes visually with Save |
| Short and long pages | Pages start at the top; the vertical scrollbar and wheel activate only when content exceeds the viewport | Corrected and covered by fake-toolkit plus real-Tk tests |
| Native save flow | The operating-system save picker is parented to the app, suggests `analog-validation-result.json` or `.csv`, and restricts the picker to the selected supported format | Corrected in this follow-up |
| Format integrity | Manual paths whose suffix conflicts with the selected JSON/CSV format are rejected before a file is created | Corrected in this follow-up |
| Repeated-run output safety | Each newly finalized analysis clears the previous destination so create-new export cannot accidentally reuse it | Corrected in this follow-up |
| Accidental data loss | Modify, review-again, new-test, and close actions ask before discarding the only unsaved finalized analysis; the default answer is No | Corrected in this follow-up |
| Input limits | Count fields show their allowed range and the combined hysteresis limit before validation | Corrected in this follow-up |
| Error explanation | The issue card shows severity/code, what happened, a possible cause, and a safe next step; meaning is not color-only | Meets the current text baseline |
| Keyboard and scaling | Interactive controls opt into focus traversal; each step moves focus away from disabled/hidden prior controls; automated Windows Tk checks cover scaling 1.0, 1.5, and 2.0 | Corrected step-transition focus; this is not a full accessibility certification |
| Responsiveness | A single worker owns long-running acquisition and the UI polls immutable state; Tk rendering stays on the UI thread | Meets the selected Tk event-loop pattern |
| Evidence integrity | `SYNTHETIC`, `CSV_REPLAY`, and host evidence remain explicit, and the UI does not turn software PASS into hardware validation | Meets the project evidence boundary |

## Deliberately deferred improvements

These are useful follow-ups, but they need a larger contract or dedicated user
study and should not be slipped into a low-risk UX patch:

1. Add a structured `field_id` to validation issues, then focus and visually
   identify the first invalid field without parsing English error text.
2. Perform a Windows screen-reader audit of changing run status and validation
   messages. Tk focus traversal alone is not proof of announcement quality.
3. Test high-contrast themes, 125%/175% scaling, small laptop displays, Remote
   Desktop, and keyboard-only long sessions with real users.
4. Add keyboard accelerators only after deciding on a visible, documented set;
   hidden shortcuts would reduce discoverability for the beginner workflow.
5. Consider localization only after all user-facing strings have stable message
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
