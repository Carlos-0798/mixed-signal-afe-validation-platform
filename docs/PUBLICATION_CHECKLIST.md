# Publication and Portfolio Governance Checklist

**Last reviewed:** 2026-09-10. **Hardware claim:** `NO_NEW_HARDWARE_VALIDATION`.

The owner authorized public source publication with the reviewed history
retained, including eight groups of ordinary local-machine path disclosures.
[PR #10](https://github.com/Carlos-0798/mixed-signal-afe-validation-platform/pull/10)
is integrated into the default `main`, which carries the owner-selected MIT
license. The repository is public; anonymous default-source cloning,
installation, and the synthetic demo passed on 2026-09-10. No tag, Release,
or package publication is implied.

See the dated [closeout review](../reports/publication-readiness-2026-09-10.md)
for inspected revisions and findings, and the [integration record](../reports/public-source-integration-2026-09-10.md)
for completed publication checks. Checked preparation
items do not authorize a merge, visibility change, history rewrite, or social post.

## Publication levels

| Level | Meaning | Current status |
|---|---|---|
| A — Private engineering beta | Validated local software with private source review | Preparation complete |
| B — Public portfolio source | Recruiter-readable source, demo, evidence, and limitations | Public; anonymous clone/install/demo verified |
| C — Versioned beta release | Approved tag, release notes, and distribution artifacts | Deferred |
| D — Hardware-backed evidence | Physical setup, raw measurements, calibration, and limitations | No new validation |

Level B is complete. It does not require Level C or new product
features. Physical AFE performance cannot be inferred from any software gate.

## 1. Source and verification

- [x] Current software scope and the sample-driven continuation plan are saved
      in the [resume checkpoint](PROJECT_RESUME_CHECKPOINT_2026-09-09.md).
- [x] The [product synchronization gate](../reports/private-github-sync-2026-09-09.md)
      records 3,048 passing local tests, 100% package **statement** coverage,
      Ruff, mypy, dependency checks, and 15 product-quality checks.
- [x] [TD-052](../reports/td-052-voltage-import-2026-09-09.md) records fresh-installed
      CLI and real desktop acceptance; these are dated results, not new runs
      for later documentation changes.
- [x] Integrate PR #10 into default `main`; merge `36450c6` has the same tree
      as reviewed source `549e91f`, and the new main checkout was clean.
- [x] Main integration checks passed: 36 architecture checks and 87 documentation
      targets. Follow-up edits are Markdown only; runtime, tests, CI, media, and
      license text are unchanged. The full product gate was not repeated.
- [x] Verify the selected source from fresh private and anonymous checkouts;
      the Windows/Python 3.12 installed demo and artifact checks passed.
- [x] Align the PR description, license, screenshots, and test claims with
      the integrated source, keeping earlier evidence explicitly dated.

Cloud CI is **optional**, governed by [local-first testing](LOCAL_TESTING_AND_CI.md).
It is not a prerequisite for routine synchronization or a portfolio page.
Each dispatch/rerun needs an explicit owner instruction for that run. A blocked
or unexecuted hosted matrix stays `NOT_RUN`; local tests do not establish native
Linux/macOS compatibility. No cloud run was requested by this checklist.

## 2. Evidence and attribution

- [x] Current presentation identifies AVS as an independent software project,
      MSP430 Equipment Health Controller as a peer integration, and OSU Lab
      Bench Monitor Senior Capstone as a separate team project.
- [x] Current importer screenshots are actual application captures using
      synthetic input; the import preview is labeled `CSV_REPLAY`.
- [x] Portfolio wording emphasizes problem definition, architecture, reusable
      workflows, failure handling, and verifiable results.
- [x] Current synthetic fixtures and documentation review are described without
      implying hand-authored data or human peer review.
- [x] Check publication claims against the merge, local audit, anonymous
      installation, and visibility records; no new product screenshot was added.

Keep `HOST_TEST`, `SYNTHETIC`, `CSV_REPLAY`, `SPICE_IDEAL`, `BENCH_CONTROLLER`,
and `BENCH` distinct. Do not claim human time savings, operator-error reduction,
universal device support, production deployment, or AFE accuracy without evidence.
Historical reports retain their original counts and context. AI-assisted work
may be discussed accurately; editing current presentation is not a reason to
conceal tool use or rewrite attribution history.

## 3. Privacy and public surfaces

- [x] Candidate-tree scanning and approved binary identities have been checked;
      the dated report identifies the inspected scope and limits.
- [x] Reachable remote Git history and commit identities have been inspected.
- [x] The owner accepted the eight reviewed groups of ordinary local-machine
      path disclosures and chose to retain history without rewriting it.
- [x] Review repository issues, PR text/comments, Actions logs, and downloadable
      artifacts; 23 expired artifact bodies remain unavailable, as recorded in
      the dated report rather than labeled as passed.
- [x] No unresolved credential or unrelated private/team-material findings
      remain within the inspected scope. Accepted local paths and unavailable
      expired artifacts remain explicitly recorded limitations.

Pattern scanning is not a guarantee that every secret or personal detail has
been detected. Do not delete runs, rewrite history, or expose reviewed personal
information without the corresponding owner decision. A fresh authorized clone
can be reviewed while private; an **anonymous** clone is a post-publication
check, not an achievable prerequisite for a private repository.

## 4. Presentation and repository settings

- [x] README has a problem statement, real preview, architecture, runnable demo,
      verification routes, limitations, and a reviewer guide.
- [x] Repository description and topics have been synchronized to the software
      and data-workflow scope.
- [x] CONTRIBUTING, SECURITY, PR template, CODEOWNERS, and Dependabot files exist.
- [x] Read back settings after publication: no main branch protection or rulesets;
      private vulnerability reporting, secret scanning/push protection, and
      Dependabot security updates were disabled. No such feature was enabled
      by this publication; configuration files do not imply active rules.
- [x] Anonymous HTTP checks retrieved README, three linked documents, and three
      images with matching bytes; credential-disabled default clone/install/demo
      passed. Browser visual inspection used the owner's logged-in session and
      is separate from the anonymous checks.

A social-preview image is optional polish, not a source-publication blocker.
Where supported, use reviewed changes and protection against force pushes.
Do not introduce a mandatory automatic CI requirement that conflicts with the
owner's manual-only policy. Security features depend on the actual account and
repository settings; enabling them is a separate, reviewable action.

## 5. Authorized publication and remaining decisions

The owner selected the following source-publication scope:

1. Accept the eight reviewed path-disclosure groups and retain history unchanged.
2. Integrate PR #10 so the implemented software and MIT license are on `main`;
   this integration is complete.
3. Publish this repository's source after verification; the public visibility
   change and subsequent anonymous checks are complete.
4. Adding the GitHub link to LinkedIn remains a separate owner-approved action
   after signed-out verification.

Keep tags, Releases, package publication, historical rewrites, and hardware work
deferred unless separately requested. Approval of this source publication does
not imply approval of those actions.

## LinkedIn handoff

The copy-ready title, description, skills, and accurate AI-use interview note
are in [PORTFOLIO_COPY.md](PORTFOLIO_COPY.md). Dates should reflect the owner's
actual work period. Add the Featured/repository link only after public access
has been verified and the owner authorizes the social update.

## Platform reference

[GitHub's visibility documentation](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility)
explains that changing a repository to public also exposes its Actions history
and logs. This is why the review covers more than the current README and files.
