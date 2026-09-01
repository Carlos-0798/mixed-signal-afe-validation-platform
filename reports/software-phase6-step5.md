# Software Phase 6 Step 5 Verification Report

- **Date:** 2026-08-31
- **Checkpoint:** Private-beta tester workflow
- **Implementation commit:** `5dc10db3a580f68038bf41e144a20900ab244350`
- **Evidence:** `HOST_TEST`, `SYNTHETIC`, and optional `CSV_REPLAY` only
- **Hardware claim:** `NO_NEW_HARDWARE_VALIDATION`

## Outcome

Software Phase 6 Step 5 is complete. An invited beginner can now verify an
owner-provided candidate, install its wheel in a new short-path environment,
run the deterministic demo, inspect evidence limits, exercise create-new
protection, and submit bounded feedback without repository knowledge or
hardware.

The workflow adds:

- `docs/INSTALLATION.md`;
- `docs/USER_TESTING_GUIDE.md`;
- `docs/TROUBLESHOOTING.md`;
- `docs/KNOWN_LIMITATIONS.md`;
- `docs/BETA_TEST_CHECKLIST.md`;
- structured private-beta bug and session-feedback issue forms;
- architecture tests that freeze the required commands, evidence language,
  privacy rules, physical-port stop conditions, and owner-only publication
  decisions.

## Verification summary

| Gate | Result |
|---|---|
| Focused documentation contract | PASS — 5 tests |
| Full local suite | PASS — 2,216 tests, 0 skipped |
| Package statement coverage | PASS — 11,470/11,470, 100% |
| Ruff | PASS — full `src`, `tools`, and `tests` rule check |
| mypy | PASS — 196 source/tool/test files |
| Dependency consistency | PASS — no broken requirements |
| Issue-form YAML parsing | PASS — 3 files |
| Hosted CI | PASS — [run 33448157429](https://github.com/Carlos-0798/mixed-signal-afe-validation-platform/actions/runs/33448157429) |
| Hosted host matrix | PASS — Windows/Ubuntu, Python 3.10/3.12/3.14 |
| Hosted candidate verifier | PASS — deterministic build, installs, demos, and manifest |

The hosted candidate from the implementation commit contained exactly:

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| wheel | 246,984 | `e269e8f768836b8a20d60d8a64b26907a4c04406b5424741c9e8ce5ce1beff00` |
| normalized sdist | 450,967 | `5cdda2d823a91e3bfd53c2c373b797f789bba316e8560b45c37902a6a979b13b` |
| release manifest | 4,938 | `9d8e45730ea23345c673c7f45b69562acd0cd959ed17b975c699f56a5fb1b5a0` |

These hashes identify this checkpoint candidate only. Later reviewed commits
will intentionally create different candidate identities.

## Repository-external tester journey

The hosted artifact was downloaded and copied into a new short directory shown
here only as `<beta-root>`. The documented Windows path was then executed with
Python 3.12.10:

1. both wheel and sdist SHA-256 values matched `release-manifest.json`;
2. a new venv was created without activation or execution-policy changes;
3. `pip install --no-deps <wheel>` and `pip check` passed;
4. the base environment contained no pyserial module;
5. installed `analog-validation version --json` returned `0.1.0b1`;
6. two create-new installed demos each produced the same 12 byte-identical
   artifacts;
7. CLI JSON returned `PASS`, `SYNTHETIC`, and
   `NO_NEW_HARDWARE_VALIDATION`;
8. the self-contained HTML report visibly retained synthetic/not-verified
   language;
9. reusing an existing destination returned exit `5` with `OUTPUT_EXISTS`, and
   every existing artifact hash remained unchanged;
10. the optional Replay command exited successfully and retained
    `CSV_REPLAY` provenance.

The optional Dashboard was `NOT_RUN` in this tester journey. Earlier Windows
Tk launch/close, scaling, and focus evidence remains valid historical evidence,
but it is not relabeled as a Step 5 execution. Serial was `NOT_RUN`; no port was
discovered or opened.

## Diagnostic transparency

Two post-command harness assertions initially read valid product output from
the wrong place: one looked for CLI summary fields at the top of the detailed
result bundle, and one expected native stderr JSON in PowerShell's stdout
variable. The commands themselves had already produced their documented
results. The checks were corrected to assert direct CLI JSON and merged native
stderr respectively, then passed. No product code or evidence artifact was
changed or overwritten to obtain the PASS result.

## Safety, privacy, and publication boundary

- Feedback requests controlled versions, hashes, exit/issue codes, and
  evidence fields, not usernames, full paths, credentials, private URLs,
  USB/port identity, raw UART data, or candidate attachments.
- Base testing defaults to Simulator and requires no MSP430, AFE, instrument,
  admin access, or security-policy change.
- Installing the optional serial extra is not permission to enumerate or open
  a physical port.
- No merge, tag, GitHub Release, PyPI upload, visibility change, license
  selection, LinkedIn publication, or v1.0 claim was performed or authorized.
- No configurable AFE was purchased, assembled, powered, or measured. Verified
  AFE hardware performance claims remain zero.

## Next checkpoint

Step 6 will prove extensibility with a repository-external-style read-only
adapter that imports only installed public APIs and runs through the shared
workflow. It must demonstrate lifecycle cleanup, capability/read behavior,
explicit provenance, no application write surface, and no dependency on
repository-private modules.
