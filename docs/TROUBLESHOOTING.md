# Troubleshooting the private beta

Use the least invasive recovery first. The base Simulator/demo path never
requires administrator access, execution-policy changes, serial hardware, or
laboratory equipment.

| Symptom | Likely cause | Safe next step |
|---|---|---|
| Candidate SHA-256 differs | incomplete, changed, or wrong file | Stop; keep the files; report expected/actual hashes to the owner |
| `py` or `python3.12` is not found | Python 3.12 is missing or not registered | Install supported 64-bit Python from python.org; do not substitute an unknown interpreter |
| `analog-validation` is not found | wrong shell environment or failed install | Invoke the exact console path inside the new venv; rerun `pip check` |
| PowerShell blocks `Activate.ps1` | execution policy prevents activation | Do not change policy; use the full venv executable paths from `INSTALLATION.md` |
| `No matching distribution` or Python-version error | unsupported Python or wrong package | Confirm Python 3.10/3.12/3.14 and wheel version; Python 3.12 is recommended |
| `WinError 206` / filename too long | venv/output is nested too deeply | Start again under a short directory such as `C:\avs-beta`; preserve prior evidence |
| `OUTPUT_EXISTS` | create-new protection found prior output | Choose a new directory name; do not automatically delete the earlier run |
| `OUTPUT_PATH` / permission denied | parent missing, read-only, synchronized, or protected | Create a short private writable directory outside protected/system folders |
| Version is not `0.1.0b1` | mixed environment or older install | Stop; create another new venv and install only the reviewed wheel |
| Base install asks for pyserial | wrong install command or package | Stop; use `--no-deps` with the exact wheel and report the unexpected behavior |
| Dashboard reports missing Tk/display | interpreter lacks Tk or session is headless | Record optional GUI as `NOT_RUN`; continue using the required CLI path |
| Demo reports `FAIL` | deterministic result or package behavior changed | Keep the demo directory; submit sanitized command/result fields and hashes |
| Demo reports `INCOMPLETE`/`UNSUPPORTED` | wrong command/config or missing evidence | Compare the exact required command; do not reinterpret it as PASS |
| Exit code `70` | unexpected internal software error | Retain sanitized stdout/stderr and steps; do not post a full environment dump |
| Process does not close | cleanup/cancellation problem | Stop interacting, note elapsed time and command category, then report it |

## What a useful diagnostic contains

Include:

- OS family/version;
- Python version/architecture;
- package version JSON;
- command category, with paths replaced by `<beta-root>`;
- exit code and controlled issue code;
- expected versus actual outcome/evidence/hardware-claim fields;
- wheel and generated manifest SHA-256 values;
- minimal ordered reproduction steps.

Do not include:

- username, email, home directory, or full absolute paths;
- access token, cookie, private URL, or repository credential;
- physical port identifier, USB serial number, VID/PID, or device identity;
- raw UART bytes, sensor values, private data files, or entire environment dumps;
- the wheel/sdist/candidate bundle itself.

## Optional serial errors

Serial is outside the required beta path. A missing pyserial dependency should
map to an optional-dependency explanation. A port open, timeout, disconnect, or
profile mismatch must not be worked around by guessing another port/profile.
Stop and request a device-specific approved procedure.

The current product adapter is receive-only, but opening a port can still
change OS control-line state. That is why serial tests remain separately gated
even when the application exposes no write method.

## Still blocked?

Read [Known limitations](KNOWN_LIMITATIONS.md), then use the sanitized GitHub
issue form. Choose `BLOCKED` only for the required base path; record optional
Dashboard/Replay/Serial items independently.
