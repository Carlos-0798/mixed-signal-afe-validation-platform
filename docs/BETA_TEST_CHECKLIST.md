# Private beta checklist — `0.1.0b1`

Use one copy per tester/environment. Check only what was actually observed.

## Owner handoff

- [ ] Candidate came from one clean reviewed commit.
- [ ] Directory contains one wheel, one sdist, and one release manifest.
- [ ] Manifest status is PASS and artifact hashes were independently checked.
- [ ] Tester received the installation, testing, troubleshooting, and known
      limitation documents.
- [ ] Tester understands that no public license or redistribution permission is
      implied.

## Tester environment

- [ ] OS family/version recorded without username or full path.
- [ ] Python version/architecture recorded; Python 3.12 preferred.
- [ ] New short-path virtual environment created.
- [ ] No administrator, policy, security-software, or hardware change required.

## Required base path

- [ ] Candidate wheel/sdist SHA-256 values match the manifest.
- [ ] Base wheel installed with `--no-deps`.
- [ ] `pip check` passed.
- [ ] Installed version JSON is `0.1.0b1`.
- [ ] Demo exited `0` into a new directory.
- [ ] Demo outcome is PASS and source is SYNTHETIC.
- [ ] Demo hardware claim is `NO_NEW_HARDWARE_VALIDATION`.
- [ ] Demo contains 12 expected files and a readable local HTML report.
- [ ] Outcome, evidence, criteria, and not-verified sections were understandable.
- [ ] Reusing the same output directory was safely refused without overwrite.

## Optional paths

- [ ] Dashboard attempted and closed normally, or explicitly marked NOT_RUN.
- [ ] Replay attempted, or explicitly marked NOT_RUN.
- [ ] Serial remained NOT_RUN unless a separate device-specific procedure was
      explicitly approved.

## Privacy and feedback

- [ ] Feedback result chosen: PASS, PARTIAL, or BLOCKED.
- [ ] Paths replaced with `<beta-root>`.
- [ ] No username, email, token, private URL, USB/port identity, raw frame,
      candidate package, or private data attached.
- [ ] One issue describes one defect; general session feedback uses the test
      feedback form.
- [ ] Required-path failures preserve the original candidate/demo evidence.

Completing this checklist does not authorize a merge, tag, GitHub Release, license change, public repository, PyPI upload, LinkedIn publication, or v1.0 claim. Those remain owner-only Phase 6 Step 8 decisions.
