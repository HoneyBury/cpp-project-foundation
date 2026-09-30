# Publishing the Python Tool

[简体中文](publishing.zh-CN.md)

This guide is only for maintainers publishing `cpp-project-foundation` itself. Projects
created by the tool do not need these steps.

Publishing has two separate stages:

1. the release workflow builds and publishes an immutable wheel on GitHub;
2. the PyPI workflow downloads that exact wheel, verifies it and uploads it to PyPI.

PyPI trusted publishing lets GitHub prove which repository and workflow started the job.
No long-lived PyPI password or API token is stored in GitHub.

## One-time setup

Create a pending trusted publisher on PyPI with these exact values:

| PyPI field | Value |
| --- | --- |
| Project name | `cpp-project-foundation` |
| GitHub owner | `HoneyBury` |
| GitHub repository | `cpp-project-foundation` |
| Workflow filename | `publish-pypi.yml` |
| Environment name | `pypi` |

Also create a GitHub environment named `pypi`. A single-maintainer repository may leave
environment reviewers empty. A team should normally require a reviewer.

Do not create or store a PyPI API token for this workflow.

## Before each publish

Confirm all of the following:

- the release pull request is merged and all required checks passed;
- the package, example manifest and workflow references use the same version;
- `CHANGELOG.md` has the release date instead of `Unreleased`;
- the version does not already exist as a Git tag, GitHub Release or PyPI release.

Create and push an annotated version tag from the merged `main` commit. The release
workflow builds the C++ example, release archive and Python wheel, verifies them, creates
signed build records and publishes the GitHub Release.

Do not continue until that workflow succeeds and the GitHub Release has the wheel and its
`.sha256` file.

## Run the no-upload check

This command checks everything but intentionally skips the PyPI upload:

```bash
gh workflow run publish-pypi.yml \
  --repo HoneyBury/cpp-project-foundation \
  -f release-tag=v0.7.0 \
  -f publish=false
```

The job verifies the tag and package version, checks the wheel checksum, installs the wheel
in a clean environment, creates a sample project, and runs `doctor` and `template-diff`.

## Publish to PyPI

Only after the no-upload run succeeds:

```bash
gh workflow run publish-pypi.yml \
  --repo HoneyBury/cpp-project-foundation \
  -f release-tag=v0.7.0 \
  -f publish=true
```

The first job repeats all verification. A separate job receives the verified wheel and
uses the short-lived GitHub identity to upload it.

## Verify the public package

After the workflow succeeds, wait for the version to appear on PyPI and install it from the
official index in a clean environment:

```bash
python3 -m venv /tmp/cpp-foundation-pypi-check
/tmp/cpp-foundation-pypi-check/bin/pip install \
  --index-url https://pypi.org/simple \
  "cpp-project-foundation==0.7.0"
/tmp/cpp-foundation-pypi-check/bin/cpp-foundation --help
```

Also compare the PyPI wheel SHA-256 with the `.sha256` file attached to the GitHub Release.
A local package mirror may take longer to show the new version than the official PyPI
index.

## If publishing fails

- Do not replace the tag.
- Do not enable `skip-existing`.
- Do not rebuild and upload different bytes under the same version.
- Preserve the workflow logs and determine whether the failure happened before or after
  PyPI accepted the file.
- If PyPI already accepted the version, fix the problem with a new version and release.

PyPI files and release tags are treated as permanent records.
