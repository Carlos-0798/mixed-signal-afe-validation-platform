# Private Beta Handoff Checklist

This checklist turns a build into a bounded, reviewable tester bundle. It does
not authorize publication or hardware access.

## 1. Maintainer creates the candidate

From a clean, full-history clone at the exact reviewed commit:

```powershell
python tools/release_candidate_check.py --output work/private-beta-candidate
python tools/release_audit.py `
  --candidate work/private-beta-candidate `
  --output work/private-beta-candidate/release-audit.json
```

Both commands are host-only. They do not enumerate or open ports, flash a
controller, operate instruments, publish a package, change visibility, choose a
license, or write application bytes to hardware.

## 2. Bundle inventory

The handoff directory must contain exactly four files after the audit:

1. one `0.1.0b1` wheel;
2. one `0.1.0b1` source distribution (`.tar.gz`);
3. `release-manifest.json` with build/install/demo evidence;
4. `release-audit.json` with archive, metadata, current-tree, history,
   workbook, license, privacy, and project-boundary results.

`release-audit.json` records the SHA-256 and byte size of the original three
candidate files. It intentionally has no self-hash. Transfer integrity for the
audit file must therefore be supplied in the owner's handoff message or by the
private delivery system.

## 3. Required maintainer checks

- candidate and audit source commits equal the intended commit;
- `candidate_status` is `PASS`;
- audit status is `PASS` or `PASS_WITH_REVIEW`;
- `private_binary_beta` is `READY`;
- any `OWNER_REVIEW_REQUIRED` item is explained to the tester and is not
  presented as resolved;
- the evidence boundary says `NO_NEW_HARDWARE_VALIDATION`, zero ports opened,
  and zero application bytes written;
- wheel/sdist hashes equal the release manifest and audit inventory;
- hosted CI is green for the same commit;
- tester receives [Installation](INSTALLATION.md),
  [User testing](USER_TESTING_GUIDE.md),
  [Troubleshooting](TROUBLESHOOTING.md),
  [Known limitations](KNOWN_LIMITATIONS.md), and
  [Beta checklist](BETA_TEST_CHECKLIST.md).

## 4. Tester boundary

The default test uses only the base wheel and deterministic demo. The tester
must not select Serial, connect or probe a controller, supply raw serial frames,
or treat a software PASS as a physical measurement. Optional hardware work
requires a separate device-specific plan and authorization.

## 5. Owner-only decisions

The owner's MIT license selection is recorded and implemented locally.
Do not infer approval for merge, tag, GitHub Release, PyPI upload, visibility
change, history rewrite, future license changes, LinkedIn publication, or v1.0.
Each requires an exact preview and explicit owner approval.
