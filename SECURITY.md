# Security Policy

## Supported versions

| Version or branch | Security support |
|---|---|
| Current `0.1.0b1` software beta on `main` | Best-effort fixes while the project remains pre-1.0 |
| Earlier snapshots and unmerged branches | Not separately supported |

This project is not a production safety system. Software checks, Simulator
results, and receive-only serial behavior do not certify an analog front end,
controller, wiring, instrument, or electrical installation.

## Report a vulnerability

Do not place exploit details, credentials, private captures, raw serial logs, or
personal information in a public issue.

Use GitHub's private vulnerability-reporting or Security Advisory channel when
it is enabled for this repository. While the repository remains private, use an
existing private collaboration channel with the repository owner. If neither
private route is available, open a minimal issue that says a private security
contact is needed, without including sensitive details.

For an ordinary, non-sensitive defect, use the repository's bug-report form.

A useful private report includes:

- the affected version or commit;
- the smallest reproducible input and exact command;
- expected and observed behavior;
- impact and reachable attack path;
- whether untrusted CSV, protocol bytes, paths, archives, or dependencies are
  involved;
- suggested remediation, if known;
- confirmation that secrets and unrelated personal data were removed.

No response-time or disclosure-time guarantee is offered during the pre-1.0 beta.
The owner will acknowledge, validate, scope, fix, and coordinate disclosure as
availability permits.

## Security-relevant product boundaries

The highest-priority properties are:

- malformed or oversized records fail closed and remain bounded;
- evidence provenance cannot be silently promoted;
- output-capable work requires explicit capability and safe-range preflight;
- the product serial surface remains receive-only;
- existing exports are not overwritten by default;
- user-facing errors do not expose raw internal details;
- build and release artifacts contain no credentials, absolute local paths, or
  undeclared physical evidence;
- optional dependencies do not enter the base runtime implicitly.

Physical safety, analog protection, instrument isolation, electromagnetic
compatibility, and long-duration hardware reliability are outside the current
software validation claim.

## Safe testing

Security testing must default to Simulator, repository fixtures, temporary CSV
files, and temporary output directories. Do not enumerate or open a physical
port, flash a controller, drive an output, or connect a load without a separate
owner-approved hardware test plan. Never commit real credentials, private
captures, or environment-specific evidence.
