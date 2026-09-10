# Contributing

Analog Validation Studio is currently an owner-led private-beta project.
Contributions are reviewed by the maintainer. This branch uses the
[MIT License](LICENSE); dependency licenses are listed in
[Third-Party Notices](THIRD_PARTY_NOTICES.md). Repository visibility and
maintainer release decisions are separate from the rights granted by the license.

## Development setup

Use Python 3.12 for the primary local baseline. The optional manual hosted
matrix is configured for Python 3.10, 3.12, and 3.14 on Windows and Ubuntu;
configuration alone is not evidence of a passed run. Follow
[local testing and manual CI](docs/LOCAL_TESTING_AND_CI.md).

~~~powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe src tools tests examples
~~~

The base installation has no runtime dependency. Install `.[serial]` only for a
separately reviewed receive-only serial task.

Use one virtual environment per active Git worktree. An editable install stores
the source path it was created from; reusing that environment from another
worktree can silently import stale code. Before a gate, verify:

~~~powershell
.\.venv\Scripts\python.exe -c "import analog_validation_app; print(analog_validation_app.__file__)"
~~~

The printed path must belong to the worktree being tested. A temporary
`PYTHONPATH=<current-worktree>\src` is acceptable for a focused diagnostic, but
release evidence must use the repository's isolated build/install workflow.

On Windows, create release-gate virtual environments under a deliberate short
path when the checkout is deeply nested. A `pip` error that explicitly cites
Windows Long Path support must be recorded and repeated in a fresh short-path
environment before it is classified as a packaging defect.

## Engineering rules

- Keep `analog_validation` controller-neutral. Board SDKs, COM names, GUI code,
  and device-specific pins do not belong in the domain or analysis layers.
- Extend hardware support through the public adapter and versioned profile
  contracts; do not copy protocol or analysis implementations.
- Preserve immutable inputs, stable errors, bounds, deterministic fixtures,
  cleanup semantics, and create-new export behavior.
- Keep the Dashboard presentation-only. CRC, fitting, point exclusion,
  threshold calculation, and engineering conclusions stay in the tested core.
- Treat the MSP430 Equipment Health Controller as an independent peer product.
  Do not import its private runtime or merge its identity, claims, or history
  into this repository.
- Do not add OSU Lab Bench Monitor Senior Capstone material.

## Evidence and claims

Every measurement-like value must retain an explicit source:

- `SYNTHETIC` for deterministic software-generated observations;
- `CSV_REPLAY` for local replay;
- `HOST_TEST` for software/in-memory integration evidence;
- `SPICE_*` for simulation evidence;
- `BENCH_CONTROLLER` only for the exact controller-side bench scope recorded;
- a future AFE bench class only after documented physical setup and raw data.

A software PASS is not a hardware PASS. Pull requests must state what was not
tested and must not broaden a claim beyond the supplied evidence.

## Pull requests

1. Keep one reviewable purpose per pull request.
2. Add or update tests before changing a frozen behavior.
3. Update current-state documentation without rewriting historical checkpoint
   results.
4. Complete the pull-request template, including safety, privacy, evidence, and
   compatibility sections.
5. Run checks appropriate to the change. Runtime changes require the full
   quality gate; documentation-only changes need the relevant static checks.
   Cloud CI is manual-only and requires an explicit owner instruction for that run.
6. Do not include generated `work/` content, real port names, raw private
   captures, credentials, personal paths, or unrelated project material.
7. Do not mark a pull request Ready, merge, tag, publish, or change visibility
   unless the repository owner explicitly approves that action.

Use focused, imperative commit subjects such as:

~~~text
feat(dashboard): add explicit result navigation
fix(export): reject a mismatched file suffix
test(protocol): preserve CRC rejection boundaries
docs(governance): add publication checklist
~~~

## Compatibility changes

Public imports, schema/profile versions, dataclass fields, signatures, errors,
CLI paths and exits, serialized fields, and golden hashes are frozen by
compatibility tests. A breaking change requires an explicit version change,
migration notes, updated fixtures, and owner review; do not simply update a
golden expectation to make a failure disappear.

## Reporting problems

Use the issue forms for non-sensitive bugs and tester feedback. Follow
[SECURITY.md](SECURITY.md) for anything that could expose sensitive data or a
security weakness.
