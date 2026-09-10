# Installation

- **Audience:** first-time software user or invited package tester
- **Package:** `mixed-signal-afe-validation-platform 0.1.0b1`
- **Default test source:** deterministic Simulator
- **Hardware required:** none

## Start from the source on main

The completed software is on the default `main` branch. No tagged Release or
prebuilt public download is published. Use a new, short directory and Python
3.12 for the primary verified Windows setup:

~~~powershell
git clone https://github.com/Carlos-0798/mixed-signal-afe-validation-platform.git avs-review
cd avs-review
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\analog-validation.exe version --json
.\.venv\Scripts\analog-validation.exe demo --output .\portfolio-demo --json
~~~

Installation may download build tools. The base software has no third-party
runtime dependency; running the Simulator demo is offline and requires no
hardware. Expect version `0.1.0b1`, a 24-point `SYNTHETIC` PASS and 12 files.
Open `portfolio-demo/report/report.html` to inspect the result. Use a new output
directory for each run; existing evidence is never overwritten.

For the GUI, run `.\.venv\Scripts\analog-validation.exe dashboard`. Tkinter
requires a normal desktop and a Python installation with Tk. See the
[README workflow](../README.md#try-the-software) and [troubleshooting](TROUBLESHOOTING.md).
Software PASS is not physical AFE validation.

## Optional: an owner-provided package

The remaining package instructions apply only if the owner separately supplies
a reviewed candidate bundle. A source clone does not contain the following
prebuilt files; source users can use the path above.

The owner-provided candidate directory contains exactly three files:

```text
release-candidate/
├── mixed_signal_afe_validation_platform-0.1.0b1-py3-none-any.whl
├── mixed_signal_afe_validation_platform-0.1.0b1.tar.gz
└── release-manifest.json
```

The wheel is the normal tester installation file. The sdist is retained for
source-distribution inspection; a beginner does not need to install it. The
manifest binds both files to a Git commit, version, size, SHA-256, completed
software gates, and the explicit `NO_NEW_HARDWARE_VALIDATION` boundary.

Do not install a file if its hash does not match the manifest. A hash mismatch
means the bytes are not the reviewed candidate, even if the filename looks
correct.

## Supported beta environments

Primary local product and installation evidence is Windows with Python 3.12.
The [2026-09-10 manual hosted verification](../reports/python310-compatibility-closeout-2026-09-10.md)
passed all eight jobs at `709c18f`, integrated through PR #11:

- Windows latest with Python 3.10, 3.12, and 3.14;
- Ubuntu latest with Python 3.10, 3.12, and 3.14;
- the full deterministic candidate build/install path on Windows with Python
  3.12.

The six host-test jobs passed; clean-install candidate verification was performed
on Windows/Python 3.12. Ubuntu skips Windows-specific GUI tests, so macOS and
Linux GUI behavior remain unverified. Python 3.12 is still the recommended
beta-test choice; see [local-first testing](LOCAL_TESTING_AND_CI.md).

## Windows: base installation

Use a short, new directory. This avoids the traditional Windows path-length
limit and keeps beta files separate from your normal Python environment. You do
not need to activate the virtual environment, so PowerShell execution-policy
settings do not need to change.

1. Install 64-bit Python 3.12 from python.org if it is not already available.
2. Copy the entire owner-provided candidate directory to `C:\avs-beta`.
3. Open PowerShell and run:

```powershell
$BetaRoot = "C:\avs-beta"
$Wheel = Join-Path $BetaRoot "mixed_signal_afe_validation_platform-0.1.0b1-py3-none-any.whl"
$ManifestPath = Join-Path $BetaRoot "release-manifest.json"
$Python = "py"

& $Python -3.12 --version
& $Python -3.12 -m venv (Join-Path $BetaRoot "venv")
$VenvPython = Join-Path $BetaRoot "venv\Scripts\python.exe"
$Cli = Join-Path $BetaRoot "venv\Scripts\analog-validation.exe"
```

4. Verify both distribution hashes before installation:

```powershell
$Manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
foreach ($Artifact in $Manifest.artifacts) {
    $ArtifactPath = Join-Path $BetaRoot $Artifact.filename
    $Actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $ArtifactPath).Hash.ToLowerInvariant()
    if ($Actual -ne $Artifact.sha256) {
        throw "Candidate hash mismatch. Stop and contact the project owner."
    }
}
```

5. Install the base wheel without resolving any third-party runtime dependency:

```powershell
& $VenvPython -m pip install --no-deps $Wheel
& $VenvPython -m pip check
& $Cli version --json
```

Expected version: `0.1.0b1`. If another version appears, stop and follow
[Troubleshooting](TROUBLESHOOTING.md); do not continue with mixed package files.

## Run the hardware-free acceptance demo

The destination must not already exist:

```powershell
$Demo = Join-Path $BetaRoot "demo-first-run"
& $Cli demo --output $Demo --json
```

Expected high-level fields are:

```text
outcome = PASS
evidence_source = SYNTHETIC
hardware_claim = NO_NEW_HARDWARE_VALIDATION
```

Open `C:\avs-beta\demo-first-run\report\report.html` in a browser and read the
evidence and limitations sections. It is a self-contained local file; the
product report requests no remote script, style, image, or font.

`PASS` means the installed software correctly processed the fixed synthetic
model under its declared criteria. It is not a measurement of an AFE, MSP430,
ADC, DAC, sensor, fan, wire, or laboratory instrument.

## Optional Dashboard smoke

Only after the CLI demo passes, a tester with a normal desktop may run:

```powershell
& $Cli dashboard
```

Keep the default Simulator source. Confirm that the six steps and evidence
language are readable, then close the window normally. A missing Tk/display or
headless session does not invalidate the CLI beta path; record it as an
environment limitation.

## Ubuntu: concise base path

Use Python 3.12 and a short private directory. Replace `/path/to/candidate` with
the directory supplied by the owner:

```bash
mkdir -p "$HOME/avs-beta"
python3.12 -m venv "$HOME/avs-beta/venv"
"$HOME/avs-beta/venv/bin/python" -m pip install --no-deps \
  /path/to/candidate/mixed_signal_afe_validation_platform-0.1.0b1-py3-none-any.whl
"$HOME/avs-beta/venv/bin/python" -m pip check
"$HOME/avs-beta/venv/bin/analog-validation" version --json
"$HOME/avs-beta/venv/bin/analog-validation" demo \
  --output "$HOME/avs-beta/demo-first-run" --json
```

Verify the owner-provided SHA-256 values with `sha256sum` before installation.
Dashboard behavior on Linux graphical environments is not currently a tested
claim; the CLI demo is the required path.

## Optional serial extra is not part of the base test

The base wheel does not install pyserial and does not need a controller. Do not
run port discovery or receive-only observation as part of the normal beta
checklist, even if a board happens to be connected.

If a later device-specific test is separately approved, the optional extra can
be installed from the same wheel:

```powershell
& $VenvPython -m pip install "$Wheel[serial]"
& $VenvPython -m pip check
```

Installing an extra is not permission to open a physical port. The exact
device, voltage domain, firmware/profile, ownership, and test procedure still
require a separate review.

## Next

Continue with the [Private beta testing guide](USER_TESTING_GUIDE.md) and keep
the original candidate directory unchanged until feedback has been accepted.
