# Public source integration — 2026-09-10

The owner approved retaining the reviewed development history, accepting its
ordinary local-profile path disclosures, merging PR #10, and making this
repository public after default-version verification. This decision applies
only to Analog Validation Studio.

## Integrated source

[PR #10](https://github.com/Carlos-0798/mixed-signal-afe-validation-platform/pull/10)
was marked Ready and merged with a normal merge commit:
`36450c630356b05e279c807daf307d1c785c8e18`.
The reviewed head was `549e91f77466ef7a8375714f2f61a9cd0d57b440`.
The predicted and actual merged trees both equal
`1b182a919f222d3f529f36e24ef154681d73483a`, exactly the reviewed candidate tree.
The development branch is retained; no commits were squashed or rewritten.

Main now includes the completed software and the already selected MIT text.
A documentation-only follow-up aligns current entry pages to the default source-install path;
these presentation edits do not change runtime code, tests, CI, media, or the
license text. Historical checkpoint reports retain their original dates and
results. Public source availability does not create a tagged Release or publish
a package to a registry.

## Disclosure disposition

The [pre-publication review](publication-readiness-2026-09-10.md) classified one
GitHub noreply identity and eight groups of ordinary machine-local project or
verification paths. The owner selected retention and disclosure of that history.
It is an accepted disclosure, not a claim that historical paths were erased.
No credential requiring removal was identified under the reviewed rules.

The review also covered 10 PR bodies, 44 available Actions attempt logs, and all
seven downloadable artifacts including wheel/source archives. Twenty-three
expired artifact bodies were unavailable and are not described as inspected.
No unrelated project or team output was introduced by this integration.

## Verification and publication record

The reviewed head already passed 36 local architecture checks, documentation
link and current-tree audits, and a fresh offline Windows/Python 3.12 installation.
All 100 runtime Python files matched their installed bytes; the installed demo
produced 24 `SYNTHETIC` points and 12 artifacts with verified sizes and hashes.
The full product gate remains the dated 3,048-test / 100% statement-coverage
result in the [synchronization report](private-github-sync-2026-09-09.md).

Final documentation checks, exact publication commit, visibility readback and
anonymous default-clone/install/demo results are recorded in the external
`avs-publication-20260910-01` receipt and summarized in PR #10 after execution.
This report does not pre-label a future anonymous check as passed.

Cloud CI remains manual-only. No cloud dispatch or rerun is part of this
publication. No tag, Release, package-registry upload, LinkedIn post, branch
deletion, hardware access, or history rewrite is included.
`HOST_TEST`, `SYNTHETIC`, `CSV_REPLAY`, `SPICE_IDEAL`,
`BENCH_CONTROLLER`, and `BENCH` remain separate evidence classes:
`NO_NEW_HARDWARE_VALIDATION`.

The software feature freeze continues. Resume from the saved
[checkpoint](../docs/PROJECT_RESUME_CHECKPOINT_2026-09-09.md) and select TD-053
only when a real, interpretable input sample justifies a bounded extension.
