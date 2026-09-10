# Publication and Portfolio Governance Checklist

**Last reviewed:** 2026-09-10. **Hardware claim:** `NO_NEW_HARDWARE_VALIDATION`.

The repository is private. Implemented software is on
`codex/calibration-workflow`, with [PR #10](https://github.com/Carlos-0798/mixed-signal-afe-validation-platform/pull/10)
still Draft and unmerged. Default `main` has the updated presentation but retains
the older runtime and license; the candidate carries the owner-selected MIT
license. No tag, Release, or package publication is implied by this checklist.

See the dated [closeout review](../reports/publication-readiness-2026-09-10.md)
for inspected revisions, findings, and remaining decisions. Checked preparation
items do not authorize a merge, visibility change, history rewrite, or social post.

## Publication levels

| Level | Meaning | Current status |
|---|---|---|
| A — Private engineering beta | Validated local software with private source review | Active |
| B — Public portfolio source | Recruiter-readable source, demo, evidence, and limitations | Pending owner decisions |
| C — Versioned beta release | Approved tag, release notes, and distribution artifacts | Deferred |
| D — Hardware-backed evidence | Physical setup, raw measurements, calibration, and limitations | No new validation |

Level B is the next useful target. It does not require Level C or new product
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
- [ ] Select the exact source revision/default-branch integration for public
      review and verify its clean-tree identity and change scope.
- [ ] Complete appropriate local checks for any changes since the recorded
      gate. Rerun the full product gate when runtime/test changes warrant it.
- [ ] Verify the selected source from a fresh authorized checkout or artifact
      and check the documented demo and links before publication.
- [ ] Ensure the PR description, license, screenshots, and test claims match
      the selected candidate and clearly identify historical evidence.

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
- [ ] Recheck any new claim or asset against its underlying evidence.

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
- [ ] Resolve each historical personal-information item through an explicit
      owner decision; a clean latest file does not remove earlier revisions.
- [x] Review repository issues, PR text/comments, Actions logs, and downloadable
      artifacts; 23 expired artifact bodies remain unavailable, as recorded in
      the dated report rather than labeled as passed.
- [ ] Confirm there are no unresolved credential findings or private/team
      material in the intended public surface.

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
- [ ] Recheck available security settings and branch protections at the selected
      publication point; do not equate configuration files with enabled rules.
- [ ] After approved public exposure, verify signed-out README/images/links and
      an anonymous clone/demo from the selected default revision.

A social-preview image is optional polish, not a source-publication blocker.
Where supported, use reviewed changes and protection against force pushes.
Do not introduce a mandatory automatic CI requirement that conflicts with the
owner's manual-only policy. Security features depend on the actual account and
repository settings; enabling them is a separate, reviewable action.

## 5. Remaining owner decisions

Before changing visibility, present the exact choices and affected material:

1. Resolve the historical disclosure items recorded in the closeout review.
2. Choose the public source/default branch and authorize any PR integration.
   The recommended product entry is the completed candidate, after integration
   review; this checklist does not mark PR #10 Ready or merge it.
3. Approve the visibility change for this repository only.
4. After signed-out verification, approve adding the GitHub link to LinkedIn.

Keep tags, Releases, package publication, historical rewrites, and hardware work
deferred unless separately requested. Updating the current private branch and
Draft PR does not imply approval of those actions.

## LinkedIn handoff

The copy-ready title, description, skills, and accurate AI-use interview note
are in [PORTFOLIO_COPY.md](PORTFOLIO_COPY.md). Dates should reflect the owner's
actual work period. A private link is not accessible to ordinary recruiters;
add the Featured/repository link after public access has been verified.

## Platform reference

[GitHub's visibility documentation](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility)
explains that changing a repository to public also exposes its Actions history
and logs. This is why the review covers more than the current README and files.
