# Publication and Portfolio Governance Checklist

**Last reviewed:** 2026-09-03

**Current state:** Private repository, Draft PR #7, package `0.1.0b1`, no tag,
no GitHub Release, no selected open-source license

**Hardware claim:** `NO_NEW_HARDWARE_VALIDATION`

This checklist governs the transition from a locally validated private-beta
project to a recruiter-visible GitHub portfolio and, later, a controlled
release. Checking a preparation item does not authorize the corresponding
remote action.

## Publication levels

| Level | Meaning | Current status |
|---|---|---|
| A — Private engineering beta | Local/hosted software evidence, private review, no public claim | Active |
| B — Public portfolio source | Recruiter-readable repository, screenshots, demo, governance, no Release required | Not authorized |
| C — Versioned beta release | Signed-off tag/Release, immutable release notes and artifacts | Not authorized |
| D — Hardware-backed product evidence | Physical AFE setup, raw bench data, instruments, calibration and limitations | Not started |

The next sensible target is Level B. Level C should follow only after the
public presentation has been reviewed in an anonymous browser session. Level D
is a separate hardware program and cannot be inferred from Levels A–C.

## 1. Technical release gate

- [ ] Working tree contains only the approved change set.
- [ ] Focused tests pass.
- [ ] Full pytest and package statement coverage pass at the documented count.
- [ ] Ruff, mypy, dependency checks, build, and fresh base/serial installs pass.
- [ ] Deterministic demo reproduces in normal and Unicode paths.
- [ ] Release-candidate verification runs from the exact clean commit proposed
      for publication.
- [ ] Hosted CI passes on the exact head commit.
- [ ] Draft PR description matches the exact head, counts, and limitations.

## 2. Evidence and claim gate

- [ ] README separates `SYNTHETIC`, `CSV_REPLAY`, `HOST_TEST`,
      `BENCH_CONTROLLER`, `SPICE_*`, and future AFE bench evidence.
- [ ] Screenshots state their source and do not imply physical measurement.
- [ ] Current-state documents agree on phase, version, test count, coverage,
      release status, and hardware status.
- [ ] Historical reports keep their original dates and counts.
- [ ] No statement implies production readiness, electrical certification,
      long-duration reliability, or a validated AFE.
- [ ] MSP430 compatibility is described as a peer integration through public
      interfaces, not an ownership or merge relationship.
- [ ] OSU Lab Bench Monitor Senior Capstone work is not present or claimed.

## 3. Privacy and repository-history gate

- [ ] Current tree contains no credentials, personal email, local absolute
      paths, private captures, receipts, unpublished team material, or raw
      physical logs.
- [ ] Generated `work/`, build, cache, virtual-environment, and local evidence
      files are ignored.
- [ ] The latest release audit reports zero current-tree privacy findings and
      zero high-confidence credentials.
- [ ] Every legacy history-review item is inspected and either accepted,
      remediated with an explicit history plan, or documented as non-sensitive.
- [ ] An anonymous clone/search check is complete before visibility changes.

Changing visibility before this section is complete may permanently expose Git
history through clones, forks, caches, or search indexing.

## 4. GitHub presentation gate

- [x] Recruiter-first README structure: value, preview, architecture, demo,
      verification, boundaries, roadmap.
- [x] Real application screenshots use deterministic Simulator data.
- [x] Repository map and documentation routes are concise.
- [x] CONTRIBUTING, SECURITY, PR template, CODEOWNERS, and Dependabot
      configuration are prepared locally.
- [x] All README and documentation links pass the 2026-09-03 local automated
      scan.
- [ ] GitHub description and topics have an approved exact preview.
- [ ] A 1280×640 PNG/JPG social-preview candidate is approved and uploaded in
      repository settings.
- [ ] The repository is reviewed while signed out or in a private browser after
      any visibility change.

The current screenshots are product evidence for the README. They are not
automatically uploaded as GitHub's social-preview image; that setting is a
separate owner-approved remote action.

The unapproved exact wording and topic proposal are staged in
[`PORTFOLIO_COPY.md`](PORTFOLIO_COPY.md). Preparing that preview does not change
the GitHub repository or LinkedIn profile.

## 5. Repository protection gate

- [ ] Private vulnerability reporting is enabled before public exposure.
- [ ] Secret scanning and dependency alerts are enabled where the account and
      repository plan permit.
- [ ] Dependabot configuration is merged and observed once.
- [ ] Branch/ruleset protection is enabled for `main` with required CI checks,
      pull-request review, and no force pushes, where the GitHub plan permits.
- [ ] Tag and Release permissions are restricted to the owner.

At the 2026-09-03 audit, branch-protection/ruleset configuration was unavailable
for this private repository under the current GitHub plan. Recheck after a
visibility or account-plan decision; do not claim protection before GitHub
accepts and displays the rule.

## 6. Owner decisions required before any remote publication

Each item needs an exact preview and explicit approval:

- [ ] Mark PR #7 Ready.
- [ ] Merge PR #7 and choose whether to retain its branch.
- [ ] Choose repository visibility.
- [ ] Choose an open-source license or intentionally retain all rights.
- [ ] Approve GitHub description and topics.
- [ ] Approve and upload the social-preview image.
- [ ] Approve `v0.1.0b1` tag and GitHub Release, or defer both.
- [ ] Approve package-registry publication, or keep distribution on GitHub only.
- [ ] Approve LinkedIn Featured link and project wording.

These decisions are independent. For example, a repository may become visible
without publishing a Release, and a Release must not be inferred from a merged
pull request.

## 7. LinkedIn handoff

Use only claims that a recruiter can verify from the public repository:

- role: independent product designer/developer;
- product: controller-neutral analog validation and test-automation software;
- evidence: tested CLI/Dashboard, deterministic demo, reports, adapters,
  protocol/CRC, analysis, CI, packaging, and governance;
- compatibility: public receive-only MSP430 profile as one peer integration;
- limitation: configurable AFE hardware remains unbuilt and unvalidated.

Before adding the link:

- [ ] Open the final GitHub page while signed out.
- [ ] Run the documented demo from a fresh clone or release artifact.
- [ ] Confirm every screenshot and badge renders.
- [ ] Confirm no private issue, branch, artifact, or local path is linked.
- [ ] Freeze the exact LinkedIn title, description, skills, and repository URL
      for owner approval.

The current wording candidate is in
[`PORTFOLIO_COPY.md`](PORTFOLIO_COPY.md); keep the item above unchecked until
the owner approves the final public commit and wording.

## Authoritative platform references

- [GitHub: About READMEs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes)
- [GitHub: Social preview](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview)
- [GitHub: Repository visibility](https://docs.github.com/en/repositories/creating-and-managing-repositories/about-repositories)
- [GitHub: Licensing](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)
- [GitHub: Protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches)
- [GitHub: Repository security quickstart](https://docs.github.com/en/code-security/getting-started/quickstart-for-securing-your-repository)
- [GitHub: Dependabot version updates](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configure-version-updates)
- [LinkedIn: Feature samples of your work](https://www.linkedin.com/help/linkedin/answer/a550399/feature-samples-of-your-work-on-your-linkedin-profile)
