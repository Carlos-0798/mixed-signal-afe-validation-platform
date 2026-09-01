# Third-Party Notices

This file records software that can be used to build, test, or extend this
project. It is not a substitute for the complete upstream license texts.

## Distributed runtime

The base `mixed-signal-afe-validation-platform` wheel declares no third-party
runtime dependency and does not vendor third-party Python packages.

The optional `serial` extra declares `pyserial>=3.5,<4`. pySerial is available
under the BSD-3-Clause license. Its upstream license is:

- <https://github.com/pyserial/pyserial/blob/master/LICENSE.txt>

Installing the optional extra installs pySerial as a separate distribution; it
is not copied into this project's wheel.

## Development and build tools

The development workflow can use setuptools, build, pytest, pytest-cov, mypy,
Ruff, and tomli. These tools are installed separately and are not vendored into
the project wheel. Their exact reviewed version ranges are recorded in
`pyproject.toml`; each remains governed by its own upstream license.

## Hosted CI actions

The CI workflow uses commit-pinned releases of:

- <https://github.com/actions/checkout>
- <https://github.com/actions/setup-python>
- <https://github.com/actions/upload-artifact>

They execute in GitHub Actions and are not distributed in the Python wheel.
Their repositories contain their respective license and dependency notices.

## Project license boundary

No open-source license has been selected for this project. `LICENSE` currently
reserves all rights pending the owner's decision. This notice documents
third-party terms; it does not grant a license to this project's source code,
documentation, binaries, name, or assets.
