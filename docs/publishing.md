# Python Distribution Publishing

[简体中文](publishing.zh-CN.md)

The GitHub Release remains the immutable source of the Python wheel. PyPI publishing
downloads that exact wheel, verifies its portable SHA-256 file, installs it in a clean
environment and transfers only the verified artifact to a separate OIDC-enabled job. The
privileged job does not checkout or execute repository code.

## One-time PyPI configuration

Create a pending trusted publisher for a new project on PyPI with these exact values:

| Field | Value |
| --- | --- |
| PyPI project name | `cpp-project-foundation` |
| GitHub owner | `HoneyBury` |
| GitHub repository | `cpp-project-foundation` |
| Workflow filename | `publish-pypi.yml` |
| Environment name | `pypi` |

The GitHub repository must also have an environment named `pypi`. Do not add a PyPI API
token: the publish job receives only a short-lived GitHub OIDC identity. Environment
reviewers are optional for a single maintainer and recommended for a team.

## Verify before publishing

After an immutable GitHub release exists, run the safe default path:

```bash
gh workflow run publish-pypi.yml \
  --repo HoneyBury/cpp-project-foundation \
  -f release-tag=v0.4.0 \
  -f publish=false
```

The workflow must verify the tag, package version, wheel checksum, installed CLI,
generated scaffold, `doctor` and `template-diff`. It stages the wheel for one day and
skips the OIDC job.

## Publish

Only after the trusted publisher fields match and the dry-run succeeds:

```bash
gh workflow run publish-pypi.yml \
  --repo HoneyBury/cpp-project-foundation \
  -f release-tag=v0.4.0 \
  -f publish=true
```

PyPI distributions are immutable. Never enable `skip-existing`, replace a Git tag or
rebuild an already published version. A correction requires a new semantic version and a
new GitHub release.

After PyPI reports the release, users can install it without a source checkout:

```bash
pipx install "cpp-project-foundation==0.4.0"
```
