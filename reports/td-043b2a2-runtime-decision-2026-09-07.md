# TD-043B2A2 accessible Dashboard runtime decision

Date: 2026-09-07<br>
Status: **COMPLETE — decision recorded; production migration not started**<br>
Evidence: **HOST_TEST only**

## Outcome

The runtime spike rejects Tk 9.1 beta as the next production candidate and
selects PySide6 Essentials with Qt Widgets as the preferred migration prototype.
ADR-0004 remains Proposed because no GUI dependency or licensing change has
been approved.

This result does not make the current Tk Dashboard screen-reader compatible.
It chooses the next engineering route based on an actual Windows UI Automation
comparison.

## Local runtime inventory

- One installed Python: CPython 3.12.10, AMD64.
- `_tkinter.pyd` comes from the Python 3.12 installation.
- Compiled Tcl and Tk ABI: 8.6.
- Runtime Tk patch level: 8.6.15.
- `tk accessible`: unavailable.

Changing `TCL_LIBRARY`, copying a new DLL, or installing Tcl/Tk beside this
interpreter would not safely change the ABI to Tk 9.1. A different `_tkinter`
build and matched runtime would be required.

## Official support findings

- CPython merged Windows Tk 9.0.4 support into the 3.14 branch in August 2026.
- Tcl/Tk 9.0.4 has no `tk accessible` command.
- Accessibility TIP 733 targets Tcl/Tk 9.1, which is currently a beta source
  release rather than the stable Python Windows runtime used by this product.
- TIP 733 says the Windows bridge is driven by MSAA, was developed mainly with
  NVDA, and gives Narrator a weaker experience because Narrator primarily uses
  UI Automation.

Therefore neither the installed Python nor an ordinary move to Python 3.14
solves the requirement. Shipping a custom Python/Tk 9.1 beta combination would
add runtime, installer, reproducibility, and assistive-technology risk before
the product can test its own UI.

## Isolated Qt prototype

The prototype was created outside the repository under the conversation work
directory. It used Python 3.12.10, PySide6 Essentials 6.10.1, and shiboken6
6.10.1. It opened no file, port, device, or network connection after package
installation and created no product artifact.

| Observation | Tk 8.6.15 Dashboard | Qt Widgets prototype |
|---|---:|---:|
| Named application controls in UIA | 0 | 6 |
| Application input roles | Unnamed Pane | ComboBox and Edit |
| Application action role | Unnamed Pane | Button |
| Keyboard-focusable application controls | 0 in UIA | 3 |
| Dynamic status property | Not exposed | Updated from `Run status` to `Run status: READY; setup validated` |

The Qt prototype exposed visible labels, the Source combobox, Replay path edit,
status text, and Validate button with meaningful UIA names and roles. This is a
stronger foundation than the candidate Tk runtime. Event capture, Narrator,
NVDA, full workflow behavior, high contrast, scaling, and real-user testing
remain future gates.

## Cost and compatibility

- PySide6 Essentials wheel downloaded: 74.5 MB.
- Prototype site-packages footprint: approximately 206.3 MiB.
- License metadata: LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only; Qt also offers
  commercial licensing.
- The official wheels include Qt binaries, improving runtime reproducibility but
  increasing package and notice obligations.

No project license, third-party notice, `pyproject.toml`, base wheel, entry
point, or public API changed in this stage.

## Migration boundary

Only `dashboard/app.py` directly imports tkinter. Tk widgets are concentrated in
`dashboard/widgets.py` and `dashboard/project_widgets.py`. The existing state,
presenter, application, wizard, project workspace, services, worker, CLI,
project/history, manifest, and evidence layers are GUI-independent.

The next implementation should therefore be a Simulator-only Qt vertical slice
that calls the existing application actions and renders the existing immutable
states. It must not duplicate business decisions or include Serial discovery.

## Verification

| Gate | Result |
|---|---|
| Local Python/Tk ABI inspection | PASS |
| Official Python/Tk support review | PASS |
| Isolated PySide6 Essentials install | PASS |
| Qt window creation | PASS |
| UIA names and roles | PASS — six application controls |
| UIA focusability | PASS — combobox, edit, button |
| Dynamic status property polling | PASS |
| UIA accessibility event capture | NOT RUN |
| Narrator/NVDA chain | NOT RUN |
| Production dependency/license change | NOT PERFORMED |
| Serial/hardware access | NOT PERFORMED |

## Evidence boundary

- `HOST_TEST`: runtime inventory, documentation review, package isolation,
  prototype window, and UI Automation inspection.
- `SYNTHETIC`: no new product run produced.
- `CSV_REPLAY`: no new product run produced.
- `SPICE_IDEAL`: not produced.
- `BENCH_CONTROLLER`: not produced or extended.
- `BENCH`: not produced.

The prototype is display-runtime evidence only and makes no hardware claim.

## Recommended next slice

After explicit approval for an optional PySide6 dependency and its LGPL/notice
work, implement a narrow Qt Widgets shell for the Simulator Source, workflow
step/guidance, validation issue, Run status, safe cancellation, and finalized
Result. Keep the current Tk entry point intact. Acceptance must include state
parity tests, UI Automation names/roles/focus/events, standard/high-contrast
rendering, scaling, complete keyboard operation, no Serial imports/actions, and
unchanged CLI/API/manifest golden files.
